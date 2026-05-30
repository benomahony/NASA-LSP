"""C++ language spec (reuses C's name/loop helpers)."""

from __future__ import annotations

from typing import Final

from nasa_lsp.languages._nodes import make_call_assert
from nasa_lsp.languages.c import c_loop, c_name
from nasa_lsp.languages.spec import LanguageSpec

_FORBIDDEN: Final = frozenset({"gets", "longjmp", "setjmp"})

SPEC: Final = LanguageSpec(
    name="cpp",
    extensions=frozenset({".cpp", ".cc", ".cxx", ".hpp", ".hh", ".hxx"}),
    function_nodes=frozenset({"function_definition"}),
    scope_nodes=frozenset({"function_definition", "class_specifier", "struct_specifier"}),
    call_nodes=frozenset({"call_expression"}),
    forbidden_calls=_FORBIDDEN,
    name_of=c_name,
    unbounded_loop=c_loop,
    is_assert=make_call_assert(frozenset({"assert"})),
)
