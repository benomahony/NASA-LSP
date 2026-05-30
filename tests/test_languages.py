"""Cross-language analyzer tests.

Each supported language is exercised against the rules that apply to it. Parsers
are seeded from bundled grammar wheels in ``conftest.py``.
"""

from __future__ import annotations

from nasa_lsp._languages import SUPPORTED_EXTENSIONS, language_for_suffix
from nasa_lsp.analyzer import analyze


def codes(code: str, language: str) -> list[str]:
    assert isinstance(code, str)
    assert isinstance(language, str)
    diagnostics, _ = analyze(code, language)
    return [d.code for d in diagnostics]


# --- language detection ----------------------------------------------------


def test_language_for_suffix_known_extensions() -> None:
    assert language_for_suffix(".py") == "python"
    assert language_for_suffix(".c") == "c"
    assert language_for_suffix(".h") == "c"
    assert language_for_suffix(".cpp") == "cpp"
    assert language_for_suffix(".go") == "go"
    assert language_for_suffix(".rs") == "rust"
    assert language_for_suffix(".js") == "javascript"
    assert language_for_suffix(".ts") == "typescript"


def test_language_for_suffix_is_case_insensitive() -> None:
    assert language_for_suffix(".PY") == "python"
    assert language_for_suffix(".Rs") == "rust"


def test_language_for_suffix_unknown_returns_none() -> None:
    assert language_for_suffix(".txt") is None
    assert language_for_suffix("") is None


def test_supported_extensions_are_dotted() -> None:
    assert ".py" in SUPPORTED_EXTENSIONS
    assert all(ext.startswith(".") for ext in SUPPORTED_EXTENSIONS)


# --- unknown language / invalid input --------------------------------------


def test_unknown_language_returns_empty() -> None:
    diagnostics, stats = analyze("fn main() {}", "haskell")
    assert diagnostics == []
    assert stats == []


def test_empty_text_returns_empty_for_any_language() -> None:
    diagnostics, stats = analyze("", "rust")
    assert diagnostics == []
    assert stats == []


def test_syntax_error_returns_empty() -> None:
    diagnostics, _ = analyze("int main(", "c")
    assert diagnostics == []
    assert isinstance(diagnostics, list)


# --- C ---------------------------------------------------------------------


def test_c_detects_recursion() -> None:
    code = "int fac(int n) {\n    assert(n >= 0);\n    assert(n < 10);\n    return fac(n - 1);\n}"
    result = codes(code, "c")
    assert "NASA01-B" in result
    assert isinstance(result, list)


def test_c_detects_unbounded_while_and_for() -> None:
    code = "void loop_forever(void) {\n    while (1) {}\n    for (;;) {}\n}"
    result = codes(code, "c")
    assert result.count("NASA02") == 2
    assert isinstance(result, list)


def test_c_detects_forbidden_call() -> None:
    code = "void read_input(char *buf) {\n    assert(buf);\n    assert(buf != 0);\n    gets(buf);\n}"
    result = codes(code, "c")
    assert "NASA01-A" in result
    assert isinstance(result, list)


def test_c_assert_density_enforced() -> None:
    code = "int bare(void) {\n    return 0;\n}"
    result = codes(code, "c")
    assert "NASA05" in result
    assert isinstance(result, list)


def test_c_bounded_loop_is_clean() -> None:
    code = "void f(int n) {\n    assert(n > 0);\n    assert(n < 5);\n    for (int i = 0; i < n; i++) {}\n}"
    result = codes(code, "c")
    assert result == []
    assert isinstance(result, list)


def test_c_bounded_while_with_variable_is_clean() -> None:
    code = "void f(int n) {\n    assert(n > 0);\n    assert(n < 9);\n    while (n) { n--; }\n}"
    result = codes(code, "c")
    assert result == []
    assert isinstance(result, list)


def test_c_while_zero_is_not_flagged() -> None:
    code = "void f(void) {\n    assert(1);\n    assert(1);\n    while (0) {}\n}"
    result = codes(code, "c")
    assert "NASA02" not in result
    assert isinstance(result, list)


# --- C++ -------------------------------------------------------------------


def test_cpp_detects_while_true_and_recursion() -> None:
    code = "int fac(int n) {\n    assert(n >= 0);\n    assert(n < 10);\n    while (true) {}\n    return fac(n - 1);\n}"
    result = codes(code, "cpp")
    assert "NASA02" in result
    assert "NASA01-B" in result


# --- Go --------------------------------------------------------------------


def test_go_detects_bare_infinite_loop() -> None:
    code = "func spin() {\n\tfor {\n\t}\n}"
    result = codes(code, "go")
    assert "NASA02" in result
    assert isinstance(result, list)


def test_go_detects_recursion() -> None:
    code = "func fac(n int) int {\n\treturn fac(n - 1)\n}"
    result = codes(code, "go")
    assert "NASA01-B" in result
    assert isinstance(result, list)


def test_go_does_not_enforce_asserts() -> None:
    code = "func noop() {\n}"
    result = codes(code, "go")
    assert "NASA05" not in result
    assert isinstance(result, list)


def test_go_bounded_loop_is_clean() -> None:
    code = "func f(n int) {\n\tfor i := 0; i < n; i++ {\n\t}\n}"
    result = codes(code, "go")
    assert result == []
    assert isinstance(result, list)


def test_go_conditional_for_is_not_flagged() -> None:
    # `for cond {}` is Go's while-loop form and is bounded by its condition.
    code = "func f(n int) {\n\tfor n > 0 {\n\t\tn--\n\t}\n}"
    result = codes(code, "go")
    assert "NASA02" not in result
    assert isinstance(result, list)


# --- Rust ------------------------------------------------------------------


def test_rust_detects_loop_and_while_true() -> None:
    code = "fn spin() {\n    loop {}\n    while true {}\n}"
    result = codes(code, "rust")
    assert result.count("NASA02") == 2
    assert isinstance(result, list)


def test_rust_detects_recursion() -> None:
    code = "fn fac(n: i32) -> i32 {\n    fac(n - 1)\n}"
    result = codes(code, "rust")
    assert "NASA01-B" in result
    assert isinstance(result, list)


def test_rust_assert_macros_count_toward_density() -> None:
    code = "fn ok(a: i32) -> i32 {\n    assert!(a > 0);\n    assert_eq!(a, a);\n    a\n}"
    result = codes(code, "rust")
    assert "NASA05" not in result
    assert isinstance(result, list)


def test_rust_missing_assertions_flagged() -> None:
    code = "fn bare(a: i32) -> i32 {\n    a\n}"
    result = codes(code, "rust")
    assert "NASA05" in result
    assert isinstance(result, list)


def test_long_function_flagged_in_rust() -> None:
    body = "\n".join(["    let _x = 0;"] * 61)
    code = f"fn big() {{\n{body}\n}}"
    result = codes(code, "rust")
    assert "NASA04" in result
    assert isinstance(result, list)


# --- JavaScript / TypeScript ----------------------------------------------


def test_javascript_detects_eval() -> None:
    code = "function run(x) {\n    eval(x);\n}"
    result = codes(code, "javascript")
    assert "NASA01-A" in result
    assert isinstance(result, list)


def test_javascript_detects_while_true_for_ever_and_recursion() -> None:
    code = "function fac(n) {\n    while (true) {}\n    for (;;) {}\n    return fac(n - 1);\n}"
    result = codes(code, "javascript")
    assert result.count("NASA02") == 2
    assert "NASA01-B" in result


def test_javascript_does_not_enforce_asserts() -> None:
    code = "function noop() {\n}"
    result = codes(code, "javascript")
    assert "NASA05" not in result
    assert isinstance(result, list)


def test_javascript_bounded_for_is_not_flagged() -> None:
    code = "function f(n) {\n    for (let i = 0; i < n; i++) {}\n}"
    result = codes(code, "javascript")
    assert "NASA02" not in result
    assert isinstance(result, list)


def test_javascript_anonymous_function_not_checked_for_asserts() -> None:
    # An anonymous function expression has no name, so per-function rules skip it,
    # but a global rule (unbounded loop) inside it is still reported.
    code = "const f = function () {\n    while (true) {}\n};"
    result = codes(code, "javascript")
    assert "NASA05" not in result
    assert "NASA02" in result


def test_typescript_detects_while_true() -> None:
    code = "function fac(n: number): number {\n    while (true) {}\n    return fac(n - 1);\n}"
    result = codes(code, "typescript")
    assert "NASA02" in result
    assert "NASA01-B" in result
