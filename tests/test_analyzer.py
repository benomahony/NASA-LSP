from __future__ import annotations

from nasa_lsp.analyzer import (
    Diagnostic,
    Position,
    Range,
    analyze,
)


def test_analyze_returns_empty_for_syntax_error() -> None:
    diagnostics, _ = analyze("def broken(")
    assert diagnostics == []
    assert isinstance(diagnostics, list)


def test_analyze_returns_empty_for_empty_string() -> None:
    diagnostics, _ = analyze("")
    assert diagnostics == []
    assert isinstance(diagnostics, list)


def test_analyze_returns_empty_for_whitespace_only() -> None:
    diagnostics, _ = analyze("   \n\n  \t  ")
    assert diagnostics == []
    assert isinstance(diagnostics, list)


def test_analyze_returns_empty_for_valid_code_with_asserts() -> None:
    code = """
def foo():
    assert True
    assert False
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert isinstance(diagnostics, list)


def test_nasa01a_detects_eval() -> None:
    code = """
def foo():
    assert True
    assert False
    eval("1+1")
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-A"
    assert "eval" in diagnostics[0].message
    assert isinstance(diagnostics[0], Diagnostic)


def test_nasa01a_detects_exec() -> None:
    code = """
def foo():
    assert True
    assert False
    exec("x=1")
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-A"
    assert "exec" in diagnostics[0].message


def test_nasa01a_detects_compile() -> None:
    code = """
def foo():
    assert True
    assert False
    compile("x=1", "", "exec")
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-A"
    assert "compile" in diagnostics[0].message


def test_nasa01a_detects_globals() -> None:
    code = """
def foo():
    assert True
    assert False
    globals()
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-A"
    assert "globals" in diagnostics[0].message


def test_nasa01a_detects_locals() -> None:
    code = """
def foo():
    assert True
    assert False
    locals()
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-A"
    assert "locals" in diagnostics[0].message


def test_nasa01a_detects_dunder_import() -> None:
    code = """
def foo():
    assert True
    assert False
    __import__("os")
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-A"
    assert "__import__" in diagnostics[0].message


def test_nasa01a_detects_setattr() -> None:
    code = """
def foo():
    assert True
    assert False
    setattr(obj, "x", 1)
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-A"
    assert "setattr" in diagnostics[0].message


def test_nasa01a_detects_getattr() -> None:
    code = """
def foo():
    assert True
    assert False
    getattr(obj, "x")
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-A"
    assert "getattr" in diagnostics[0].message


def test_nasa01a_detects_method_call_with_forbidden_name() -> None:
    code = """
def foo():
    assert True
    assert False
    obj.eval()
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-A"
    assert "eval" in diagnostics[0].message


def test_nasa01a_allows_safe_calls() -> None:
    code = """
def foo():
    assert True
    assert False
    print("hello")
    len([1, 2, 3])
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa01b_detects_direct_recursion() -> None:
    code = """
def factorial(n):
    assert n >= 0
    assert isinstance(n, int)
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-B"
    assert "factorial" in diagnostics[0].message
    assert "Recursive" in diagnostics[0].message


def test_nasa01b_allows_non_recursive_functions() -> None:
    code = """
def add(a, b):
    assert a is not None
    assert b is not None
    return a + b
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa01b_detects_nested_function_recursion() -> None:
    code = """
def outer():
    assert True
    assert False
    def inner():
        inner()
    return inner
"""
    diagnostics, _ = analyze(code)
    codes = [d.code for d in diagnostics]
    assert "NASA01-B" in codes
    inner_diag = next(d for d in diagnostics if d.code == "NASA01-B")
    assert "inner" in inner_diag.message


def test_nasa02_detects_while_true() -> None:
    code = """
def foo():
    assert True
    assert False
    while True:
        pass
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA02"
    assert "while True" in diagnostics[0].message


def test_nasa02_allows_bounded_while() -> None:
    code = """
def foo():
    assert True
    assert False
    x = 10
    while x > 0:
        x -= 1
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa02_allows_while_false() -> None:
    code = """
def foo():
    assert True
    assert False
    while False:
        pass
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa04_detects_long_function() -> None:
    lines = ["    pass"] * 61
    code = "def long_func():\n    assert True\n    assert False\n" + "\n".join(lines)
    diagnostics, _ = analyze(code)
    codes = [d.code for d in diagnostics]
    assert "NASA04" in codes
    nasa04 = next(d for d in diagnostics if d.code == "NASA04")
    assert "long_func" in nasa04.message
    assert "60" in nasa04.message


def test_nasa04_allows_short_function() -> None:
    code = """
def short_func():
    assert True
    assert False
    pass
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa05_detects_zero_asserts() -> None:
    code = """
def no_asserts():
    pass
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA05"
    assert "0 assert" in diagnostics[0].message


def test_nasa05_detects_one_assert() -> None:
    code = """
def one_assert():
    assert True
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA05"
    assert "1 assert" in diagnostics[0].message


def test_nasa05_allows_two_asserts() -> None:
    code = """
def two_asserts():
    assert True
    assert False
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa05_allows_more_than_two_asserts() -> None:
    code = """
def many_asserts():
    assert True
    assert False
    assert 1 == 1
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa05_counts_nested_asserts() -> None:
    code = """
def nested_asserts():
    if True:
        assert True
        assert False
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa05_ignores_asserts_in_nested_functions() -> None:
    code = """
def outer():
    def inner():
        assert True
        assert False
    pass
"""
    diagnostics, _ = analyze(code)
    codes = [d.code for d in diagnostics]
    assert codes.count("NASA05") == 1
    nasa05 = next(d for d in diagnostics if d.code == "NASA05")
    assert "outer" in nasa05.message


def test_nasa05_ignores_asserts_in_nested_classes() -> None:
    code = """
def outer():
    class Inner:
        def method(self):
            assert True
            assert False
    pass
"""
    diagnostics, _ = analyze(code)
    outer_diags = [d for d in diagnostics if "outer" in d.message]
    assert len(outer_diags) == 1
    assert outer_diags[0].code == "NASA05"


def test_async_function_recursion() -> None:
    code = """
async def recursive():
    assert True
    assert False
    await recursive()
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-B"
    assert "recursive" in diagnostics[0].message


def test_async_function_asserts() -> None:
    code = """
async def no_asserts():
    await something()
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA05"


def test_async_function_with_enough_asserts() -> None:
    code = """
async def with_asserts():
    assert True
    assert False
    await something()
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_diagnostic_position_is_correct() -> None:
    code = "def foo():\n    pass"
    expected_col = len("def ")
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    diag = diagnostics[0]
    assert isinstance(diag.range, Range)
    assert isinstance(diag.range.start, Position)
    assert isinstance(diag.range.end, Position)
    assert diag.range.start.line == 0
    assert diag.range.start.character == expected_col


def test_multiple_violations_in_same_code() -> None:
    code = """
def bad():
    eval("x")
    while True:
        pass
"""
    diagnostics, _ = analyze(code)
    codes = {d.code for d in diagnostics}
    assert "NASA01-A" in codes
    assert "NASA02" in codes
    assert "NASA05" in codes


def test_module_level_code_not_checked_for_asserts() -> None:
    code = """
x = 1
y = 2
print(x + y)
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_class_method_checked_for_asserts() -> None:
    code = """
class Foo:
    def method(self):
        pass
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA05"
    assert "method" in diagnostics[0].message


def test_lambda_not_checked() -> None:
    code = """
def foo():
    assert True
    assert False
    f = lambda x: x + 1
    return f
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_range_for_func_name_fallback_when_def_not_found() -> None:
    code = "def foo(): pass"
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].range.start.line == 0


def test_empty_function_body() -> None:
    code = """
def empty():
    ...
"""
    diagnostics, _ = analyze(code)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA05"
