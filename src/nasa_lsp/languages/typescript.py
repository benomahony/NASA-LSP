"""TypeScript language spec (reuses JavaScript's function/loop helpers)."""

from __future__ import annotations

from typing import Final

from nasa_lsp.languages.javascript import FORBIDDEN, FUNCTION_NODES, SCOPE_NODES, js_loop
from nasa_lsp.languages.spec import LanguageSpec

SPEC: Final = LanguageSpec(
    name="typescript",
    extensions=frozenset({".ts", ".tsx"}),
    function_nodes=FUNCTION_NODES,
    scope_nodes=SCOPE_NODES,
    call_nodes=frozenset({"call_expression"}),
    forbidden_calls=FORBIDDEN,
    unbounded_loop=js_loop,
    check_asserts=False,
)
