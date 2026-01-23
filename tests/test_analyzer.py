from __future__ import annotations

import ast

from nasa_lsp.analyzer import (
    NasaVisitor,
    analyze,
)


def test_analyze_returns_empty_for_syntax_error() -> None:
    result = analyze("def broken(")
    assert result == []
    assert len(result) == 0


def test_analyze_returns_empty_for_empty_string() -> None:
    result = analyze("")
    assert result == []
    assert len(result) == 0


def test_analyze_returns_empty_for_whitespace_only() -> None:
    result = analyze("   \n\n  \t  ")
    assert result == []
    assert len(result) == 0


def test_analyze_returns_empty_for_valid_code_with_asserts() -> None:
    code = """
def foo():
    assert True
    assert False
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_nasa01a_detects_eval() -> None:
    code = """
def foo():
    assert True
    assert False
    eval("1+1")
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA01-A"


def test_nasa01a_detects_exec() -> None:
    code = """
def foo():
    assert True
    assert False
    exec("x=1")
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA01-A"
    assert "exec" in result[0].message


def test_nasa01a_detects_compile() -> None:
    code = """
def foo():
    assert True
    assert False
    compile("x=1", "", "exec")
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA01-A"
    assert "compile" in result[0].message


def test_nasa01a_detects_globals() -> None:
    code = """
def foo():
    assert True
    assert False
    globals()
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA01-A"
    assert "globals" in result[0].message


def test_nasa01a_detects_locals() -> None:
    code = """
def foo():
    assert True
    assert False
    locals()
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA01-A"
    assert "locals" in result[0].message


def test_nasa01a_detects_dunder_import() -> None:
    code = """
def foo():
    assert True
    assert False
    __import__("os")
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA01-A"
    assert "__import__" in result[0].message


def test_nasa01a_detects_setattr() -> None:
    code = """
def foo():
    assert True
    assert False
    setattr(obj, "x", 1)
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA01-A"
    assert "setattr" in result[0].message


def test_nasa01a_detects_getattr() -> None:
    code = """
def foo():
    assert True
    assert False
    getattr(obj, "x")
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA01-A"
    assert "getattr" in result[0].message


def test_nasa01a_detects_method_call_with_forbidden_name() -> None:
    code = """
def foo():
    assert True
    assert False
    obj.eval()
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA01-A"
    assert "eval" in result[0].message


def test_nasa01a_allows_safe_calls() -> None:
    code = """
def foo():
    assert True
    assert False
    print("hello")
    len([1, 2, 3])
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_nasa01b_detects_direct_recursion() -> None:
    code = """
def factorial(n):
    assert n >= 0
    assert isinstance(n, int)
    if n <= 1:
        return 1
    return n * factorial(n - 1)
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA01-B"


def test_nasa01b_allows_non_recursive_functions() -> None:
    code = """
def add(a, b):
    assert a is not None
    assert b is not None
    return a + b
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_nasa01b_detects_nested_function_recursion() -> None:
    code = """
def outer():
    assert True
    assert False
    def inner():
        inner()
    return inner
"""
    result = analyze(code)
    codes = [d.code for d in result]
    assert "NASA01-B" in codes
    inner_diag = next(d for d in result if d.code == "NASA01-B")
    assert "inner" in inner_diag.message


def test_nasa02_detects_while_true() -> None:
    code = """
def foo():
    assert True
    assert False
    while True:
        pass
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA02"
    assert "while True" in result[0].message


def test_nasa02_allows_bounded_while() -> None:
    code = """
def foo():
    assert True
    assert False
    x = 10
    while x > 0:
        x -= 1
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_nasa02_allows_while_false() -> None:
    code = """
def foo():
    assert True
    assert False
    while False:
        pass
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_nasa04_detects_long_function() -> None:
    lines = ["    pass"] * 61
    code = "def long_func():\n    assert True\n    assert False\n" + "\n".join(lines)
    result = analyze(code)
    codes = [d.code for d in result]
    assert "NASA04" in codes
    assert "long_func" in next(d for d in result if d.code == "NASA04").message


def test_nasa04_allows_short_function() -> None:
    code = """
def short_func():
    assert True
    assert False
    pass
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_nasa05_detects_zero_asserts() -> None:
    code = """
def no_asserts():
    pass
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA05"
    assert "0 assert" in result[0].message


def test_nasa05_detects_one_assert() -> None:
    code = """
def one_assert():
    assert True
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA05"
    assert "1 assert" in result[0].message


def test_nasa05_allows_two_asserts() -> None:
    code = """
def two_asserts():
    assert True
    assert False
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_nasa05_allows_more_than_two_asserts() -> None:
    code = """
def many_asserts():
    assert True
    assert False
    assert 1 == 1
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_nasa05_counts_nested_asserts() -> None:
    code = """
def nested_asserts():
    if True:
        assert True
        assert False
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_nasa05_ignores_asserts_in_nested_functions() -> None:
    code = """
def outer():
    def inner():
        assert True
        assert False
    pass
"""
    result = analyze(code)
    codes = [d.code for d in result]
    assert codes.count("NASA05") == 1
    nasa05 = next(d for d in result if d.code == "NASA05")
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
    result = analyze(code)
    outer_diags = [d for d in result if "outer" in d.message]
    assert len(outer_diags) == 1
    assert outer_diags[0].code == "NASA05"


def test_async_function_recursion() -> None:
    code = """
async def recursive():
    assert True
    assert False
    await recursive()
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA01-B"
    assert "recursive" in result[0].message


def test_async_function_asserts() -> None:
    code = """
async def no_asserts():
    await something()
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA05"


def test_async_function_with_enough_asserts() -> None:
    code = """
async def with_asserts():
    assert True
    assert False
    await something()
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_diagnostic_position_is_correct() -> None:
    code = "def foo():\n    pass"
    expected_col = len("def ")
    result = analyze(code)
    assert len(result) == 1
    assert result[0].range.start.character == expected_col


def test_multiple_violations_in_same_code() -> None:
    code = """
def bad():
    eval("x")
    while True:
        pass
"""
    result = analyze(code)
    codes = {d.code for d in result}
    assert "NASA01-A" in codes
    assert "NASA02" in codes
    assert "NASA05" in codes


def test_module_level_code_not_checked_for_asserts() -> None:
    code = """
x = 1
y = 2
print(x + y)
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_class_method_checked_for_asserts() -> None:
    code = """
class Foo:
    def method(self):
        pass
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA05"


def test_lambda_not_checked() -> None:
    code = """
def foo():
    assert True
    assert False
    f = lambda x: x + 1
    return f
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_range_for_func_name_fallback_when_def_not_found() -> None:
    code = "def foo(): pass"
    result = analyze(code)
    assert len(result) == 1
    assert result[0].range.start.line == 0


def test_empty_function_body() -> None:
    code = """
def empty():
    ...
"""
    result = analyze(code)
    assert len(result) == 1
    assert result[0].code == "NASA05"


def test_range_for_func_name_with_whitespace() -> None:
    code = """
def     foo():
    assert True
    assert False
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_call_with_no_name() -> None:
    code = """
def foo():
    assert True
    assert False
    x = (lambda: None)()
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_call_with_subscript() -> None:
    code = """
def foo():
    assert True
    assert False
    funcs = [print, len]
    funcs[0]("hello")
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0


def test_range_for_func_invalid_line_number() -> None:
    code = """
def foo():
    assert True
    assert False
"""
    tree = ast.parse(code)
    visitor = NasaVisitor(code)

    func_def = tree.body[0]
    assert isinstance(func_def, ast.FunctionDef)

    # Test that visitor can process the function even with modified line numbers
    # This tests the fallback behavior when line numbers are out of range
    saved_lineno = func_def.lineno
    func_def.lineno = 9999
    try:
        visitor.visit_FunctionDef(func_def)
        assert True  # If we get here, the fallback worked
        assert len(visitor.diagnostics) == 0  # Should have no violations
    finally:
        func_def.lineno = saved_lineno


def test_async_def_range_with_whitespace() -> None:
    code = """
async   def     foo():
    assert True
    assert False
"""
    result = analyze(code)
    assert result == []
    assert len(result) == 0
