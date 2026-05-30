"""The :class:`LanguageSpec` that ties a grammar to the Power of 10 rule engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from nasa_lsp.languages._nodes import field_name, never_assert

if TYPE_CHECKING:
    from collections.abc import Callable

    from tree_sitter import Node


@dataclass(frozen=True)
class LanguageSpec:
    """Describes how one language maps onto the NASA Power of 10 rule engine.

    Attributes:
        name: tree-sitter language name (also the parser key).
        extensions: file extensions (with leading dot) that select this language.
        function_nodes: node types treated as functions for the per-function rules.
        scope_nodes: node types that bound a scope (functions, classes, …); the
            analyzer does not descend into nested scopes when counting a
            function's own assertions or recursion.
        call_nodes: node types representing a call expression.
        forbidden_calls: callee names banned by NASA01-A.
        name_of: extracts a function's name node.
        unbounded_loop: returns a label if the node is an unbounded loop, else None.
        is_assert: whether a node is an assertion (for NASA05 density).
        check_asserts: whether NASA05 applies to this language.
    """

    name: str
    extensions: frozenset[str]
    function_nodes: frozenset[str]
    scope_nodes: frozenset[str]
    call_nodes: frozenset[str]
    forbidden_calls: frozenset[str]
    name_of: Callable[[Node], Node | None] = field_name
    unbounded_loop: Callable[[Node], str | None] = field(default=lambda _node: None)
    is_assert: Callable[[Node], bool] = never_assert
    check_asserts: bool = True
