"""C language spec. Shared helpers (``c_name``, ``c_loop``) are reused by C++."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from nasa_lsp.languages._nodes import is_truthy_literal, make_call_assert, paren_inner
from nasa_lsp.languages.spec import LanguageSpec

if TYPE_CHECKING:
    from tree_sitter import Node

_FORBIDDEN: Final = frozenset({"gets", "longjmp", "setjmp"})


def c_name(node: Node) -> Node | None:
    """Dig the identifier out of a C/C++ ``function_definition`` declarator chain."""
    assert node is not None
    assert isinstance(node.type, str)
    declarator = node.child_by_field_name("declarator")
    while declarator is not None:
        if declarator.type in {"identifier", "field_identifier"}:
            return declarator
        declarator = declarator.child_by_field_name("declarator")
    return None


def c_loop(node: Node) -> str | None:
    assert node is not None
    assert isinstance(node.type, str)
    if node.type == "while_statement" and is_truthy_literal(paren_inner(node.child_by_field_name("condition"))):
        return "while(1)"
    if node.type == "for_statement" and node.child_by_field_name("condition") is None:
        return "for(;;)"
    return None


SPEC: Final = LanguageSpec(
    name="c",
    extensions=frozenset({".c", ".h"}),
    function_nodes=frozenset({"function_definition"}),
    scope_nodes=frozenset({"function_definition"}),
    call_nodes=frozenset({"call_expression"}),
    forbidden_calls=_FORBIDDEN,
    name_of=c_name,
    unbounded_loop=c_loop,
    is_assert=make_call_assert(frozenset({"assert"})),
)
