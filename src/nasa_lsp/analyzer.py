"""Language-agnostic NASA Power of 10 analyzer.

The analyzer parses source with tree-sitter and walks the resulting syntax tree,
applying the Power of 10 rules through a per-language :class:`LanguageSpec`. The
public surface (:func:`analyze`, :class:`Diagnostic`, :class:`Position`,
:class:`Range`, :class:`FunctionStat`) is unchanged from the original
Python-only implementation, so existing callers keep working; Python remains the
default language.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

from nasa_lsp._languages import (
    SPECS,
    LanguageSpec,
    direct_callee_name,
    node_text,
    resolved_callee_name,
)
from nasa_lsp._parsers import get_parser

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tree_sitter import Node

MAX_FUNCTION_LINES: Final = 60
MIN_ASSERTS_PER_FUNCTION: Final = 2
DEFAULT_LANGUAGE: Final = "python"


@dataclass
class Position:
    line: int
    character: int


@dataclass
class Range:
    start: Position
    end: Position


@dataclass
class Diagnostic:
    range: Range
    message: str
    code: str


@dataclass
class FunctionStat:
    name: str
    line_start: int
    line_count: int
    assert_count: int


def _pos(point: tuple[int, int]) -> Position:
    row, col = point
    assert row >= 0
    assert col >= 0
    return Position(line=row, character=col)


def _range_of(node: Node) -> Range:
    assert node is not None
    assert isinstance(node.type, str)
    return Range(start=_pos(node.start_point), end=_pos(node.end_point))


def _walk(node: Node) -> Iterator[Node]:
    """Yield ``node`` and every descendant (iterative, no recursion)."""
    assert node is not None
    assert isinstance(node.type, str)
    stack: list[Node] = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def _walk_within_scope(node: Node, spec: LanguageSpec) -> Iterator[Node]:
    """Yield descendants of ``node`` without entering nested scopes.

    Used so a function's assertions/recursion are measured against its own body,
    not against nested functions or classes. Iterative to avoid recursion.
    """
    assert node is not None
    assert spec is not None
    stack: list[Node] = list(reversed(node.children))
    while stack:
        current = stack.pop()
        yield current
        if current.type not in spec.scope_nodes:
            stack.extend(reversed(current.children))


class _Analysis:
    def __init__(self, spec: LanguageSpec) -> None:
        assert spec is not None
        assert isinstance(spec, LanguageSpec)
        self.spec: LanguageSpec = spec
        self.diagnostics: list[Diagnostic] = []
        self.stats: list[FunctionStat] = []

    def _add(self, rng: Range, message: str, code: str) -> None:
        assert message
        assert code
        self.diagnostics.append(Diagnostic(range=rng, message=message, code=code))

    # --- NASA01-A: forbidden APIs, NASA02: unbounded loops (whole-tree) ---

    def check_global_rules(self, root: Node) -> None:
        assert root is not None
        assert isinstance(root.type, str)
        spec = self.spec
        for node in _walk(root):
            if node.type in spec.call_nodes and spec.forbidden_calls:
                name = resolved_callee_name(node)
                if name in spec.forbidden_calls:
                    callee = node.child_by_field_name("function") or node
                    self._add(
                        _range_of(callee),
                        f"Call to forbidden API '{name}' (NASA01: restricted subset)",
                        "NASA01-A",
                    )
            label = spec.unbounded_loop(node)
            if label is not None:
                self._add(
                    _range_of(node),
                    f"Unbounded loop '{label}' (NASA02: loops must be bounded)",
                    "NASA02",
                )

    # --- NASA01-B, NASA04, NASA05: per function ---

    def check_functions(self, root: Node) -> None:
        assert root is not None
        assert isinstance(root.type, str)
        spec = self.spec
        for node in _walk(root):
            if node.type in spec.function_nodes:
                self._check_function(node)

    def _check_function(self, node: Node) -> None:
        assert node is not None
        assert isinstance(node.type, str)
        spec = self.spec
        name_node = spec.name_of(node)
        if name_node is None:
            return  # anonymous functions/lambdas are not checked
        func_name = node_text(name_node)
        name_range = _range_of(name_node)

        line_count = node.end_point[0] - node.start_point[0] + 1
        assert_count = self._count_asserts(node)
        self.stats.append(FunctionStat(func_name, node.start_point[0] + 1, line_count, assert_count))

        if self._is_recursive(node, func_name):
            self._add(
                name_range,
                f"Recursive call to '{func_name}' (NASA01: no recursion)",
                "NASA01-B",
            )

        if line_count >= MAX_FUNCTION_LINES:
            self._add(
                name_range,
                f"Function '{func_name}' longer than {MAX_FUNCTION_LINES} lines (NASA04)",
                "NASA04",
            )

        if spec.check_asserts and assert_count < MIN_ASSERTS_PER_FUNCTION:
            self._add(
                name_range,
                (
                    f"Function '{func_name}' has only {assert_count} assert(s); "
                    f"expected at least {MIN_ASSERTS_PER_FUNCTION} (NASA05)"
                ),
                "NASA05",
            )

    def _count_asserts(self, node: Node) -> int:
        assert node is not None
        assert isinstance(node.type, str)
        spec = self.spec
        return sum(1 for sub in _walk_within_scope(node, spec) if spec.is_assert(sub))

    def _is_recursive(self, node: Node, func_name: str) -> bool:
        assert node is not None
        assert func_name
        spec = self.spec
        for sub in _walk_within_scope(node, spec):
            if sub.type in spec.call_nodes and direct_callee_name(sub) == func_name:
                return True
        return False


def analyze(text: str, language: str = DEFAULT_LANGUAGE) -> tuple[list[Diagnostic], list[FunctionStat]]:
    """Analyze ``text`` against the NASA Power of 10 rules.

    ``language`` selects the rule set and grammar; it defaults to Python so that
    existing callers are unaffected. Unknown languages, unparseable sources, and
    empty input all yield no diagnostics.
    """
    assert isinstance(text, str)
    assert isinstance(language, str)
    if not text.strip():
        return [], []

    spec = SPECS.get(language)
    if spec is None:
        return [], []

    parser = get_parser(language)
    if parser is None:  # pragma: no cover - grammar unavailable at runtime
        return [], []

    tree = parser.parse(text.encode("utf-8"))
    if tree.root_node.has_error:
        return [], []

    analysis = _Analysis(spec)
    analysis.check_global_rules(tree.root_node)
    analysis.check_functions(tree.root_node)
    return analysis.diagnostics, analysis.stats
