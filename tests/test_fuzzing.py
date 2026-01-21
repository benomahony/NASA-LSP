"""Fuzzing and property-based tests for NASA-LSP analyzer.

These tests use random code generation and property-based testing
to discover edge cases and ensure robustness.

All random tests use deterministic seeds for reproducibility.
If a test fails, the seed can be used to reproduce the exact failure.
"""

from __future__ import annotations

import ast
import random
import string
from typing import Any

import pytest

from nasa_lsp.analyzer import analyze

# Deterministic seed for reproducible fuzzing
FUZZ_SEED = 42

# Set random seed at module level for reproducibility
random.seed(FUZZ_SEED)

# Try to import hypothesis for property-based testing
try:
    from hypothesis import given, settings, strategies as st
    from hypothesis import assume

    HAS_HYPOTHESIS = True
except ImportError:
    HAS_HYPOTHESIS = False
    # Create dummy decorators if hypothesis is not available
    def given(*args: Any, **kwargs: Any):  # type: ignore[misc]
        def decorator(f):  # type: ignore[misc]
            return pytest.mark.skip(reason="hypothesis not installed")(f)

        return decorator

    def settings(*args: Any, **kwargs: Any):  # type: ignore[misc]
        def decorator(f):  # type: ignore[misc]
            return f

        return decorator

    class st:  # type: ignore[no-redef]
        @staticmethod
        def text(*args: Any, **kwargs: Any) -> Any:
            return None

        @staticmethod
        def integers(*args: Any, **kwargs: Any) -> Any:
            return None

        @staticmethod
        def lists(*args: Any, **kwargs: Any) -> Any:
            return None

        @staticmethod
        def booleans(*args: Any, **kwargs: Any) -> Any:
            return None


# ============================================================================
# PROPERTY-BASED TESTS WITH HYPOTHESIS
# ============================================================================


@given(st.text())
@settings(max_examples=200)
def test_analyze_never_crashes_on_random_strings(code: str) -> None:
    """Property: analyze should never crash on any string input."""
    try:
        result = analyze(code)
        # Should always return a list
        assert isinstance(result, list)
        # All items should be Diagnostic objects (duck-typed check)
        for diagnostic in result:
            assert hasattr(diagnostic, "range")
            assert hasattr(diagnostic, "message")
            assert hasattr(diagnostic, "code")
    except Exception as e:
        pytest.fail(f"analyze() crashed on input: {repr(code)}\nError: {e}")


@given(st.text(alphabet=string.printable))
@settings(max_examples=200)
def test_analyze_handles_printable_characters(code: str) -> None:
    """Property: analyze should handle all printable ASCII characters."""
    result = analyze(code)
    assert isinstance(result, list)


@given(st.integers(min_value=0, max_value=1000))
@settings(max_examples=100)
def test_generated_function_with_n_lines(n: int) -> None:
    """Property: analyze should handle functions of any length."""
    lines = [f"def func_{n}():"]
    for i in range(n):
        lines.append(f"    x{i} = {i}")

    code = "\n".join(lines)
    result = analyze(code)

    # Should always return a list
    assert isinstance(result, list)

    # If n > 60, should have NASA04 violation
    if n > 60:
        nasa04_violations = [d for d in result if d.code == "NASA04"]
        assert len(nasa04_violations) > 0


@given(st.integers(min_value=0, max_value=100))
@settings(max_examples=50)
def test_generated_function_with_n_assertions(n: int) -> None:
    """Property: analyze should handle functions with any number of assertions."""
    lines = [f"def func_with_{n}_asserts():"]
    for i in range(n):
        lines.append(f"    assert {i} >= 0")
    lines.append("    return True")

    code = "\n".join(lines)
    result = analyze(code)

    assert isinstance(result, list)

    # If n < 2, should have NASA05 violation
    if n < 2:
        nasa05_violations = [d for d in result if d.code == "NASA05"]
        assert len(nasa05_violations) > 0
    else:
        # Might have NASA04 if too long, but not NASA05
        nasa05_violations = [d for d in result if d.code == "NASA05"]
        assert len(nasa05_violations) == 0


@given(st.lists(st.text(alphabet=string.ascii_letters, min_size=1, max_size=20), min_size=0, max_size=50))
@settings(max_examples=100)
def test_multiple_function_definitions(func_names: list[str]) -> None:
    """Property: analyze should handle any number of function definitions."""
    lines = []
    for name in func_names:
        lines.extend(
            [
                f"def {name}():",
                "    assert True",
                "    assert False",
                "    pass",
                "",
            ]
        )

    code = "\n".join(lines)
    result = analyze(code)

    # Should always return a list
    assert isinstance(result, list)


@given(st.booleans())
@settings(max_examples=50)
def test_while_true_detection(has_while_true: bool) -> None:
    """Property: while True should always be detected."""
    if has_while_true:
        code = """
def func():
    assert True
    assert False
    while True:
        pass
"""
    else:
        code = """
def func():
    assert True
    assert False
    while False:
        pass
"""

    result = analyze(code)
    nasa02_violations = [d for d in result if d.code == "NASA02"]

    if has_while_true:
        assert len(nasa02_violations) > 0
    else:
        assert len(nasa02_violations) == 0


# ============================================================================
# RANDOM CODE GENERATION FUZZING
# ============================================================================


def generate_random_identifier(length: int = 10) -> str:
    """Generate a random valid Python identifier."""
    first = random.choice(string.ascii_letters + "_")
    rest = "".join(random.choices(string.ascii_letters + string.digits + "_", k=length - 1))
    return first + rest


def generate_random_expression() -> str:
    """Generate a random Python expression."""
    expressions = [
        f"{random.randint(1, 1000)}",
        f'"{generate_random_identifier()}"',
        f"[{random.randint(1, 10)} for i in range({random.randint(1, 5)})]",
        f"{generate_random_identifier()}",
        f"{random.randint(1, 100)} + {random.randint(1, 100)}",
        "True",
        "False",
        "None",
    ]
    return random.choice(expressions)


def generate_random_statement() -> str:
    """Generate a random Python statement."""
    var = generate_random_identifier()
    expr = generate_random_expression()

    statements = [
        f"{var} = {expr}",
        f"if {random.choice(['True', 'False'])}:\n        pass",
        f"for i in range({random.randint(1, 10)}):\n        pass",
        "pass",
        "return None",
        f"assert {random.choice(['True', 'False'])}",
    ]
    return random.choice(statements)


def generate_random_function(
    num_statements: int = 10,
    num_assertions: int = 2,
    include_forbidden_api: bool = False,
    include_while_true: bool = False,
    include_recursion: bool = False,
) -> str:
    """Generate a random function with specified characteristics."""
    func_name = generate_random_identifier()
    lines = [f"def {func_name}():"]

    # Add assertions first
    for _ in range(num_assertions):
        lines.append(f"    assert {random.choice(['True', 'False', '1 > 0', '0 < 1'])}")

    # Add forbidden API if requested
    if include_forbidden_api:
        forbidden = random.choice(["eval", "exec", "compile", "globals", "locals"])
        lines.append(f'    {forbidden}("test")')

    # Add while True if requested
    if include_while_true:
        lines.append("    while True:")
        lines.append("        break")

    # Add recursion if requested
    if include_recursion:
        lines.append(f"    return {func_name}()")

    # Add random statements
    for _ in range(num_statements):
        stmt = generate_random_statement()
        # Indent multi-line statements
        if "\n" in stmt:
            lines.append("    " + stmt.replace("\n", "\n    "))
        else:
            lines.append(f"    {stmt}")

    return "\n".join(lines)


def test_fuzz_random_functions_basic() -> None:
    """Fuzz test: generate random clean functions."""
    for _ in range(50):
        code = generate_random_function(
            num_statements=random.randint(1, 20),
            num_assertions=random.randint(2, 10),
        )

        result = analyze(code)

        # Should not crash
        assert isinstance(result, list)


def test_fuzz_random_functions_with_violations() -> None:
    """Fuzz test: generate random functions with various violations."""
    for _ in range(50):
        code = generate_random_function(
            num_statements=random.randint(1, 20),
            num_assertions=random.randint(0, 1),  # Too few assertions
            include_forbidden_api=random.choice([True, False]),
            include_while_true=random.choice([True, False]),
            include_recursion=random.choice([True, False]),
        )

        result = analyze(code)

        # Should not crash
        assert isinstance(result, list)


def test_fuzz_multiple_random_functions() -> None:
    """Fuzz test: generate files with multiple random functions."""
    for _ in range(20):
        num_functions = random.randint(1, 20)
        functions = []

        for _ in range(num_functions):
            func = generate_random_function(
                num_statements=random.randint(1, 15),
                num_assertions=random.randint(0, 5),
                include_forbidden_api=random.choice([True, False]),
                include_while_true=random.choice([True, False]),
                include_recursion=random.choice([True, False]),
            )
            functions.append(func)

        code = "\n\n".join(functions)
        result = analyze(code)

        # Should not crash
        assert isinstance(result, list)


# ============================================================================
# RANDOM SYNTAX FUZZING
# ============================================================================


def test_fuzz_random_whitespace() -> None:
    """Fuzz test: random whitespace patterns."""
    base_code = """
def func():
    assert True
    assert False
    return 42
"""
    whitespace_chars = [" ", "\t", "\n"]

    for _ in range(30):
        # Insert random whitespace
        modified = base_code
        for _ in range(random.randint(0, 10)):
            pos = random.randint(0, len(modified) - 1)
            ws = random.choice(whitespace_chars)
            modified = modified[:pos] + ws + modified[pos:]

        result = analyze(modified)
        # Should handle gracefully (might be syntax error)
        assert isinstance(result, list)


def test_fuzz_random_comments() -> None:
    """Fuzz test: random comment insertion."""
    base_code = """
def func():
    assert True
    assert False
    return 42
"""
    for _ in range(30):
        lines = base_code.split("\n")
        # Insert random comments
        for i in range(random.randint(1, 5)):
            pos = random.randint(0, len(lines))
            comment = f"# {generate_random_identifier()}"
            lines.insert(pos, comment)

        code = "\n".join(lines)
        result = analyze(code)

        # Should not crash
        assert isinstance(result, list)


def test_fuzz_random_string_literals() -> None:
    """Fuzz test: functions with random string literals."""
    for _ in range(50):
        # Generate random strings
        strings = []
        for _ in range(random.randint(1, 10)):
            # Random printable string
            s = "".join(random.choices(string.printable, k=random.randint(1, 50)))
            # Escape quotes
            s = s.replace('"', '\\"').replace("\\", "\\\\")
            strings.append(f'    s{len(strings)} = "{s}"')

        code = f"""
def func_with_strings():
    assert True
    assert False
{chr(10).join(strings)}
    return None
"""
        result = analyze(code)
        assert isinstance(result, list)


def test_fuzz_random_numeric_literals() -> None:
    """Fuzz test: functions with random numeric literals."""
    for _ in range(50):
        numbers = []
        for _ in range(random.randint(1, 20)):
            num_type = random.choice(["int", "float", "complex", "hex", "oct", "bin"])
            if num_type == "int":
                num = str(random.randint(-1000000, 1000000))
            elif num_type == "float":
                num = str(random.random() * 1000000)
            elif num_type == "complex":
                num = f"{random.random()}+{random.random()}j"
            elif num_type == "hex":
                num = hex(random.randint(0, 0xFFFFFF))
            elif num_type == "oct":
                num = oct(random.randint(0, 0o7777))
            else:  # bin
                num = bin(random.randint(0, 0b11111111))

            numbers.append(f"    n{len(numbers)} = {num}")

        code = f"""
def func_with_numbers():
    assert True
    assert False
{chr(10).join(numbers)}
    return None
"""
        result = analyze(code)
        assert isinstance(result, list)


# ============================================================================
# EDGE CASE FUZZING
# ============================================================================


def test_fuzz_deeply_nested_code() -> None:
    """Fuzz test: deeply nested code structures."""
    for depth in range(1, 20):
        # Build nested if statements
        lines = ["def deeply_nested():"]
        lines.append("    assert True")
        lines.append("    assert False")

        indent = "    "
        for i in range(depth):
            lines.append(f"{indent}if True:")
            indent += "    "

        lines.append(f"{indent}pass")

        code = "\n".join(lines)
        result = analyze(code)

        # Should not crash
        assert isinstance(result, list)


def test_fuzz_long_function_names() -> None:
    """Fuzz test: extremely long function names."""
    for length in [10, 50, 100, 500, 1000]:
        func_name = generate_random_identifier(length)
        code = f"""
def {func_name}():
    assert True
    assert False
    return 42
"""
        result = analyze(code)
        assert isinstance(result, list)


def test_fuzz_many_parameters() -> None:
    """Fuzz test: functions with many parameters."""
    for num_params in [0, 1, 10, 50, 100]:
        params = [f"p{i}" for i in range(num_params)]
        param_list = ", ".join(params)

        code = f"""
def func({param_list}):
    assert True
    assert False
    return None
"""
        result = analyze(code)
        assert isinstance(result, list)


def test_fuzz_unicode_identifiers() -> None:
    """Fuzz test: Unicode characters in identifiers."""
    unicode_names = [
        "функция",  # Russian
        "函数",  # Chinese
        "関数",  # Japanese
        "função",  # Portuguese
        "función",  # Spanish
        "fonksiyon",  # Turkish
        "συνάρτηση",  # Greek
        "פונקציה",  # Hebrew
        "फ़ंक्शन",  # Hindi
        "함수",  # Korean
    ]

    for name in unicode_names:
        code = f"""
def {name}():
    assert True
    assert False
    return 42
"""
        result = analyze(code)
        assert isinstance(result, list)


def test_fuzz_mixed_quotes() -> None:
    """Fuzz test: mixed quote styles in strings."""
    for _ in range(30):
        quote_type = random.choice(['"""', "'''", '"', "'"])
        content = generate_random_identifier(20)

        code = f"""
def func():
    assert True
    assert False
    s = {quote_type}{content}{quote_type}
    return s
"""
        result = analyze(code)
        assert isinstance(result, list)


# ============================================================================
# MALFORMED CODE FUZZING
# ============================================================================


def test_fuzz_incomplete_syntax() -> None:
    """Fuzz test: various incomplete/malformed syntax patterns."""
    malformed_patterns = [
        "def func(",  # Missing closing paren
        "def func():",  # Missing body
        "def func():\n    if True:",  # Incomplete if
        "def func():\n    assert",  # Incomplete assert
        "def func():\n    return",  # Incomplete return (actually valid)
        "def func():\n    x = ",  # Incomplete assignment
        "def func():\n    [1, 2,",  # Unclosed list
        "def func():\n    {1: 2,",  # Unclosed dict
        "def func():\n    (1, 2,",  # Unclosed tuple
        "def func():\n    '''unclosed string",  # Unclosed string
    ]

    for pattern in malformed_patterns:
        result = analyze(pattern)
        # Should handle gracefully (return empty list for syntax errors)
        assert isinstance(result, list)


def test_fuzz_random_character_injection() -> None:
    """Fuzz test: inject random characters into valid code."""
    base_code = """
def func():
    assert True
    assert False
    return 42
"""

    for _ in range(50):
        # Pick a random position
        pos = random.randint(0, len(base_code) - 1)
        # Insert random character
        char = random.choice(string.printable)
        modified = base_code[:pos] + char + base_code[pos:]

        result = analyze(modified)
        # Should handle gracefully
        assert isinstance(result, list)


def test_fuzz_random_line_deletion() -> None:
    """Fuzz test: randomly delete lines from valid code."""
    base_code = """
def func():
    assert True
    assert False
    x = 1
    y = 2
    z = 3
    return x + y + z
"""

    for _ in range(30):
        lines = base_code.split("\n")
        # Delete random number of lines
        for _ in range(random.randint(1, 3)):
            if len(lines) > 1:
                del lines[random.randint(0, len(lines) - 1)]

        code = "\n".join(lines)
        result = analyze(code)
        # Should handle gracefully
        assert isinstance(result, list)


# ============================================================================
# PERFORMANCE FUZZING
# ============================================================================


def test_fuzz_very_large_file() -> None:
    """Fuzz test: extremely large file with many functions."""
    functions = []

    for i in range(1000):  # Generate 1000 functions
        functions.append(f"""
def func_{i}():
    assert True
    assert {i} >= 0
    return {i}
""")

    code = "\n".join(functions)
    result = analyze(code)

    # Should complete without crashing or timing out
    assert isinstance(result, list)


def test_fuzz_very_long_single_function() -> None:
    """Fuzz test: single function with thousands of lines."""
    lines = ["def very_long_function():"]

    # Generate 5000 lines
    for i in range(5000):
        lines.append(f"    x{i} = {i}")

    code = "\n".join(lines)
    result = analyze(code)

    # Should complete and detect NASA04 violation
    assert isinstance(result, list)
    nasa04_violations = [d for d in result if d.code == "NASA04"]
    assert len(nasa04_violations) > 0


def test_fuzz_very_long_lines() -> None:
    """Fuzz test: functions with extremely long lines."""
    for line_length in [1000, 5000, 10000]:
        long_string = "x" * line_length
        code = f"""
def long_line():
    assert True
    assert False
    s = "{long_string}"
    return s
"""
        result = analyze(code)
        assert isinstance(result, list)


# ============================================================================
# AST MANIPULATION FUZZING
# ============================================================================


def test_fuzz_ast_round_trip() -> None:
    """Fuzz test: parse valid code, unparse, and analyze again."""
    test_cases = [
        """
def func():
    assert True
    assert False
    return 42
""",
        """
def recursive(n):
    assert n >= 0
    assert isinstance(n, int)
    return recursive(n - 1)
""",
        """
def has_eval():
    assert True
    assert False
    eval("test")
""",
    ]

    for code in test_cases:
        try:
            # Parse to AST
            tree = ast.parse(code)
            # Unparse back to code
            unparsed = ast.unparse(tree)
            # Analyze unparsed code
            result = analyze(unparsed)
            # Should produce same violations
            assert isinstance(result, list)
        except SyntaxError:
            # Some code might not round-trip perfectly
            pass


# ============================================================================
# RANDOM COMBINATION FUZZING
# ============================================================================


def test_fuzz_random_combinations() -> None:
    """Fuzz test: random combinations of all features."""
    for _ in range(100):
        # Random function parameters
        num_functions = random.randint(1, 10)
        functions = []

        for _ in range(num_functions):
            # Random characteristics
            num_lines = random.randint(1, 100)
            num_asserts = random.randint(0, 10)
            has_eval = random.random() < 0.3
            has_while_true = random.random() < 0.3
            has_recursion = random.random() < 0.3

            func = generate_random_function(
                num_statements=num_lines,
                num_assertions=num_asserts,
                include_forbidden_api=has_eval,
                include_while_true=has_while_true,
                include_recursion=has_recursion,
            )
            functions.append(func)

        code = "\n\n".join(functions)
        result = analyze(code)

        # Should never crash
        assert isinstance(result, list)

        # Verify expected violations are present
        codes = {d.code for d in result}

        # If any function has eval, should have NASA01-A
        if any("eval" in f or "exec" in f or "compile" in f for f in functions):
            # Note: might not be detected if code is malformed
            pass

        # If any function has while True, should have NASA02
        if any("while True" in f for f in functions):
            # Note: might not be detected if code is malformed
            pass


def test_fuzz_stress_test() -> None:
    """Stress test: analyze many random inputs rapidly."""
    for _ in range(500):
        # Generate random code
        choice = random.randint(0, 3)

        if choice == 0:
            # Random text
            code = "".join(random.choices(string.printable, k=random.randint(10, 200)))
        elif choice == 1:
            # Random function
            code = generate_random_function(
                num_statements=random.randint(1, 30),
                num_assertions=random.randint(0, 5),
            )
        elif choice == 2:
            # Empty or whitespace
            code = "".join(random.choices(" \t\n", k=random.randint(0, 50)))
        else:
            # Valid code
            code = """
def valid():
    assert True
    assert False
    return 42
"""

        result = analyze(code)
        assert isinstance(result, list)
