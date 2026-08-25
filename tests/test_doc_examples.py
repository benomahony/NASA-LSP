from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from pytest_examples import CodeExample, EvalExample, find_examples

from nasa_lsp import analyzer
from nasa_lsp.analyzer import analyze


def _repo_file(relative: str) -> Path:
    """Locate a repo file by walking up from this test, since the cwd varies.

    mutmut runs the suite from a copied ``mutants/`` tree that omits the docs, so
    the nearest ancestor that actually contains the file is the real repo root.
    """
    for parent in Path(__file__).resolve().parents:
        candidate = parent / relative
        if candidate.exists():
            return candidate
    raise FileNotFoundError(relative)


RULES_DOC = _repo_file("docs/rules.md")
README = _repo_file("README.md")


_README_EXAMPLES = list(find_examples(README))


@pytest.mark.parametrize("example", _README_EXAMPLES, ids=[str(example) for example in _README_EXAMPLES])
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
    return codes


def _reference_section() -> str:
    text = RULES_DOC.read_text()
    return text.split("## Rule detection reference", 1)[1].split("## Original", 1)[0]


def _documented_rules() -> set[str]:
    """Every rule labelled in the reference section (a label starts its line)."""
    return set(re.findall(r"(?m)^`(NASA[\w-]+)`", _reference_section()))


def _doc_rule_examples() -> list[tuple[str, str]]:
    """(rule_code, source) for each fenced example, paired with its preceding `NASA...` label."""
    parts = re.split(r"```python\n(.*?)\n```", _reference_section(), flags=re.DOTALL)
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


def test_every_rule_is_documented() -> None:
    missing = sorted(_emitted_rule_codes() - _documented_rules())
    assert not missing, f"rules absent from the reference section: {missing}"
