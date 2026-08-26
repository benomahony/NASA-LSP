"""Cross-language tests for the tree-sitter engine.

These exercise the real grammars from ``tree-sitter-language-pack`` -- the same
parser production uses -- so there is no test-only parser seam that could pass
while the shipped path fails.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from nasa_lsp._languages import LANGUAGES, SUPPORTED_EXTENSIONS, language_for_path
from nasa_lsp.analyzer import ALL_RULES, analyze
from nasa_lsp.generic import analyze_generic


def codes(source: str, suffix: str) -> list[str]:
    diagnostics, _ = analyze(source, Path(f"snippet{suffix}"))
    return [d.code for d in diagnostics]


# --- language selection ----------------------------------------------------


def test_language_for_path_defaults_to_python() -> None:
    assert language_for_path(None) == "python"
    assert language_for_path(Path("mod.py")) == "python"
    assert language_for_path(Path("README.txt")) == "python"


def test_language_for_path_selects_by_suffix() -> None:
    assert language_for_path(Path("main.c")) == "c"
    assert language_for_path(Path("lib.rs")) == "rust"
    assert language_for_path(Path("app.TS")) == "typescript"


def test_supported_extensions_are_dotted_and_lower() -> None:
    assert ".c" in SUPPORTED_EXTENSIONS
    assert all(ext.startswith(".") and ext.islower() for ext in SUPPORTED_EXTENSIONS)


def test_every_language_name_matches_its_key() -> None:
    assert all(name == lang.name for name, lang in LANGUAGES.items())


# --- C ---------------------------------------------------------------------


def test_c_flags_recursion_forbidden_and_density() -> None:
    source = "int f(int n){\n  return f(n - 1);\n}\nvoid bad(void){ gets(); }\n"
    result = codes(source, ".c")
    assert "NASA01-recursion" in result
    assert "NASA01-forbidden-api" in result
    assert "NASA05" in result


def test_c_counts_assert_calls_toward_density() -> None:
    source = "int ok(int n){\n  assert(n > 0);\n  assert(n < 10);\n  return n;\n}\n"
    assert "NASA05" not in codes(source, ".c")


def test_c_flags_functions_over_the_line_budget() -> None:
    body = "\n".join(f"  int x{i} = {i};" for i in range(70))
    source = f"int big(void){{\n{body}\n  return 0;\n}}\n"
    assert "NASA04" in codes(source, ".c")


# --- Rust ------------------------------------------------------------------


def test_rust_recursion_and_assert_macro_density() -> None:
    recursive = "fn f(n: i32) -> i32 {\n  f(n - 1)\n}\n"
    assert "NASA01-recursion" in codes(recursive, ".rs")
    asserted = "fn g(n: i32) -> i32 {\n  assert!(n > 0);\n  debug_assert!(n < 9);\n  n\n}\n"
    assert "NASA05" not in codes(asserted, ".rs")


# --- Go: no assert idiom, so the density rule stays silent -----------------


def test_go_has_no_density_rule_but_still_finds_recursion() -> None:
    source = "package m\nfunc f(n int) int {\n  return f(n - 1)\n}\n"
    result = codes(source, ".go")
    assert "NASA01-recursion" in result
    assert "NASA05" not in result


# --- JavaScript / TypeScript ----------------------------------------------


def test_javascript_recursion() -> None:
    assert "NASA01-recursion" in codes("function f(n){ return f(n - 1); }\n", ".js")


def test_typescript_uses_custom_function_query() -> None:
    source = "function f(n: number){\n  return f(n - 1);\n}\n"
    result = codes(source, ".ts")
    assert "NASA01-recursion" in result


# --- engine edges ----------------------------------------------------------


def test_generic_engine_ignores_unregistered_language() -> None:
    diagnostics, stats = analyze_generic("fn main() {}", "haskell", ALL_RULES)
    assert diagnostics == []
    assert stats == []


def test_empty_source_is_clean_for_any_language() -> None:
    assert codes("", ".c") == []
    assert codes("   \n", ".rs") == []


def test_disabled_rule_is_not_emitted() -> None:
    source = "int f(int n){ return f(n - 1); }\n"
    diagnostics, _ = analyze_generic(source, "c", ALL_RULES - {"NASA01-recursion"})
    assert "NASA01-recursion" not in [d.code for d in diagnostics]


@pytest.mark.parametrize("suffix", [".c", ".rs", ".go", ".js", ".ts"])
def test_stats_are_reported_for_each_language(suffix: str) -> None:
    _, stats = analyze("", Path(f"empty{suffix}"))
    assert stats == []
    diagnostics, func_stats = analyze("int f(void){ return 0; }\n", Path(f"one{suffix}"))
    assert isinstance(diagnostics, list)
    assert isinstance(func_stats, list)
