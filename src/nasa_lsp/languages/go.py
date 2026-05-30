"""Go language spec. Go has no idiomatic assertion, so NASA05 is disabled."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from nasa_lsp.languages._nodes import is_truthy_literal
from nasa_lsp.languages.spec import LanguageSpec

if TYPE_CHECKING:
    from tree_sitter import Node


def _loop(node: Node) -> str | None:
    assert node is not None
    assert isinstance(node.type, str)
    if node.type != "for_statement":
        return None
    spec_children = [c for c in node.named_children if c.type != "block"]
    if not spec_children:
        return "for {}"
    if len(spec_children) == 1 and is_truthy_literal(spec_children[0]):
        return "for true {}"
    return None


SPEC: Final = LanguageSpec(
    name="go",
    extensions=frozenset({".go"}),
    function_nodes=frozenset({"function_declaration", "method_declaration"}),
    scope_nodes=frozenset({"function_declaration", "method_declaration", "func_literal"}),
    call_nodes=frozenset({"call_expression"}),
    forbidden_calls=frozenset(),
    unbounded_loop=_loop,
    check_asserts=False,
)
