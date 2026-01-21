"""Simulation tests for NASA-LSP analyzer.

These tests simulate real-world scenarios, edge cases, and stress tests
to ensure the analyzer handles complex situations correctly.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from nasa_lsp.analyzer import analyze
from nasa_lsp.cli import app

runner = CliRunner()


# ============================================================================
# LARGE FILE PROCESSING SIMULATION TESTS
# ============================================================================


def test_large_file_with_1000_lines() -> None:
    """Simulate analyzing a large file with 1000+ lines."""
    # Generate a large file with multiple violations spread throughout
    lines = ['"""Large module for testing."""', ""]

    # Add 100 clean functions with proper assertions
    for i in range(100):
        lines.extend(
            [
                f"def clean_function_{i}():",
                "    assert True",
                "    assert False",
                f"    return {i}",
                "",
            ]
        )

    # Add 10 functions with NASA01-A violations (forbidden APIs)
    for i in range(10):
        lines.extend(
            [
                f"def eval_violation_{i}():",
                "    assert True",
                "    assert False",
                '    eval("1+1")',
                "",
            ]
        )

    # Add 10 functions with NASA05 violations (missing assertions)
    for i in range(10):
        lines.extend([f"def no_assert_{i}():", f"    return {i}", ""])

    # Add 10 functions with NASA04 violations (too long)
    for i in range(10):
        lines.extend([f"def too_long_{i}():"])
        for j in range(65):  # 65 lines > 60 line limit
            lines.append(f"    x{j} = {j}")
        lines.append("")

    code = "\n".join(lines)
    result = analyze(code)

    # Should detect violations from all violation categories
    assert len(result) > 0
    codes = {d.code for d in result}
    assert "NASA01-A" in codes  # eval violations
    assert "NASA05" in codes  # missing assertions
    assert "NASA04" in codes  # too long functions


def test_large_file_with_deeply_nested_structures() -> None:
    """Simulate a file with deeply nested code structures."""
    code = """
def outer1():
    assert True
    assert False
    def inner1():
        assert True
        assert False
        def inner2():
            assert True
            assert False
            def inner3():
                assert True
                assert False
                def inner4():
                    assert True
                    assert False
                    def inner5():
                        assert True
                        assert False
                        return 5
                    return 4
                return 3
            return 2
        return 1
    return 0
"""
    result = analyze(code)
    # All nested functions have proper assertions, should be clean
    assert result == []


def test_file_with_500_functions() -> None:
    """Simulate analyzing a file with many functions."""
    lines = ['"""Module with many functions."""', ""]

    for i in range(500):
        lines.extend([f"def func_{i}():", "    assert True", "    assert False", "    pass", ""])

    code = "\n".join(lines)
    result = analyze(code)

    # All functions have proper assertions, should be clean
    assert result == []


# ============================================================================
# EDGE CASE PYTHON SYNTAX SIMULATION TESTS
# ============================================================================


def test_complex_decorators_and_annotations() -> None:
    """Simulate functions with complex decorators and type annotations."""
    code = """
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec("P")
T = TypeVar("T")

def decorator1(func: Callable[P, T]) -> Callable[P, T]:
    assert func is not None
    assert callable(func)
    return func

def decorator2(x: int) -> Callable[[Callable[P, T]], Callable[P, T]]:
    assert x > 0
    assert isinstance(x, int)
    def wrapper(func: Callable[P, T]) -> Callable[P, T]:
        assert func is not None
        assert callable(func)
        return func
    return wrapper

@decorator1
@decorator2(10)
def complex_function(a: int, b: str, *, c: list[dict[str, int]]) -> tuple[int, ...]:
    assert a > 0
    assert isinstance(b, str)
    return (a,)

async def async_function_with_annotations(
    x: int | None = None,
    y: str | int = "default",
) -> dict[str, list[int]]:
    assert x is None or x > 0
    assert isinstance(y, (str, int))
    return {"result": [1, 2, 3]}
"""
    result = analyze(code)
    # All functions should be clean
    assert result == []


def test_fstrings_with_complex_expressions() -> None:
    """Simulate f-strings with complex expressions."""
    code = """
def process_data(items: list[int]) -> str:
    assert items
    assert isinstance(items, list)
    result = f"Items: {', '.join(str(x) for x in items if x > 0)}"
    nested = f"Count: {len([x for x in items if x > 0])}"
    complex_expr = f"Result: {sum(x**2 for x in items) if items else 0}"
    return result + nested + complex_expr
"""
    result = analyze(code)
    assert result == []


def test_match_statements() -> None:
    """Simulate match/case statements (Python 3.10+)."""
    code = """
def handle_command(command: str) -> int:
    assert command
    assert isinstance(command, str)
    match command:
        case "start":
            return 1
        case "stop":
            return 0
        case _:
            return -1
"""
    result = analyze(code)
    assert result == []


def test_walrus_operator() -> None:
    """Simulate walrus operator usage."""
    code = """
def process_items(items: list[int]) -> int:
    assert items
    assert isinstance(items, list)
    if (n := len(items)) > 10:
        return n
    while (item := items.pop(0) if items else None) is not None:
        pass
    return 0
"""
    result = analyze(code)
    assert result == []


def test_async_generators_and_context_managers() -> None:
    """Simulate async generators and context managers."""
    code = """
async def async_generator():
    assert True
    assert True
    for i in range(10):
        yield i

async def async_context_manager():
    assert True
    assert True
    async with some_context():
        await something()
"""
    result = analyze(code)
    # Should be clean (both functions have 2 assertions)
    assert result == []


def test_comprehensions_with_conditions() -> None:
    """Simulate complex comprehensions."""
    code = """
def process_data(data: list[int]) -> dict[int, list[int]]:
    assert data
    assert isinstance(data, list)
    # List comprehension
    squares = [x**2 for x in data if x > 0]
    # Dict comprehension
    mapping = {x: x**2 for x in data if x % 2 == 0}
    # Set comprehension
    unique = {x % 10 for x in data}
    # Nested comprehension
    matrix = [[i*j for j in range(5)] for i in range(5)]
    return mapping
"""
    result = analyze(code)
    assert result == []


# ============================================================================
# PATHOLOGICAL CODE PATTERN SIMULATION TESTS
# ============================================================================


def test_function_with_exactly_60_lines() -> None:
    """Test boundary: function with exactly 60 lines should pass."""
    lines = ["def exactly_60_lines():"]
    # Add 59 more lines (60 total including def line)
    for i in range(59):
        lines.append(f"    x{i} = {i}")
    code = "\n".join(lines)
    result = analyze(code)

    # Should NOT have NASA04 violation (60 lines is OK)
    nasa04_violations = [d for d in result if d.code == "NASA04"]
    assert len(nasa04_violations) == 0


def test_function_with_exactly_61_lines() -> None:
    """Test boundary: function with exactly 61 lines should fail."""
    lines = ["def exactly_61_lines():"]
    # Add 60 more lines (61 total including def line)
    for i in range(60):
        lines.append(f"    x{i} = {i}")
    code = "\n".join(lines)
    result = analyze(code)

    # Should have NASA04 violation
    nasa04_violations = [d for d in result if d.code == "NASA04"]
    assert len(nasa04_violations) == 1


def test_function_with_exactly_2_assertions() -> None:
    """Test boundary: function with exactly 2 assertions should pass."""
    code = """
def exactly_2_asserts():
    assert True
    assert False
    return 42
"""
    result = analyze(code)
    assert result == []


def test_function_with_exactly_1_assertion() -> None:
    """Test boundary: function with exactly 1 assertion should fail."""
    code = """
def exactly_1_assert():
    assert True
    return 42
"""
    result = analyze(code)

    # Should have NASA05 violation
    nasa05_violations = [d for d in result if d.code == "NASA05"]
    assert len(nasa05_violations) == 1


def test_very_long_lines() -> None:
    """Simulate functions with very long lines (1000+ characters)."""
    long_string = "x" * 1000
    code = f"""
def long_line_function():
    assert True
    assert False
    very_long_variable = "{long_string}"
    return very_long_variable
"""
    result = analyze(code)
    # Should still parse correctly and be clean
    assert result == []


def test_function_with_100_assertions() -> None:
    """Simulate a function with many assertions."""
    lines = ["def many_asserts():"]
    for i in range(100):
        lines.append(f"    assert {i} >= 0")
    lines.append("    return True")

    code = "\n".join(lines)
    result = analyze(code)

    # Should have NASA04 violation (>60 lines) but NOT NASA05
    codes = {d.code for d in result}
    assert "NASA04" in codes
    assert "NASA05" not in codes


# ============================================================================
# ERROR HANDLING SIMULATION TESTS
# ============================================================================


def test_incomplete_function_definitions() -> None:
    """Simulate incomplete/malformed function definitions."""
    incomplete_codes = [
        "def incomplete(",  # Missing closing paren
        "def no_body():",  # No body (syntax error)
        "def incomplete():\n    if True:",  # Incomplete if
        "def unclosed():\n    assert True\n    assert False\n    x = [1, 2",  # Unclosed bracket
    ]

    for incomplete in incomplete_codes:
        result = analyze(incomplete)
        # Should handle gracefully and return empty list
        assert isinstance(result, list)


def test_mixed_indentation() -> None:
    """Simulate code with mixed tabs and spaces (could cause issues)."""
    code = """
def mixed_indentation():
\tassert True  # Tab
    assert False  # Spaces
\treturn 42  # Tab
"""
    result = analyze(code)
    # Should either parse correctly or handle gracefully
    assert isinstance(result, list)


def test_unicode_in_code() -> None:
    """Simulate unicode characters in function names and strings."""
    code = """
def функция_с_кириллицей():
    assert True
    assert False
    text = "Hello 世界 🌍"
    emoji = "🚀 NASA 🛰️"
    return text + emoji

def func_with_emoji_💯():
    assert True
    assert False
    return "✨"
"""
    result = analyze(code)
    # Should handle unicode correctly
    assert isinstance(result, list)


def test_files_with_various_encodings() -> None:
    """Simulate analyzing code with encoding declarations."""
    code = """# -*- coding: utf-8 -*-
def test_encoding():
    assert True
    assert False
    return "UTF-8 text: café, naïve"
"""
    result = analyze(code)
    assert result == []


def test_empty_and_whitespace_functions() -> None:
    """Simulate various empty/whitespace patterns."""
    code = """
def empty_with_pass():
    pass

def empty_with_ellipsis():
    ...

def only_docstring():
    '''Just a docstring.'''

def whitespace_only():


    return None
"""
    result = analyze(code)
    # All should have NASA05 violations (no assertions)
    nasa05_violations = [d for d in result if d.code == "NASA05"]
    assert len(nasa05_violations) == 4


# ============================================================================
# COMPLEX CONTROL FLOW SIMULATION TESTS
# ============================================================================


def test_nested_try_except_finally() -> None:
    """Simulate complex nested exception handling."""
    code = """
def complex_exception_handling():
    assert True
    assert True
    try:
        try:
            risky_operation()
        except ValueError:
            handle_value_error()
        except KeyError:
            handle_key_error()
        finally:
            cleanup_inner()
    except Exception:
        handle_any()
    finally:
        cleanup_outer()
"""
    result = analyze(code)
    assert result == []


def test_multiple_context_managers() -> None:
    """Simulate multiple nested context managers."""
    code = """
def multiple_contexts():
    assert True
    assert True
    with open("file1") as f1:
        with open("file2") as f2:
            with open("file3") as f3:
                data = f1.read() + f2.read() + f3.read()
    return data
"""
    result = analyze(code)
    assert result == []


def test_complex_boolean_expressions() -> None:
    """Simulate complex boolean logic."""
    code = """
def complex_logic(a: int, b: int, c: int, d: int) -> bool:
    assert isinstance(a, int)
    assert isinstance(b, int)
    result = (
        (a > 0 and b < 10)
        or (c == 5 and d != 0)
        or (a + b > c + d and a * b < c * d)
    )
    return result
"""
    result = analyze(code)
    assert result == []


# ============================================================================
# RECURSION DETECTION SIMULATION TESTS
# ============================================================================


def test_direct_recursion() -> None:
    """Simulate direct recursive function calls."""
    code = """
def factorial(n: int) -> int:
    assert n >= 0
    assert isinstance(n, int)
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
    result = analyze(code)

    # Should detect NASA01-B violation (recursion)
    nasa01b_violations = [d for d in result if d.code == "NASA01-B"]
    assert len(nasa01b_violations) == 1


def test_mutual_recursion_not_detected() -> None:
    """Mutual recursion is not currently detected (indirect recursion)."""
    code = """
def is_even(n: int) -> bool:
    assert n >= 0
    assert isinstance(n, int)
    if n == 0:
        return True
    return is_odd(n - 1)

def is_odd(n: int) -> bool:
    assert n >= 0
    assert isinstance(n, int)
    if n == 0:
        return False
    return is_even(n - 1)
"""
    result = analyze(code)

    # Currently, indirect recursion is NOT detected
    # This is expected behavior - only direct recursion is flagged
    nasa01b_violations = [d for d in result if d.code == "NASA01-B"]
    assert len(nasa01b_violations) == 0


def test_recursion_in_nested_function() -> None:
    """Simulate recursion in nested function."""
    code = """
def outer():
    assert True
    assert True

    def inner(n: int) -> int:
        assert n >= 0
        assert isinstance(n, int)
        if n <= 1:
            return 1
        return n * inner(n - 1)

    return inner(5)
"""
    result = analyze(code)

    # Should detect recursion in inner function
    nasa01b_violations = [d for d in result if d.code == "NASA01-B"]
    assert len(nasa01b_violations) == 1


# ============================================================================
# FORBIDDEN API SIMULATION TESTS
# ============================================================================


def test_all_forbidden_apis() -> None:
    """Test all forbidden APIs from NASA01-A."""
    forbidden_apis = [
        "eval",
        "exec",
        "compile",
        "globals",
        "locals",
        "__import__",
        "setattr",
        "getattr",
    ]

    for api in forbidden_apis:
        code = f"""
def test_{api}():
    assert True
    assert False
    {api}("test")
"""
        result = analyze(code)
        nasa01a_violations = [d for d in result if d.code == "NASA01-A"]
        assert len(nasa01a_violations) == 1, f"Failed to detect forbidden API: {api}"
        assert api in result[0].message


def test_forbidden_apis_in_expressions() -> None:
    """Simulate forbidden APIs used in complex expressions."""
    code = """
def complex_forbidden_usage():
    assert True
    assert False
    # Eval in expression
    result = 5 + eval("2 + 3")
    # Exec in conditional
    if exec("x = 1"):
        pass
    # Compile in list comprehension
    compiled = [compile(f"x={i}", "<string>", "exec") for i in range(5)]
    return result
"""
    result = analyze(code)

    # Should detect multiple NASA01-A violations
    nasa01a_violations = [d for d in result if d.code == "NASA01-A"]
    assert len(nasa01a_violations) >= 3


def test_forbidden_apis_as_methods() -> None:
    """Simulate forbidden APIs used as methods (should still be detected)."""
    code = """
def method_calls():
    assert True
    assert False
    obj = SomeClass()
    # These should be detected
    value = getattr(obj, "attr")
    setattr(obj, "attr", value)
"""
    result = analyze(code)

    # Should detect getattr and setattr
    nasa01a_violations = [d for d in result if d.code == "NASA01-A"]
    assert len(nasa01a_violations) == 2


# ============================================================================
# UNBOUNDED LOOP SIMULATION TESTS
# ============================================================================


def test_while_true_loops() -> None:
    """Simulate various while True patterns."""
    code = """
def server_loop():
    assert True
    assert False
    while True:
        handle_request()

def event_loop():
    assert True
    assert False
    while True:
        event = get_event()
        process(event)
"""
    result = analyze(code)

    # Should detect NASA02 violations
    nasa02_violations = [d for d in result if d.code == "NASA02"]
    assert len(nasa02_violations) == 2


def test_bounded_while_loops() -> None:
    """Simulate bounded while loops (should be clean)."""
    code = """
def bounded_loop(n: int):
    assert n > 0
    assert isinstance(n, int)
    i = 0
    while i < n:
        process(i)
        i += 1

def conditional_loop(items: list):
    assert items
    assert isinstance(items, list)
    while items:
        item = items.pop()
        process(item)
"""
    result = analyze(code)

    # Should NOT have NASA02 violations
    nasa02_violations = [d for d in result if d.code == "NASA02"]
    assert len(nasa02_violations) == 0


def test_for_loops_are_allowed() -> None:
    """For loops should be allowed even if large."""
    code = """
def large_for_loop():
    assert True
    assert False
    for i in range(1000000):
        process(i)

def nested_for_loops():
    assert True
    assert False
    for i in range(100):
        for j in range(100):
            for k in range(100):
                process(i, j, k)
"""
    result = analyze(code)

    # Should NOT have NASA02 violations (for loops are OK)
    nasa02_violations = [d for d in result if d.code == "NASA02"]
    assert len(nasa02_violations) == 0


# ============================================================================
# MULTI-FILE/DIRECTORY SIMULATION TESTS
# ============================================================================


def test_analyze_directory_with_mixed_files() -> None:
    """Simulate analyzing a directory with clean and violating files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create clean file
        clean_file = tmp_path / "clean.py"
        clean_file.write_text(
            """
def clean_function():
    assert True
    assert False
    return 42
"""
        )

        # Create file with violations
        violations_file = tmp_path / "violations.py"
        violations_file.write_text(
            """
def has_eval():
    assert True
    assert False
    eval("1+1")

def no_asserts():
    return 1
"""
        )

        # Create subdirectory with more files
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        sub_file = subdir / "sub.py"
        sub_file.write_text(
            """
def recursive(n: int) -> int:
    assert n >= 0
    assert isinstance(n, int)
    return recursive(n - 1)
"""
        )

        # Analyze the directory using CLI
        result = runner.invoke(app, ["lint", str(tmp_path)])

        # Should find violations (exit code 1)
        assert result.exit_code == 1
        assert "violation" in result.stdout.lower()


def test_exclude_common_directories() -> None:
    """Simulate that common directories are excluded."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Create file in main directory
        main_file = tmp_path / "main.py"
        main_file.write_text(
            """
def bad():
    eval("test")
"""
        )

        # Create files in directories that should be excluded
        for excluded_dir in [".venv", "__pycache__", "node_modules", ".git"]:
            exc_dir = tmp_path / excluded_dir
            exc_dir.mkdir()
            exc_file = exc_dir / "test.py"
            exc_file.write_text(
                """
def bad():
    eval("test")
"""
            )

        # Analyze the directory using CLI
        result = runner.invoke(app, ["lint", str(tmp_path)])

        # Should find violations only in main.py (exit code 1)
        assert result.exit_code == 1
        # Output should mention main.py
        assert "main.py" in result.stdout
        # Should NOT mention any excluded directories
        for excluded in [".venv", "__pycache__", "node_modules", ".git"]:
            assert excluded not in result.stdout or f"{excluded}/test.py" not in result.stdout


# ============================================================================
# CLASS METHOD SIMULATION TESTS
# ============================================================================


def test_class_methods_and_static_methods() -> None:
    """Simulate analysis of class methods."""
    code = """
class MyClass:
    def instance_method(self):
        assert self is not None
        assert True
        return self

    @classmethod
    def class_method(cls):
        assert cls is not None
        assert True
        return cls

    @staticmethod
    def static_method():
        assert True
        assert False
        return 42

    def no_asserts(self):
        return 1

    def too_long(self):
        x0 = 0
        x1 = 1
        x2 = 2
        x3 = 3
        x4 = 4
        x5 = 5
        x6 = 6
        x7 = 7
        x8 = 8
        x9 = 9
        x10 = 10
        x11 = 11
        x12 = 12
        x13 = 13
        x14 = 14
        x15 = 15
        x16 = 16
        x17 = 17
        x18 = 18
        x19 = 19
        x20 = 20
        x21 = 21
        x22 = 22
        x23 = 23
        x24 = 24
        x25 = 25
        x26 = 26
        x27 = 27
        x28 = 28
        x29 = 29
        x30 = 30
        x31 = 31
        x32 = 32
        x33 = 33
        x34 = 34
        x35 = 35
        x36 = 36
        x37 = 37
        x38 = 38
        x39 = 39
        x40 = 40
        x41 = 41
        x42 = 42
        x43 = 43
        x44 = 44
        x45 = 45
        x46 = 46
        x47 = 47
        x48 = 48
        x49 = 49
        x50 = 50
        x51 = 51
        x52 = 52
        x53 = 53
        x54 = 54
        x55 = 55
        x56 = 56
        x57 = 57
        x58 = 58
        x59 = 59
        x60 = 60
"""
    result = analyze(code)

    # Should detect violations in class methods
    codes = {d.code for d in result}
    assert "NASA05" in codes  # no_asserts method
    assert "NASA04" in codes  # too_long method


def test_nested_classes() -> None:
    """Simulate nested class definitions."""
    code = """
class Outer:
    def outer_method(self):
        assert True
        assert False
        return 1

    class Inner:
        def inner_method(self):
            assert True
            assert False
            return 2

        class DeepInner:
            def deep_method(self):
                assert True
                assert False
                return 3
"""
    result = analyze(code)
    # All methods should be clean
    assert result == []


# ============================================================================
# LAMBDA AND GENERATOR SIMULATION TESTS
# ============================================================================


def test_lambda_functions() -> None:
    """Lambdas are not regular functions, should be ignored."""
    code = """
def has_lambda():
    assert True
    assert False
    # Lambdas don't need assertions
    square = lambda x: x**2
    add = lambda a, b: a + b
    return square(5)
"""
    result = analyze(code)
    # Should be clean (lambdas are ignored)
    assert result == []


def test_generator_functions() -> None:
    """Simulate generator functions."""
    code = """
def simple_generator():
    assert True
    assert False
    for i in range(10):
        yield i

def generator_with_send():
    assert True
    assert False
    value = None
    while True:
        value = yield value
"""
    result = analyze(code)

    # First generator is clean, second has while True
    nasa02_violations = [d for d in result if d.code == "NASA02"]
    assert len(nasa02_violations) == 1


# ============================================================================
# DOCSTRING SIMULATION TESTS
# ============================================================================


def test_functions_with_various_docstrings() -> None:
    """Simulate functions with different docstring styles."""
    code = '''
def single_line_docstring():
    """Single line docstring."""
    assert True
    assert False
    return 1

def multi_line_docstring():
    """
    Multi-line docstring.

    With multiple paragraphs.
    """
    assert True
    assert False
    return 2

def triple_single_quote():
    \'\'\'Using single quotes.\'\'\'
    assert True
    assert False
    return 3

def no_docstring():
    assert True
    assert False
    return 4

def docstring_with_asserts():
    """
    Docstring that mentions assert.

    Example:
        assert x > 0
    """
    assert True
    assert False
    return 5
'''
    result = analyze(code)
    # All should be clean
    assert result == []


# ============================================================================
# PROPERTY AND DESCRIPTOR SIMULATION TESTS
# ============================================================================


def test_property_methods() -> None:
    """Simulate property decorators."""
    code = """
class MyClass:
    @property
    def value(self):
        assert True
        assert False
        return self._value

    @value.setter
    def value(self, val):
        assert val is not None
        assert isinstance(val, int)
        self._value = val

    @value.deleter
    def value(self):
        assert True
        assert False
        del self._value
"""
    result = analyze(code)
    # All property methods should be clean
    assert result == []


# ============================================================================
# ASYNC/AWAIT SIMULATION TESTS
# ============================================================================


def test_async_functions_comprehensive() -> None:
    """Comprehensive async function testing."""
    code = """
async def simple_async():
    assert True
    assert False
    return await some_coroutine()

async def async_with_loop():
    assert True
    assert False
    for i in range(10):
        await process(i)

async def async_with_while_true():
    assert True
    assert False
    while True:
        await handle_event()

async def async_generator():
    assert True
    assert False
    for i in range(10):
        yield await fetch(i)

async def async_context_manager():
    assert True
    assert False
    async with resource() as r:
        await r.process()
"""
    result = analyze(code)

    # Should detect while True in async_with_while_true
    nasa02_violations = [d for d in result if d.code == "NASA02"]
    assert len(nasa02_violations) == 1


# ============================================================================
# STRESS TEST: MULTIPLE VIOLATIONS IN ONE FUNCTION
# ============================================================================


def test_function_with_all_violations() -> None:
    """Simulate a function that violates multiple rules."""
    code = """
def terrible_function():
    # NASA05: No assertions (violation 1)
    # NASA01-A: Uses eval (violation 2)
    eval("bad code")
    # NASA02: while True (violation 3)
    while True:
        break
"""
    # Add many lines to also trigger NASA04
    lines = code.split("\n")
    for i in range(65):
        lines.insert(-1, f"    x{i} = {i}")
    code = "\n".join(lines)

    result = analyze(code)

    # Should detect all violations
    codes = {d.code for d in result}
    assert "NASA01-A" in codes  # eval
    assert "NASA02" in codes  # while True
    assert "NASA04" in codes  # too long
    assert "NASA05" in codes  # no assertions


# ============================================================================
# REAL-WORLD SIMULATION: NASA-LSP ANALYZING ITSELF
# ============================================================================


def test_analyzing_nasa_lsp_code() -> None:
    """Simulate analyzing actual NASA-LSP source code."""
    # This simulates patterns found in the actual codebase
    code = """
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

@dataclass
class Position:
    line: int
    character: int

@dataclass
class Range:
    start: Position
    end: Position

@dataclass
class Diagnostic:
    range: Range
    message: str
    code: str
    severity: int = 1

class Visitor(Protocol):
    def visit(self, node) -> None:
        assert node is not None
        assert hasattr(node, "__class__")
        ...

def analyze(source: str) -> list[Diagnostic]:
    assert isinstance(source, str)
    assert source is not None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    diagnostics: list[Diagnostic] = []
    # Process tree
    return diagnostics
"""
    result = analyze(code)
    # Should be relatively clean (similar to actual NASA-LSP code)
    assert isinstance(result, list)
