from __future__ import annotations

import ast
from pathlib import Path

import pytest
from pytest_examples import CodeExample, EvalExample, find_examples

from nasa_lsp import analyzer

DOC_SOURCES = ("README.md", "docs/rules.md")


@pytest.mark.parametrize("example", find_examples(*DOC_SOURCES), ids=str)
def test_doc_examples(example: CodeExample, eval_example: EvalExample) -> None:
    """Every Python code block in the docs must be valid, formatted, and importable."""
    # Docs are illustrative snippets, so relax rules that only make sense for
    # production modules: type annotations, "magic" literals, and the
    # implicit-namespace-package check (every snippet is a standalone file).
    # PT018 is ignored because the rule docs deliberately show a compound
    # assertion as an anti-pattern (the very thing NASA05-M7 flags).
    eval_example.set_config(
        line_length=120,
        ruff_ignore=["ANN", "PLR2004", "INP001", "PT018"],
    )
    if eval_example.update_examples:
        eval_example.format(example)
    else:
        eval_example.lint(example)
    _ = eval_example.run(example)


def _emitted_rule_codes() -> set[str]:
    """Every rule code passed to NasaVisitor._add_diag in analyzer.py.

    Read straight from the source so the coverage check cannot drift from the
    rules the linter can actually emit.
    """
    tree = ast.parse(Path(analyzer.__file__).read_text())
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


def test_every_rule_has_a_doc_example() -> None:
    sources = "\n".join(example.source for example in find_examples(*DOC_SOURCES))
    # Codes appear quoted in the docs (e.g. "NASA05"), and the trailing quote
    # keeps "NASA05" from matching "NASA05-M1" and friends.
    missing = sorted(code for code in _emitted_rule_codes() if f'"{code}"' not in sources)
    assert not missing, f"rules with no doc example: {missing}"
