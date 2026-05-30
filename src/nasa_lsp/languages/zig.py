"""Zig language spec.

Zig spells its infinite loop ``while (true) {}`` (the condition is a bare
``boolean`` node, not a parenthesized expression), and its idiomatic assertions
are ``std.debug.assert`` / ``std.testing.expect`` calls.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from nasa_lsp.languages._nodes import is_truthy_literal, make_call_assert
from nasa_lsp.languages.spec import LanguageSpec

if TYPE_CHECKING:
    from tree_sitter import Node

_ASSERTS: Final = frozenset({"assert", "expect"})


def _loop(node: Node) -> str | None:
    assert node is not None
    assert isinstance(node.type, str)
    if node.type == "while_statement" and is_truthy_literal(node.child_by_field_name("condition")):
        return "while (true)"
    return None


SPEC: Final = LanguageSpec(
    name="zig",
    extensions=frozenset({".zig"}),
    function_nodes=frozenset({"function_declaration"}),
    scope_nodes=frozenset({"function_declaration", "test_declaration"}),
    call_nodes=frozenset({"call_expression"}),
    forbidden_calls=frozenset(),
    unbounded_loop=_loop,
    is_assert=make_call_assert(_ASSERTS),
)
