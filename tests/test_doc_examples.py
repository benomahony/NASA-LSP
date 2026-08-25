from __future__ import annotations

import pytest
from pytest_examples import CodeExample, EvalExample, find_examples


@pytest.mark.parametrize("example", find_examples("README.md", "docs/rules.md"), ids=str)
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
