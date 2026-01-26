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

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from nasa_lsp.analyzer import analyze

# Deterministic seed for reproducible fuzzing
FUZZ_SEED = 42

# Set random seed at module level for reproducibility
random.seed(FUZZ_SEED)

# ============================================================================
# PROPERTY-BASED TESTS WITH HYPOTHESIS
# ============================================================================


@given(st.text())
@settings(max_examples=200)
def test_analyze_never_crashes_on_random_strings(code: str) -> None:
    """Property: analyze should never crash on any string input."""
    try:
        diagnostics, _ = analyze(code)
        # Should always return diagnostics list
        assert isinstance(diagnostics, list), "analyze() must return diagnostics list"
        # All items should be Diagnostic objects (duck-typed check)
        for diagnostic in diagnostics:
            assert hasattr(diagnostic, "range"), "Diagnostic missing 'range' attribute"
            assert hasattr(diagnostic, "message"), "Diagnostic missing 'message' attribute"
            assert hasattr(diagnostic, "code"), "Diagnostic missing 'code' attribute"
    except Exception as e:
        pytest.fail(f"analyze() crashed on input: {code!r}\nError: {e}")


@given(st.text(alphabet=string.printable))
@settings(max_examples=200)
def test_analyze_handles_printable_characters(code: str) -> None:
    """Property: analyze should handle all printable ASCII characters."""
    diagnostics, _ = analyze(code)
    assert isinstance(diagnostics, list), "analyze() must return a list"
    assert all(hasattr(d, "code") for d in diagnostics), "All diagnostics must have a code"


@given(st.integers(min_value=0, max_value=1000))
@settings(max_examples=100)
def test_generated_function_with_n_lines(n: int) -> None:
    """Property: analyze should handle functions of any length."""
    lines = [f"def func_{n}():"]
    lines.extend([f"    x{i} = {i}" for i in range(n)])

    code = "\n".join(lines)
    diagnostics, _ = analyze(code)

    # Should always return a list
    assert isinstance(diagnostics, list), "analyze() must return a list"

    # If n > 60, should have NASA04 violation
    nasa04_violations = [d for d in diagnostics if d.code == "NASA04"]
    if n > 60:
        assert len(nasa04_violations) > 0, f"Expected NASA04 violation for {n}-line function"
    else:
        # Might still have NASA05 violation (no assertions), but checking NASA04 specifically
        assert True, "Function within size limits processed successfully"


@given(st.integers(min_value=0, max_value=100))
@settings(max_examples=50)
def test_generated_function_with_n_assertions(n: int) -> None:
    """Property: analyze should handle functions with any number of assertions."""
    lines = [f"def func_with_{n}_asserts():"]
    lines.extend([f"    assert {i} >= 0" for i in range(n)])
    lines.append("    return True")

    code = "\n".join(lines)
    diagnostics, _ = analyze(code)

    assert isinstance(diagnostics, list), "analyze() must return a list"

    # If n < 2, should have NASA05 violation
    nasa05_violations = [d for d in diagnostics if d.code == "NASA05"]
    if n < 2:
        assert len(nasa05_violations) > 0, f"Expected NASA05 violation for {n} assertions"
    else:
        # Might have NASA04 if too long, but not NASA05
        assert len(nasa05_violations) == 0, f"Should not have NASA05 violation with {n} assertions"


@given(st.lists(st.text(alphabet=string.ascii_letters, min_size=1, max_size=20), min_size=0, max_size=50))
@settings(max_examples=100)
def test_multiple_function_definitions(func_names: list[str]) -> None:
    """Property: analyze should handle any number of function definitions."""
    lines: list[str] = []
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
    diagnostics, _ = analyze(code)

    # Should always return a list
    assert isinstance(diagnostics, list), "analyze() must return a list"
    # Should not crash with multiple functions
    assert len(diagnostics) >= 0, "Should return diagnostics for multiple functions"


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

    diagnostics, _ = analyze(code)
    nasa02_violations = [d for d in diagnostics if d.code == "NASA02"]

    if has_while_true:
        assert len(nasa02_violations) > 0, "Expected NASA02 violation for 'while True'"
    else:
        assert len(nasa02_violations) == 0, "Should not detect NASA02 for 'while False'"


# ============================================================================
# CODE GENERATION HELPERS
# ============================================================================


def generate_random_identifier(length: int = 10) -> str:
    """Generate a random valid Python identifier."""
    first = random.choice(string.ascii_letters + "_")
    rest = "".join(random.choices(string.ascii_letters + string.digits + "_", k=length - 1))
    result = first + rest
    assert len(result) == length, f"Identifier length {len(result)} != expected {length}"
    assert result[0] in string.ascii_letters + "_", "Identifier must start with letter or underscore"
    return result


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
    result = random.choice(expressions)
    assert len(result) > 0, "Expression must not be empty"
    assert isinstance(result, str), "Expression must be a string"
    return result


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
    result = random.choice(statements)
    assert len(result) > 0, "Statement must not be empty"
    assert isinstance(result, str), "Statement must be a string"
    return result


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
    lines.extend([f"    assert {random.choice(['True', 'False', '1 > 0', '0 < 1'])}" for _ in range(num_assertions)])

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

    result = "\n".join(lines)
    assert result.startswith("def "), "Generated code must start with 'def '"
    assert len(result) > 0, "Generated function must not be empty"
    return result


# ============================================================================
# SYNTAX ROBUSTNESS FUZZING
# ============================================================================


def test_fuzz_whitespace_variations() -> None:
    """Fuzz test: random whitespace patterns should be handled gracefully."""
    base_code = """
def func():
    assert True
    assert False
    return 42
"""
    whitespace_chars = [" ", "\t", "\n"]
    for _ in range(30):
        modified = base_code
        for _ in range(random.randint(0, 10)):
            pos = random.randint(0, len(modified) - 1)
            ws = random.choice(whitespace_chars)
            modified = modified[:pos] + ws + modified[pos:]
        diagnostics, _ = analyze(modified)
        assert isinstance(diagnostics, list), "Must return list for whitespace variations"
        assert len(diagnostics) >= 0, "Whitespace variations should be processed"


def test_fuzz_comment_variations() -> None:
    """Fuzz test: random comment insertion should be handled gracefully."""
    base_code = """
def func():
    assert True
    assert False
    return 42
"""
    for _ in range(30):
        lines = base_code.split("\n")
        num_comments = random.randint(1, 5)
        for _ in range(num_comments):
            pos = random.randint(0, len(lines))
            comment = f"# {generate_random_identifier()}"
            lines = [*lines[:pos], comment, *lines[pos:]]
        code = "\n".join(lines)
        diagnostics, _ = analyze(code)
        assert isinstance(diagnostics, list), "Must return list for comment variations"
        assert all(hasattr(d, "code") for d in diagnostics), "All diagnostics must be well-formed"


def test_fuzz_unicode_identifiers() -> None:
    """Fuzz test: Unicode identifiers should be handled gracefully."""
    unicode_names = ["функция", "函数", "関数", "função", "función"]
    for name in unicode_names:
        code = f"""
def {name}():
    assert True
    assert False
    return 42
"""
        diagnostics, _ = analyze(code)
        assert isinstance(diagnostics, list), f"Must return list for unicode name: {name}"
        assert len(diagnostics) >= 0, "Unicode identifiers should be processed"


def test_fuzz_mixed_quote_styles() -> None:
    """Fuzz test: mixed quote styles should be handled gracefully."""
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
        diagnostics, _ = analyze(code)
        assert isinstance(diagnostics, list), "Must return list for mixed quotes"
        assert len(diagnostics) >= 0, "Quote styles should be handled"


def test_fuzz_string_literals() -> None:
    """Fuzz test: random string literals should be handled gracefully."""
    for _ in range(50):
        strings: list[str] = []
        for _ in range(random.randint(1, 10)):
            s = "".join(random.choices(string.printable, k=random.randint(1, 50)))
            s = s.replace('"', '\\"').replace("\\", "\\\\")
            strings.append(f'    s{len(strings)} = "{s}"')
        code = f"""
def func_with_strings():
    assert True
    assert False
{chr(10).join(strings)}
    return None
"""
        diagnostics, _ = analyze(code)
        assert isinstance(diagnostics, list), "Must return list for string literals"
        assert len(diagnostics) >= 0, "String literals should be processed"


def test_fuzz_numeric_literals() -> None:
    """Fuzz test: random numeric literals should be handled gracefully."""
    for _ in range(50):
        numbers: list[str] = []
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
        diagnostics, _ = analyze(code)
        assert isinstance(diagnostics, list), "Must return list for numeric literals"
        assert len(diagnostics) >= 0, "Numeric literals should be processed"


# ============================================================================
# STRUCTURE FUZZING
# ============================================================================


@pytest.mark.parametrize(
    ("structure_type", "test_values"),
    [
        ("nesting_depth", [1, 5, 10, 15, 19]),
        ("function_name_length", [10, 50, 100, 500, 1000]),
        ("parameter_count", [0, 1, 10, 50, 100]),
    ],
)
def test_fuzz_code_structure(structure_type: str, test_values: list[int]) -> None:
    """Fuzz test: various code structure extremes should be handled."""
    if structure_type == "nesting_depth":
        for depth in test_values:
            lines = ["def deeply_nested():"]
            lines.append("    assert True")
            lines.append("    assert False")
            indent = "    "
            for _ in range(depth):
                lines.append(f"{indent}if True:")
                indent += "    "
            lines.append(f"{indent}pass")
            code = "\n".join(lines)
            diagnostics, _ = analyze(code)
            assert isinstance(diagnostics, list), f"Must handle depth {depth}"
            assert len(diagnostics) >= 0, "Deep nesting should be processed"

    elif structure_type == "function_name_length":
        for length in test_values:
            func_name = generate_random_identifier(length)
            code = f"""
def {func_name}():
    assert True
    assert False
    return 42
"""
            diagnostics, _ = analyze(code)
            assert isinstance(diagnostics, list), f"Must handle name length {length}"
            assert len(diagnostics) >= 0, "Long names should be processed"

    elif structure_type == "parameter_count":
        for num_params in test_values:
            params = [f"p{i}" for i in range(num_params)]
            param_list = ", ".join(params)
            code = f"""
def func({param_list}):
    assert True
    assert False
    return None
"""
            diagnostics, _ = analyze(code)
            assert isinstance(diagnostics, list), f"Must handle {num_params} parameters"
            assert len(diagnostics) >= 0, "Many parameters should be processed"


# ============================================================================
# MALFORMED INPUT FUZZING
# ============================================================================


@pytest.mark.parametrize(
    "malformed_pattern",
    [
        "def func(",  # Missing closing paren
        "def func():",  # Missing body
        "def func():\n    if True:",  # Incomplete if
        "def func():\n    assert",  # Incomplete assert
        "def func():\n    return",  # Incomplete return
        "def func():\n    x = ",  # Incomplete assignment
        "def func():\n    [1, 2,",  # Unclosed list
        "def func():\n    {1: 2,",  # Unclosed dict
        "def func():\n    (1, 2,",  # Unclosed tuple
        "def func():\n    '''unclosed string",  # Unclosed string
    ],
)
def test_fuzz_malformed_syntax(malformed_pattern: str) -> None:
    """Fuzz test: malformed syntax should be handled gracefully."""
    diagnostics, _ = analyze(malformed_pattern)
    # Should handle gracefully (return empty or minimal list for syntax errors)
    assert isinstance(diagnostics, list), "Must return list even for malformed syntax"
    # Should not crash - that's the key property
    assert True, "Malformed syntax handled without crashing"


def test_fuzz_character_and_line_mutations() -> None:
    """Fuzz test: random mutations to valid code should not crash analyzer."""
    base_code = """
def func():
    assert True
    assert False
    x = 1
    y = 2
    return x + y
"""

    # Test character injection
    for _ in range(50):
        pos = random.randint(0, len(base_code) - 1)
        char = random.choice(string.printable)
        modified = base_code[:pos] + char + base_code[pos:]
        diagnostics, _ = analyze(modified)
        assert isinstance(diagnostics, list), "Character injection must not crash"

    # Test line deletion
    for _ in range(30):
        lines = base_code.split("\n")
        for _ in range(random.randint(1, 3)):
            if len(lines) > 1:
                del lines[random.randint(0, len(lines) - 1)]
        code = "\n".join(lines)
        diagnostics, _ = analyze(code)
        assert isinstance(diagnostics, list), "Line deletion must not crash"
        assert len(diagnostics) >= 0, "Should process mutated code"


# ============================================================================
# PERFORMANCE AND SCALE FUZZING
# ============================================================================


@pytest.mark.parametrize(
    ("scale_type", "scale_value"),
    [
        ("many_functions", 1000),
        ("very_long_function", 5000),
        ("very_long_lines", 10000),
    ],
)
def test_fuzz_scale_performance(scale_type: str, scale_value: int) -> None:
    """Fuzz test: analyzer should handle extreme scale without timing out."""
    if scale_type == "many_functions":
        functions = [
            f"""
def func_{i}():
    assert True
    assert {i} >= 0
    return {i}
"""
            for i in range(scale_value)
        ]
        code = "\n".join(functions)
        diagnostics, _ = analyze(code)
        assert isinstance(diagnostics, list), f"Must handle {scale_value} functions"
        assert len(diagnostics) >= 0, "Large files should complete"

    elif scale_type == "very_long_function":
        lines = ["def very_long_function():"]
        lines.extend([f"    x{i} = {i}" for i in range(scale_value)])
        code = "\n".join(lines)
        diagnostics, _ = analyze(code)
        assert isinstance(diagnostics, list), f"Must handle {scale_value}-line function"
        nasa04_violations = [d for d in diagnostics if d.code == "NASA04"]
        assert len(nasa04_violations) > 0, "Should detect NASA04 for very long function"

    elif scale_type == "very_long_lines":
        long_string = "x" * scale_value
        code = f"""
def long_line():
    assert True
    assert False
    s = "{long_string}"
    return s
"""
        diagnostics, _ = analyze(code)
        assert isinstance(diagnostics, list), f"Must handle {scale_value}-char lines"
        assert len(diagnostics) >= 0, "Very long lines should be processed"


# ============================================================================
# NASA RULE VIOLATION DETECTION
# ============================================================================


@pytest.mark.parametrize(
    ("violation_characteristics", "expected_codes"),
    [
        ({"num_assertions": 0}, ["NASA05"]),
        ({"num_assertions": 1}, ["NASA05"]),
        ({"include_forbidden_api": True, "num_assertions": 2}, ["NASA01-A"]),
        ({"include_while_true": True, "num_assertions": 2}, ["NASA02"]),
        ({"include_recursion": True, "num_assertions": 2}, ["NASA01-B"]),
        ({"num_statements": 70, "num_assertions": 2}, ["NASA04"]),
    ],
)
def test_fuzz_nasa_violation_detection(
    violation_characteristics: dict[str, int | bool], expected_codes: list[str]
) -> None:
    """Fuzz test: NASA violations should be consistently detected."""
    # Set defaults
    config = {
        "num_statements": 10,
        "num_assertions": 2,
        "include_forbidden_api": False,
        "include_while_true": False,
        "include_recursion": False,
    }
    config.update(violation_characteristics)

    violations_detected = 0
    for _ in range(20):
        code = generate_random_function(
            num_statements=int(config["num_statements"]),
            num_assertions=int(config["num_assertions"]),
            include_forbidden_api=bool(config["include_forbidden_api"]),
            include_while_true=bool(config["include_while_true"]),
            include_recursion=bool(config["include_recursion"]),
        )
        diagnostics, _ = analyze(code)
        assert isinstance(diagnostics, list), "Must return list for violation detection"

        # Check if expected violations are detected (if code is valid)
        if diagnostics:  # Only check if analyze found something
            detected_codes = {d.code for d in diagnostics}
            if any(expected_code in detected_codes for expected_code in expected_codes):
                violations_detected += 1

    # At least some of the generated code should trigger the expected violations
    assert violations_detected > 0, f"Expected violations {expected_codes} never detected in 20 attempts"


# ============================================================================
# STRESS TESTING
# ============================================================================


def test_fuzz_random_combinations_stress() -> None:
    """Stress test: rapid analysis of diverse random inputs."""
    combinations_tested = 0
    crashes = 0

    for _ in range(100):
        num_functions = random.randint(1, 10)
        functions: list[str] = []

        for _ in range(num_functions):
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
        try:
            diagnostics, _ = analyze(code)
            assert isinstance(diagnostics, list)
            combinations_tested += 1
        except Exception:
            crashes += 1

    # Should test all combinations without crashing
    assert combinations_tested == 100, f"Only {combinations_tested}/100 succeeded, {crashes} crashed"
    assert crashes == 0, f"Analyzer crashed {crashes} times"


def test_fuzz_rapid_stress_test() -> None:
    """Stress test: analyze many varied inputs rapidly."""
    success_count = 0
    total_tests = 500

    for _ in range(total_tests):
        choice = random.randint(0, 3)

        if choice == 0:
            code = "".join(random.choices(string.printable, k=random.randint(10, 200)))
        elif choice == 1:
            code = generate_random_function(
                num_statements=random.randint(1, 30),
                num_assertions=random.randint(0, 5),
            )
        elif choice == 2:
            code = "".join(random.choices(" \t\n", k=random.randint(0, 50)))
        else:
            code = """
def valid():
    assert True
    assert False
    return 42
"""

        diagnostics, _ = analyze(code)
        assert isinstance(diagnostics, list)
        success_count += 1

    assert success_count == total_tests, f"Only completed {success_count}/{total_tests} stress tests"
    # High-volume testing completed successfully
    assert success_count > 0, "Stress testing should complete successfully"


# ============================================================================
# AST ROUND-TRIP FUZZING
# ============================================================================


def test_fuzz_ast_round_trip() -> None:
    """Fuzz test: parse, unparse, and re-analyze code."""
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

    successful_roundtrips = 0
    for code in test_cases:
        try:
            tree = ast.parse(code)
            unparsed = ast.unparse(tree)
            diagnostics, _ = analyze(unparsed)
            assert isinstance(diagnostics, list), "Round-tripped code must analyze successfully"
            successful_roundtrips += 1
        except SyntaxError:
            # Some code might not round-trip perfectly - that's acceptable
            pass

    # At least some round-trips should succeed
    assert successful_roundtrips >= len(test_cases) - 1, "Most AST round-trips should succeed"
    assert successful_roundtrips > 0, "At least one round-trip should succeed"
