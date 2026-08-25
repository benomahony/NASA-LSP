from __future__ import annotations

import ast
import doctest
from pathlib import Path

from nasa_lsp import analyzer

ANALYZER_PATH = Path(analyzer.__file__)


def _emitted_rule_codes() -> set[str]:
    """Every rule code passed to NasaVisitor._add_diag in analyzer.py.

    This is the authoritative set of diagnostics the linter can emit, read
    straight from the source so the doc test cannot drift from the rules.
    """
    tree = ast.parse(ANALYZER_PATH.read_text())
    codes: set[str] = set()
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)):
            continue
        if node.func.attr != "_add_diag":
            continue
        for arg in (*node.args, *(kw.value for kw in node.keywords)):
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and arg.value.startswith("NASA"):
                codes.add(arg.value)
    assert codes, "expected to find rule codes emitted via _add_diag"
    assert all(c.startswith("NASA") for c in codes), "every emitted rule code must be NASA-prefixed"
    return codes


def _doctest_wants() -> str:
    """The concatenated expected output of every doctest in the analyzer module."""
    examples = [ex for test in doctest.DocTestFinder().find(analyzer) for ex in test.examples]
    assert examples, "analyzer module must contain rule doctests"
    return "\n".join(ex.want for ex in examples)


def test_rule_doctests_execute_cleanly() -> None:
    results = doctest.testmod(analyzer)
    assert results.attempted > 0, "expected analyzer rule doctests to run"
    assert results.failed == 0, "analyzer rule doctests must pass"


def test_every_rule_code_has_a_doctest() -> None:
    wants = _doctest_wants()
    codes = _emitted_rule_codes()
    # Each rule doctest reports its diagnostic code as a quoted repr (e.g. 'NASA05-M6'),
    # so the trailing quote keeps 'NASA05' from matching 'NASA05-M1' and friends.
    missing = sorted(code for code in codes if f"'{code}'" not in wants)
    assert not missing, f"rule codes with no doctest example: {missing}"
