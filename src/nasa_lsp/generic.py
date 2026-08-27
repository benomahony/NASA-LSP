"""Language-agnostic Power of 10 engine over tree-sitter.

This engine covers the portable subset of the rules -- the ones that need only a
notion of *function*, *call*, and *name*, all of which come from the grammar's
bundled tree-sitter ``tags`` query rather than any hand-written per-language
traversal:

* NASA01-forbidden-api -- a call to a banned API.
* NASA01-recursion     -- a function that calls itself directly.
* NASA04               -- a function longer than the line budget.
* NASA05               -- too few assertions in a function (only where the
                          language declares an assertion idiom).

The deeper, Python-specific assertion-quality rules stay in the ``ast`` analyzer;
this engine is what every non-Python file runs through. Diagnostics and stats use
the same public dataclasses as the Python path, so callers cannot tell which
engine produced a result.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from nasa_lsp._languages import LANGUAGES
from nasa_lsp._parsers import compile_query, parse, run_query, tags_query
from nasa_lsp._types import (
    MAX_FUNCTION_LINES,
    MIN_ASSERTS_PER_FUNCTION,
    Diagnostic,
    FunctionStat,
    Position,
    Range,
)

if TYPE_CHECKING:
    from tree_sitter import Node

    from nasa_lsp._languages import Language

# Recovers direct-identifier calls for grammars whose tags query omits them.
_CALL_FALLBACK_QUERY: Final = "(call_expression function: (identifier) @name) @reference.call"

_FUNCTION_CAPTURES: Final = ("definition.function", "definition.method")

# Ceiling on the parent walk from a tags definition node to its whole function.
MAX_ASCENT: Final = 40


def _text(node: Node) -> str:
    assert node is not None, "node must not be None"
    assert node.type, "a tree-sitter node always has a type"
    return node.text.decode("utf-8", "replace") if node.text is not None else ""


def _alloc_label(captures: dict[str, list[Node]]) -> str:
    """A short name for an allocation match: ``vec!``, ``Box::new``, or ``new``."""
    assert captures is not None, "captures must not be None"
    assert "alloc" in captures, "an allocation match must capture @alloc"
    macro = captures.get("macro")
    if macro:
        return f"{_text(macro[0])}!"
    types = captures.get("type")
    methods = captures.get("method")
    if types and methods:
        return f"{_text(types[0])}::{_text(methods[0])}"
    tokens = _text(captures["alloc"][0]).split()
    return tokens[0] if tokens else captures["alloc"][0].type


def _position(row: int, column: int) -> Position:
    assert row >= 0, "row must be non-negative"
    assert column >= 0, "column must be non-negative"
    return Position(line=row, character=column)


def _range_of(node: Node) -> Range:
    assert node is not None, "node must not be None"
    assert node.start_byte <= node.end_byte, "a node's range must be well-formed"
    start_row, start_col = node.start_point
    end_row, end_col = node.end_point
    return Range(start=_position(start_row, start_col), end=_position(end_row, end_col))


def _enclosing_function(node: Node, function_types: frozenset[str]) -> Node | None:
    """Climb from a tags definition node to the whole-function node above it.

    The tags query often anchors a definition to a declarator or signature (C's
    ``function_declarator``, for example); the length and scope rules need the
    full function node, so walk up to the nearest ancestor of a function type.
    """
    assert node is not None, "node must not be None"
    assert function_types, "function_types must not be empty"
    current: Node | None = node
    for _step in range(MAX_ASCENT):
        if current is None or current.type in function_types:
            return current
        current = current.parent
    return None


class _Call:
    """A resolved call site: the node and the simple name of its callee."""

    def __init__(self, node: Node, name: str) -> None:
        assert node is not None, "call node must not be None"
        assert name, "call name must not be empty"
        self.node: Node = node
        self.name: str = name


class _Function:
    """A function found in the tree: its whole-function node and its name node."""

    def __init__(self, node: Node, name_node: Node) -> None:
        assert node is not None, "function node must not be None"
        assert name_node is not None, "name node must not be None"
        self.node: Node = node
        self.name_node: Node = name_node
        self.name: str = _text(name_node)


def _collect_calls(root: Node, language: Language) -> list[_Call]:
    """All call sites under ``root`` with a resolvable simple callee name."""
    assert root is not None, "root must not be None"
    assert language is not None, "language must not be None"
    calls: list[_Call] = []
    for captures in _call_matches(root, language):
        nodes = captures.get("reference.call")
        names = captures.get("name")
        if nodes and names:
            calls.append(_Call(nodes[0], _text(names[0])))
    return calls


def _call_matches(root: Node, language: Language) -> list[dict[str, list[Node]]]:
    """Query matches that expose call references for ``language``."""
    assert root is not None, "root must not be None"
    assert language is not None, "language must not be None"
    if language.call_query is not None:
        return run_query(compile_query(language.name, language.call_query), root)
    if language.tags_lack_calls:
        return run_query(compile_query(language.name, _CALL_FALLBACK_QUERY), root)
    query = tags_query(language.name)
    return run_query(query, root) if query is not None else []


def _collect_functions(root: Node, language: Language) -> list[_Function]:
    """All named functions under ``root``, paired with their name node."""
    assert root is not None, "root must not be None"
    assert language is not None, "language must not be None"
    query = (
        compile_query(language.name, language.function_query)
        if language.function_query is not None
        else tags_query(language.name)
    )
    if query is None:
        return []
    functions: list[_Function] = []
    seen: set[int] = set()
    for captures in run_query(query, root):
        function = _function_from_match(captures, language)
        if function is not None and function.node.id not in seen:
            seen.add(function.node.id)
            functions.append(function)
    return functions


def _function_from_match(captures: dict[str, list[Node]], language: Language) -> _Function | None:
    """Turn one tags match into a :class:`_Function`, if it defines one."""
    assert captures is not None, "captures must not be None"
    assert language is not None, "language must not be None"
    definition = _first_capture(captures, _FUNCTION_CAPTURES)
    names = captures.get("name")
    if definition is None or not names:
        return None
    whole = _enclosing_function(definition, language.function_types)
    return _Function(whole, names[0]) if whole is not None else None


def _first_capture(captures: dict[str, list[Node]], keys: tuple[str, ...]) -> Node | None:
    assert captures is not None, "captures must not be None"
    assert keys, "keys must not be empty"
    for key in keys:
        nodes = captures.get(key)
        if nodes:
            return nodes[0]
    return None


def _within(node: Node, container: Node) -> bool:
    """Whether ``node`` lies inside ``container``'s byte range but is not it."""
    assert node is not None, "node must not be None"
    assert container is not None, "container must not be None"
    if node.id == container.id:
        return False
    return container.start_byte <= node.start_byte and node.end_byte <= container.end_byte


class _Analysis:
    def __init__(self, language: Language, enabled_rules: frozenset[str]) -> None:
        assert language is not None, "language must not be None"
        assert enabled_rules is not None, "enabled_rules must not be None"
        self.language: Language = language
        self.enabled: frozenset[str] = enabled_rules
        self.diagnostics: list[Diagnostic] = []
        self.stats: list[FunctionStat] = []

    def add(self, rng: Range, message: str, code: str) -> None:
        assert message, "message must not be empty"
        assert code, "code must not be empty"
        if code in self.enabled:
            self.diagnostics.append(Diagnostic(range=rng, message=f"{message} ({code})", code=code))

    def check_calls(self, calls: list[_Call]) -> None:
        assert calls is not None, "calls must not be None"
        assert self.language is not None, "language must be set"
        forbidden = self.language.forbidden_calls
        allocators = self.language.allocation_names
        for call in calls:
            if call.name in forbidden:
                self.add(_range_of(call.node), f"Call to forbidden API '{call.name}'", "NASA01-forbidden-api")
            if call.name in allocators:
                self.add(_range_of(call.node), f"Dynamic memory allocation '{call.name}'", "NASA03")

    def check_allocation_syntax(self, root: Node) -> None:
        assert root is not None, "root must not be None"
        assert self.language is not None, "language must be set"
        query_source = self.language.allocation_query
        if query_source is None:
            return
        query = compile_query(self.language.name, query_source)
        for captures in run_query(query, root):
            alloc = captures.get("alloc")
            if alloc and self._is_allocation(captures):
                self.add(_range_of(alloc[0]), f"Dynamic memory allocation '{_alloc_label(captures)}'", "NASA03")

    def _is_allocation(self, captures: dict[str, list[Node]]) -> bool:
        assert captures is not None, "captures must not be None"
        assert "alloc" in captures, "an allocation match captures @alloc"
        spec = self.language
        if not spec.allocation_scoped and not spec.allocation_macros:
            return True  # an unconditional query (C++ new): every match allocates
        macro = captures.get("macro")
        if macro and _text(macro[0]) in spec.allocation_macros:
            return True
        types = captures.get("type")
        methods = captures.get("method")
        if not types or not methods:
            return False
        return f"{_text(types[0])}::{_text(methods[0])}" in spec.allocation_scoped

    def check_loops(self, root: Node) -> None:
        assert root is not None, "root must not be None"
        assert self.language is not None, "language must be set"
        query_source = self.language.unbounded_loop_query
        if query_source is None:
            return
        query = compile_query(self.language.name, query_source)
        for captures in run_query(query, root):
            for loop in captures.get("loop", []):
                self.add(_range_of(loop), "Unbounded loop; loops must have a fixed bound", "NASA02")

    def check_function(self, function: _Function, calls: list[_Call]) -> None:
        assert function is not None, "function must not be None"
        assert calls is not None, "calls must not be None"
        inner = [call for call in calls if _within(call.node, function.node)]
        assert_count = sum(1 for call in inner if call.name in self.language.assert_names)
        line_count = function.node.end_point[0] - function.node.start_point[0] + 1
        self.stats.append(FunctionStat(function.name, function.node.start_point[0] + 1, line_count, assert_count))
        self._emit_function_rules(function, inner, assert_count, line_count)

    def _emit_function_rules(self, function: _Function, inner: list[_Call], assert_count: int, line_count: int) -> None:
        assert function is not None, "function must not be None"
        assert line_count >= 1, "a function spans at least one line"
        name_range = _range_of(function.name_node)
        if any(call.name == function.name for call in inner):
            self.add(name_range, f"Recursive call to '{function.name}'", "NASA01-recursion")
        if line_count >= MAX_FUNCTION_LINES:
            self.add(name_range, f"Function '{function.name}' longer than {MAX_FUNCTION_LINES} lines", "NASA04")
        if self.language.assert_names and assert_count < MIN_ASSERTS_PER_FUNCTION:
            message = (
                f"Function '{function.name}' has only {assert_count} assert(s); "
                f"expected at least {MIN_ASSERTS_PER_FUNCTION}"
            )
            self.add(name_range, message, "NASA05")


def analyze_generic(
    text: str,
    language: str,
    enabled_rules: frozenset[str],
) -> tuple[list[Diagnostic], list[FunctionStat]]:
    """Analyze ``text`` as a non-Python ``language`` against the portable rules."""
    assert text is not None, "source text must not be None"
    assert language, "language name must not be empty"
    spec = LANGUAGES.get(language)
    if spec is None:
        return [], []
    root = parse(text, language).root_node
    calls = _collect_calls(root, spec)
    analysis = _Analysis(spec, enabled_rules)
    analysis.check_calls(calls)
    analysis.check_allocation_syntax(root)
    analysis.check_loops(root)
    for function in _collect_functions(root, spec):
        analysis.check_function(function, calls)
    return analysis.diagnostics, analysis.stats
