from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
from pytest_examples import CodeExample, EvalExample, find_examples

from nasa_lsp import analyzer, generic
from nasa_lsp.analyzer import ALL_RULES, analyze

# Fenced-example language -> a file suffix that selects it, so a rule can be
# demonstrated in whatever language it applies to (NASA03 is C, not Python).
_FENCE_SUFFIX = {
    "python": ".py",
    "c": ".c",
    "cpp": ".cpp",
    "rust": ".rs",
    "go": ".go",
    "javascript": ".js",
    "typescript": ".ts",
}


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


_SLUG = re.compile(r"NASA0[0-9](?:-[a-z][a-z-]*)?")


def _emitted_rule_codes() -> set[str]:
    """Every rule code emitted by either analyzer, read from the source.

    A code is the last positional argument of a diagnostic-adding method call
    (``_add_diag`` in the Python analyzer, ``add`` in the tree-sitter engine).
    Codes are ``NASA0N``-shaped; the shape filter also skips the mutated string
    variants (uppercased, ``XX..XX``-wrapped) that mutmut writes into its mutants tree.
    """
    codes: set[str] = set()
    for module in (analyzer, generic):
        module_file = module.__file__
        assert module_file is not None, "analyzer modules are loaded from files"
        tree = ast.parse(Path(module_file).read_text())
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.args):
                continue
            code = node.args[-1]
            if isinstance(code, ast.Constant) and isinstance(code.value, str) and _SLUG.fullmatch(code.value):
                codes.add(code.value)
    assert codes, "expected to find rule codes emitted by the analyzers"
    return codes


def _reference_section() -> str:
    text = RULES_DOC.read_text()
    return text.split("## Rule detection reference", 1)[1].split("## Original", 1)[0]


# A rule label is a slug in backticks at the start of a line (`NASA05-isinstance` — ...).
_LABEL = r"(?m)^`(NASA0[0-9](?:-[a-z][a-z-]*)?)`"


def _documented_rules() -> set[str]:
    """Every rule labelled in the reference section."""
    return set(re.findall(_LABEL, _reference_section()))


def _doc_rule_examples() -> list[tuple[str, str, str]]:
    """(rule_code, fence_language, source) for each fenced example, by its label."""
    parts = re.split(r"```(\w+)\n(.*?)\n```", _reference_section(), flags=re.DOTALL)
    examples: list[tuple[str, str, str]] = []
    for preceding, language, source in zip(parts[0::3], parts[1::3], parts[2::3], strict=False):
        labels = re.findall(_LABEL, preceding)
        assert labels, "each example block must be preceded by a rule label"
        assert language in _FENCE_SUFFIX, f"unsupported example language: {language}"
        examples.append((labels[-1], language, source))
    assert examples, "expected labelled rule examples in the reference section"
    return examples


_RULE_EXAMPLES = _doc_rule_examples()


@pytest.mark.parametrize(("code", "language", "source"), _RULE_EXAMPLES, ids=[code for code, _, _ in _RULE_EXAMPLES])
def test_doc_source_triggers_its_rule(code: str, language: str, source: str) -> None:
    example_path = Path("example").with_suffix(_FENCE_SUFFIX[language])
    diagnostics, _ = analyze(source, example_path, enabled_rules=frozenset({code}))
    assert [d.code for d in diagnostics] == [code], f"{code} example did not trigger {code}"


def test_every_rule_is_documented() -> None:
    missing = sorted(_emitted_rule_codes() - _documented_rules())
    assert not missing, f"rules absent from the reference section: {missing}"


def test_registry_matches_the_emittable_rules() -> None:
    # ALL_RULES is the single source of truth: every rule the linter emits must be
    # registered (so it is known, severity-mapped, and on by default), and the
    # registry must not list a rule that no longer exists.
    assert _emitted_rule_codes() == set(ALL_RULES)
