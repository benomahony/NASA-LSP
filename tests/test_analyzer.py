from __future__ import annotations

from typing import TYPE_CHECKING

from nasa_lsp.analyzer import (
    DEFAULT_ENABLED_RULES,
    Diagnostic,
    Position,
    Range,
    analyze,
    load_enabled_rules,
    load_exclude_patterns,
    rule_severity,
)

if TYPE_CHECKING:
    from pathlib import Path

# The structural rules only: base-rule tests use illustrative asserts that should not
# trip the assertion-quality rules (NASA05-A and the NASA05-M family).
RULES_WITHOUT_ASSERT_MESSAGES = frozenset({"NASA01-A", "NASA01-B", "NASA02", "NASA04", "NASA05"})


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
    assert True, "Test assertion 1"
    assert False, "Test assertion 2"
"""
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert diagnostics == []
    assert isinstance(diagnostics, list)


def test_nasa01a_detects_eval() -> None:
    code = """
def foo():
    assert True
    assert False
    eval("1+1")
"""
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa04_detects_long_function() -> None:
    lines = ["    pass"] * 61
    code = "def long_func():\n    assert True\n    assert False\n" + "\n".join(lines)
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa05_detects_zero_asserts() -> None:
    code = """
def no_asserts():
    pass
"""
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA05"
    assert "0 assert" in diagnostics[0].message


def test_nasa05_detects_one_assert() -> None:
    code = """
def one_assert():
    assert True
"""
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA05"
    assert "1 assert" in diagnostics[0].message


def test_nasa05_allows_two_asserts() -> None:
    code = """
def two_asserts():
    assert True
    assert False
"""
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa05_allows_more_than_two_asserts() -> None:
    code = """
def many_asserts():
    assert True
    assert False
    assert 1 == 1
"""
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_nasa05_counts_nested_asserts() -> None:
    code = """
def nested_asserts():
    if True:
        assert True
        assert False
"""
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA01-B"
    assert "recursive" in diagnostics[0].message


def test_async_function_asserts() -> None:
    code = """
async def no_asserts():
    await something()
"""
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA05"


def test_async_function_with_enough_asserts() -> None:
    code = """
async def with_asserts():
    assert True
    assert False
    await something()
"""
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_diagnostic_position_is_correct() -> None:
    code = "def foo():\n    pass"
    expected_col = len("def ")
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_class_method_checked_for_asserts() -> None:
    code = """
class Foo:
    def method(self):
        pass
"""
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
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
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert diagnostics == []
    assert len(diagnostics) == 0


def test_range_for_func_name_fallback_when_def_not_found() -> None:
    code = "def foo(): pass"
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert len(diagnostics) == 1
    assert diagnostics[0].range.start.line == 0


def test_empty_function_body() -> None:
    code = """
def empty():
    ...
"""
    diagnostics, _ = analyze(code, enabled_rules=RULES_WITHOUT_ASSERT_MESSAGES)
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA05"


def test_nasa05_m1_flags_isinstance_restating_annotation() -> None:
    code = """
def f(value: bool) -> bool:
    assert isinstance(value, bool), "value must be a bool"
    return value
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M1"}))
    assert len(diagnostics) == 1
    assert diagnostics[0].code == "NASA05-M1"
    assert "bool" in diagnostics[0].message


def test_nasa05_m1_flags_isinstance_restating_optional_annotation() -> None:
    code = """
from pathlib import Path
def f(path: Path | None) -> None:
    assert isinstance(path, Path), "path must be a Path"
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M1"}))
    assert [d.code for d in diagnostics] == ["NASA05-M1"]


def test_nasa05_m1_ignores_isinstance_on_wider_annotation() -> None:
    code = """
def f(value: object) -> None:
    assert isinstance(value, int), "value must be int"
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M1"}))
    assert diagnostics == []


def test_nasa05_m1_ignores_isinstance_on_unannotated_param() -> None:
    code = """
def f(value):
    assert isinstance(value, int), "value must be int"
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M1"}))
    assert diagnostics == []


def test_nasa05_m2_flags_equality_after_literal_assignment() -> None:
    code = """
class C:
    def __init__(self):
        self.findings = {}
        assert self.findings == {}, "findings must start empty"
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M2"}))
    assert [d.code for d in diagnostics] == ["NASA05-M2"]


def test_nasa05_m2_flags_not_none_after_constant_assignment() -> None:
    code = """
def f():
    x = 5
    assert x is not None, "x must be set"
    return x
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M2"}))
    assert [d.code for d in diagnostics] == ["NASA05-M2"]


def test_nasa05_m2_ignores_assert_after_computed_value() -> None:
    code = """
def f():
    x = compute()
    assert x is not None, "compute may return None"
    return x
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M2"}))
    assert diagnostics == []


def test_nasa05_m2_ignores_assert_not_adjacent_to_assignment() -> None:
    code = """
def f(y):
    x = 5
    y = do(x)
    assert y is not None, "y comes from external call"
    return y
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M2"}))
    assert diagnostics == []


def test_nasa05_m3_flags_none_check_before_isinstance() -> None:
    code = """
def f(x):
    assert x is not None, "x must not be None"
    assert isinstance(x, int), "x must be an int"
    return x
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M3"}))
    assert [d.code for d in diagnostics] == ["NASA05-M3"]


def test_nasa05_m3_ignores_none_check_for_different_variable() -> None:
    code = """
def f(x, y):
    assert x is not None, "x must not be None"
    assert isinstance(y, int), "y must be an int"
    return x
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M3"}))
    assert diagnostics == []


def test_nasa05_m3_ignores_lone_none_check() -> None:
    code = """
def f(x):
    assert x is not None, "x must not be None"
    return len(x)
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M3"}))
    assert diagnostics == []


def test_nasa05_m4_flags_truthiness_of_str_result() -> None:
    code = """
def f(kind):
    name = str(kind)
    assert name, "kind name must be non-empty"
    return name
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M4"}))
    assert [d.code for d in diagnostics] == ["NASA05-M4"]


def test_nasa05_m4_flags_truthiness_of_fstring_result() -> None:
    code = """
def f(kind):
    label = f"kind-{kind}"
    assert label, "label must be non-empty"
    return label
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M4"}))
    assert [d.code for d in diagnostics] == ["NASA05-M4"]


def test_nasa05_m4_ignores_truthiness_of_arbitrary_call() -> None:
    code = """
def f(x):
    value = compute(x)
    assert value, "compute must return a truthy value"
    return value
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M4"}))
    assert diagnostics == []


def test_nasa05_m4_ignores_non_truthiness_assert() -> None:
    code = """
def f(kind):
    name = str(kind)
    assert name == "expected", "name must match"
    return name
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M4"}))
    assert diagnostics == []


def test_nasa05_m5_flags_non_negative_length_postcondition() -> None:
    code = """
def f(x):
    n = len(x)
    assert n >= 0, "length must be non-negative"
    return n
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M5"}))
    assert [d.code for d in diagnostics] == ["NASA05-M5"]


def test_nasa05_m5_ignores_positive_length_check() -> None:
    code = """
def f(x):
    n = len(x)
    assert n > 0, "must be non-empty"
    return n
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M5"}))
    assert diagnostics == []


def test_nasa05_m5_ignores_non_negative_check_on_arbitrary_value() -> None:
    code = """
def f(x):
    n = compute(x)
    assert n >= 0, "compute may return a negative value"
    return n
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M5"}))
    assert diagnostics == []


def test_nasa05_m6_flags_isinstance_on_wider_annotation() -> None:
    code = """
def f(value: object) -> None:
    assert isinstance(value, int), "value must be int"
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M6"}))
    assert [d.code for d in diagnostics] == ["NASA05-M6"]


def test_nasa05_m6_ignores_isinstance_combined_with_condition() -> None:
    code = """
def f(x):
    assert isinstance(x, int) and x > 0, "x must be a positive int"
    return x
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M6"}))
    assert diagnostics == []


def test_nasa05_m6_ignores_non_isinstance_assert() -> None:
    code = """
def f(x):
    assert x > 0, "x must be positive"
    return x
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M6"}))
    assert diagnostics == []


def test_nasa05_m6_does_not_double_flag_annotation_restatement() -> None:
    code = """
def f(value: bool) -> bool:
    assert isinstance(value, bool), "value must be a bool"
    return value
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M1", "NASA05-M6"}))
    assert [d.code for d in diagnostics] == ["NASA05-M1"]


def test_nasa05_m6_excludes_simple_isinstance_from_meaningful_count() -> None:
    code = """
def f(x):
    assert isinstance(x, int), "x must be an int"
    assert x > 5, "x must exceed the threshold"
    return x
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05", "NASA05-M6"}))
    codes = [d.code for d in diagnostics]
    assert "NASA05-M6" in codes
    assert "NASA05" in codes


def test_nasa05_m7_flags_or_type_guard() -> None:
    code = """
def main(argv):
    assert argv is None or isinstance(argv, list), "argv is a list of args or None"
    return 0
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M7"}))
    assert [d.code for d in diagnostics] == ["NASA05-M7"]


def test_nasa05_m7_ignores_single_condition_assert() -> None:
    code = """
def f(x):
    assert x > 0, "x must be positive"
    return x
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M7"}))
    assert diagnostics == []


def test_nasa05_m7_ignores_chained_comparison() -> None:
    code = """
def f(i, items):
    assert 0 <= i < len(items), "index must be in range"
    return items[i]
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M7"}))
    assert diagnostics == []


def test_nasa05_m7_excludes_compound_assertion_from_meaningful_count() -> None:
    code = """
def f(x, y):
    assert x > 0 and y > 0, "both must be positive"
    assert x != y, "x and y must differ"
    return x + y
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05", "NASA05-M7"}))
    codes = [d.code for d in diagnostics]
    assert "NASA05-M7" in codes
    assert "NASA05" in codes


def test_default_rules_enforce_the_quality_family() -> None:
    code = """
def f(query):
    assert query is None or isinstance(query, str), "query must be a string or None"
    return query
"""
    diagnostics, _ = analyze(code, enabled_rules=DEFAULT_ENABLED_RULES)
    assert "NASA05-M7" in [d.code for d in diagnostics], "compound assertions must fail by default"


def test_nasa05_count_excludes_flagged_assertions_when_m_rule_enabled() -> None:
    code = """
def f(value: bool) -> bool:
    assert isinstance(value, bool), "restates type"
    assert isinstance(value, bool), "restates type again"
    return value
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05", "NASA05-M1"}))
    codes = [d.code for d in diagnostics]
    assert "NASA05" in codes


def test_nasa05_count_keeps_flagged_assertions_when_m_rule_disabled() -> None:
    code = """
def f(value: bool) -> bool:
    assert isinstance(value, bool), "restates type"
    assert isinstance(value, bool), "restates type again"
    return value
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05"}))
    assert diagnostics == []


def test_ignore_comment_suppresses_specific_code() -> None:
    code = """
def f(value: bool) -> bool:
    assert isinstance(value, bool), "restates"  # nasa: ignore[NASA05-M1]
    assert value in (True, False), "real check"
    return value
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M1"}))
    assert diagnostics == []


def test_ignore_comment_blanket_suppresses_all_codes_on_line() -> None:
    code = """
def f(value: bool) -> bool:
    assert isinstance(value, bool), "restates"  # nasa: ignore
    assert value in (True, False), "real check"
    return value
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M1"}))
    assert diagnostics == []


def test_ignore_comment_for_other_code_does_not_suppress() -> None:
    code = """
def f(value: bool) -> bool:
    assert isinstance(value, bool), "restates"  # nasa: ignore[NASA04]
    assert value in (True, False), "real check"
    return value
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M1"}))
    assert [d.code for d in diagnostics] == ["NASA05-M1"]


def test_ignore_comment_suppresses_function_level_rule_on_def_line() -> None:
    code = """
def no_asserts():  # nasa: ignore[NASA05]
    return 1
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05"}))
    assert diagnostics == []


def test_ignore_comment_only_affects_its_own_line() -> None:
    code = """
def f(value: bool, other: bool) -> bool:
    assert isinstance(value, bool), "restates"  # nasa: ignore[NASA05-M1]
    assert isinstance(other, bool), "restates too"
    return value
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M1"}))
    assert len(diagnostics) == 1
    assert diagnostics[0].range.start.line == 3


def test_analyze_does_not_crash_on_undecodable_source() -> None:
    diagnostics, _ = analyze("\rº")
    assert diagnostics == []


def test_nasa05_m1_ignores_malformed_isinstance_arity() -> None:
    code = """
def f(value: int) -> None:
    assert isinstance(value), "single-arg isinstance"
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M1"}))
    assert diagnostics == []


def test_nasa05_m2_flags_bare_truthiness_after_constant() -> None:
    code = """
def f():
    x = 5
    assert x, "x was just set"
    return x
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M2"}))
    assert [d.code for d in diagnostics] == ["NASA05-M2"]


def test_nasa05_m3_ignores_is_not_check_against_non_none() -> None:
    code = """
def f(x):
    assert x is not True, "not the sentinel"
    assert isinstance(x, int), "x must be int"
    return x
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M3"}))
    assert diagnostics == []


def test_nasa05_m5_ignores_chained_length_comparison() -> None:
    code = """
def f(x):
    n = len(x)
    assert 0 <= n <= 10, "bounded"
    return n
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M5"}))
    assert diagnostics == []


def test_nasa05_m5_ignores_length_bound_on_other_variable() -> None:
    code = """
def f(x, k):
    n = len(x)
    assert k >= 0, "k is unrelated to n"
    return n
"""
    diagnostics, _ = analyze(code, enabled_rules=frozenset({"NASA05-M5"}))
    assert diagnostics == []


def test_rule_severity_maps_documented_levels() -> None:
    assert rule_severity("NASA05-M2") == "error"
    assert rule_severity("NASA05") == "error"
    assert rule_severity("NASA05-M1") == "warning"
    assert rule_severity("NASA05-M3") == "warning"
    assert rule_severity("NASA05-M4") == "information"
    assert rule_severity("NASA05-M5") == "information"


def test_rule_severity_defaults_to_warning_for_unknown_code() -> None:
    assert rule_severity("NASA01-A") == "warning"
    assert rule_severity("SOMETHING-ELSE") == "warning"


def test_load_exclude_patterns_reads_config(tmp_path: Path) -> None:
    _ = (tmp_path / "pyproject.toml").write_text('[tool.nasa-lsp]\nexclude = ["tests", "*.pyi"]\n')
    patterns = load_exclude_patterns(tmp_path)
    assert patterns == ("tests", "*.pyi")


def test_load_exclude_patterns_defaults_to_empty(tmp_path: Path) -> None:
    _ = (tmp_path / "pyproject.toml").write_text('[tool.nasa-lsp]\nrules = ["NASA05"]\n')
    patterns = load_exclude_patterns(tmp_path)
    assert patterns == ()


def test_load_enabled_rules_reads_config_after_refactor(tmp_path: Path) -> None:
    _ = (tmp_path / "pyproject.toml").write_text('[tool.nasa-lsp]\nrules = ["NASA02", "NASA04"]\n')
    rules = load_enabled_rules(tmp_path)
    assert rules == frozenset({"NASA02", "NASA04"})
