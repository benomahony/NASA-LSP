"""JavaScript language spec. Shared function/loop helpers are reused by TypeScript."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from nasa_lsp.languages._nodes import is_truthy_literal, paren_inner
from nasa_lsp.languages.spec import LanguageSpec

if TYPE_CHECKING:
    from tree_sitter import Node

FORBIDDEN: Final = frozenset({"eval", "Function"})

FUNCTION_NODES: Final = frozenset(
    {
        "function_declaration",
        "function_expression",
        "generator_function_declaration",
        "generator_function",
        "arrow_function",
        "method_definition",
    }
)
SCOPE_NODES: Final = FUNCTION_NODES | {"class_declaration", "class"}


def js_loop(node: Node) -> str | None:
    assert node is not None
    assert isinstance(node.type, str)
    if node.type == "while_statement" and is_truthy_literal(paren_inner(node.child_by_field_name("condition"))):
        return "while (true)"
    if node.type == "for_statement":
        # for(;;) has no real condition: the field is absent or an empty statement.
        condition = node.child_by_field_name("condition")
        if condition is None or condition.type == "empty_statement":
            return "for (;;)"
    return None


SPEC: Final = LanguageSpec(
    name="javascript",
    extensions=frozenset({".js", ".mjs", ".cjs", ".jsx"}),
    function_nodes=FUNCTION_NODES,
    scope_nodes=SCOPE_NODES,
    call_nodes=frozenset({"call_expression"}),
    forbidden_calls=FORBIDDEN,
    unbounded_loop=js_loop,
    check_asserts=False,
)
