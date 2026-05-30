"""Shared tree-sitter node helpers used by the per-language specs.

These are grammar-agnostic primitives: extracting text and names from nodes,
resolving call targets, recognising truthy literals, and building assertion
predicates. Language-specific logic (which node types are functions, how a
particular grammar shapes its loops) lives in the individual language modules.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

    from tree_sitter import Node

_NAME_NODE_TYPES: Final = frozenset({"identifier", "field_identifier", "property_identifier", "type_identifier"})
_NAME_FIELDS: Final = ("attribute", "field", "property", "name")
_TRUE_LITERAL_TYPES: Final = frozenset({"true", "boolean_literal", "boolean"})


def node_text(node: Node) -> str:
    assert node is not None
    assert isinstance(node.type, str)
    return node.text.decode("utf-8", "replace") if node.text is not None else ""


def field_name(node: Node) -> Node | None:
    """Return the ``name`` field node (works for most C-family/script grammars)."""
    assert node is not None
    assert isinstance(node.type, str)
    return node.child_by_field_name("name")


# --- callee extraction -----------------------------------------------------


def direct_callee_name(call: Node) -> str | None:
    """Name of a call whose callee is a bare identifier (used for recursion).

    Only treats ``foo()`` as a recursive call, never ``obj.foo()``.
    """
    assert call is not None
    assert isinstance(call.type, str)
    func = call.child_by_field_name("function")
    if func is not None and func.type == "identifier":
        return node_text(func)
    return None


def resolved_callee_name(call: Node) -> str | None:
    """Simple name of a call's callee, resolving member/attribute access.

    ``eval()`` and ``obj.eval()`` both resolve to ``"eval"`` so the forbidden-API
    rule catches method calls too.
    """
    assert call is not None
    assert isinstance(call.type, str)
    func = call.child_by_field_name("function")
    if func is None:
        return None
    return _simple_name(func)


def _next_name_node(node: Node) -> Node | None:
    """Step towards the simple name of a member/scoped expression."""
    assert node is not None
    assert isinstance(node.type, str)
    for fname in _NAME_FIELDS:
        child = node.child_by_field_name(fname)
        if child is not None:
            return child
    # Member access without a named field (e.g. zig ``std.debug.assert``):
    # the member is the last identifier child.
    for child in reversed(node.children):
        if child.type in _NAME_NODE_TYPES:
            return child
    return None


def _simple_name(node: Node) -> str | None:
    """Resolve a callee node to its simple name (iterative, no recursion)."""
    assert node is not None
    assert isinstance(node.type, str)
    current: Node | None = node
    while current is not None:
        if current.type in _NAME_NODE_TYPES:
            return node_text(current)
        current = _next_name_node(current)
    return None


def _macro_name(node: Node) -> str | None:
    """Identifier of a rust ``macro_invocation`` (``assert!`` -> ``assert``)."""
    assert node is not None
    assert isinstance(node.type, str)
    macro = node.child_by_field_name("macro")
    return _simple_name(macro) if macro is not None else None


# --- loop-condition primitives ---------------------------------------------


def is_truthy_literal(node: Node | None) -> bool:
    """Whether ``node`` is a literal that always evaluates true (``true``, ``1``)."""
    if node is None:
        return False
    assert isinstance(node.type, str)
    text = node_text(node).strip()
    assert isinstance(text, str)
    if node.type in _TRUE_LITERAL_TYPES:
        return text == "true"
    # C uses integer literals as booleans: while(1).
    return node.type == "number_literal" and text not in {"", "0"}


def paren_inner(node: Node | None) -> Node | None:
    """Inner expression of a ``(...)``/``condition_clause`` wrapper."""
    if node is None:
        return None
    assert isinstance(node.type, str)
    assert node.child_count >= 0
    if node.type in {"parenthesized_expression", "condition_clause"}:
        named = node.named_children
        return named[0] if named else None
    return node


# --- assertion predicates --------------------------------------------------


def make_call_assert(names: frozenset[str]) -> Callable[[Node], bool]:
    """Build an assertion predicate matching calls to one of ``names``."""
    assert names is not None
    assert isinstance(names, frozenset)

    def predicate(node: Node) -> bool:
        assert node is not None
        assert isinstance(node.type, str)
        return node.type == "call_expression" and resolved_callee_name(node) in names

    return predicate


def make_macro_assert(names: frozenset[str]) -> Callable[[Node], bool]:
    """Build an assertion predicate matching rust macros (``assert!`` …)."""
    assert names is not None
    assert isinstance(names, frozenset)

    def predicate(node: Node) -> bool:
        assert node is not None
        assert isinstance(node.type, str)
        return node.type == "macro_invocation" and _macro_name(node) in names

    return predicate


def never_assert(node: Node) -> bool:
    """Default assertion predicate for languages without an assert idiom."""
    assert node is not None
    assert isinstance(node.type, str)
    return False
