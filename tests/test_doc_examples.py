from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from pytest_examples import CodeExample, EvalExample, find_examples

from nasa_lsp import analyzer
from nasa_lsp.analyzer import analyze

RULES_DOC = Path("docs/rules.md")


@pytest.mark.parametrize("example", find_examples("README.md"), ids=str)
def test_readme_examples(example: CodeExample, eval_example: EvalExample) -> None:
    """Every Python code block in the README must be valid, formatted, and importable."""
    eval_example.set_config(line_length=120, ruff_ignore=["ANN", "PLR2004", "INP001"])
    if eval_example.update_examples:
        eval_example.format(example)
    else:
        eval_example.lint(example)
    _ = eval_example.run(example)


def _emitted_rule_codes() -> set[str]:
    """Every rule code passed to NasaVisitor._add_diag, read from the analyzer source."""
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


def _doc_rule_examples() -> list[tuple[str, str]]:
    """(rule_code, source) for each labelled example in the 'Rule detection reference' section.

    Each fenced block is preceded by a `NASA...` label; the source is the block itself.
    """
    text = RULES_DOC.read_text()
    section = text.split("## Rule detection reference", 1)[1].split("## Original", 1)[0]
    parts = re.split(r"```python\n(.*?)\n```", section, flags=re.DOTALL)
    examples: list[tuple[str, str]] = []
    for preceding, source in zip(parts[0::2], parts[1::2], strict=False):
        labels = re.findall(r"`(NASA[\w-]+)`", preceding)
        assert labels, "each example block must be preceded by a rule label"
        examples.append((labels[-1], source))
    assert examples, "expected labelled rule examples in the reference section"
    return examples


_RULE_EXAMPLES = _doc_rule_examples()


@pytest.mark.parametrize(("code", "source"), _RULE_EXAMPLES, ids=[code for code, _ in _RULE_EXAMPLES])
def test_doc_source_triggers_its_rule(code: str, source: str) -> None:
    diagnostics, _ = analyze(source, enabled_rules=frozenset({code}))
    assert [d.code for d in diagnostics] == [code], f"{code} example did not trigger {code}"


def test_every_rule_has_a_doc_example() -> None:
    documented = {code for code, _ in _doc_rule_examples()}
    missing = sorted(_emitted_rule_codes() - documented)
    assert not missing, f"rules with no doc example: {missing}"
