"""Python language spec for the NASA Power of 10 analyzer."""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from nasa_lsp.languages.spec import LanguageSpec

if TYPE_CHECKING:
    from tree_sitter import Node

_FORBIDDEN: Final = frozenset({"eval", "exec", "compile", "globals", "locals", "__import__", "setattr", "getattr"})


def _loop(node: Node) -> str | None:
    assert node is not None
    assert isinstance(node.type, str)
    if node.type == "while_statement":
        cond = node.child_by_field_name("condition")
        if cond is not None and cond.type == "true":
            return "while True"
    return None


def _is_assert(node: Node) -> bool:
    assert node is not None
    assert isinstance(node.type, str)
    return node.type == "assert_statement"


SPEC: Final = LanguageSpec(
    name="python",
    extensions=frozenset({".py", ".pyi"}),
    function_nodes=frozenset({"function_definition"}),
    scope_nodes=frozenset({"function_definition", "class_definition", "lambda"}),
    call_nodes=frozenset({"call"}),
    forbidden_calls=_FORBIDDEN,
    unbounded_loop=_loop,
    is_assert=_is_assert,
)
