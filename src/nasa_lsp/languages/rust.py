"""Rust language spec. ``assert!``/``assert_eq!`` macros count toward density."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from nasa_lsp.languages._nodes import is_truthy_literal, make_macro_assert
from nasa_lsp.languages.spec import LanguageSpec

if TYPE_CHECKING:
    from tree_sitter import Node

_ASSERT_MACROS: Final = frozenset(
    {"assert", "assert_eq", "assert_ne", "debug_assert", "debug_assert_eq", "debug_assert_ne"}
)


def _loop(node: Node) -> str | None:
    assert node is not None
    assert isinstance(node.type, str)
    if node.type == "loop_expression":
        return "loop"
    if node.type == "while_expression" and is_truthy_literal(node.child_by_field_name("condition")):
        return "while true"
    return None


SPEC: Final = LanguageSpec(
    name="rust",
    extensions=frozenset({".rs"}),
    function_nodes=frozenset({"function_item"}),
    scope_nodes=frozenset({"function_item", "impl_item", "trait_item", "closure_expression"}),
    call_nodes=frozenset({"call_expression"}),
    forbidden_calls=frozenset(),
    unbounded_loop=_loop,
    is_assert=make_macro_assert(_ASSERT_MACROS),
)
