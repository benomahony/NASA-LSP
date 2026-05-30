"""Language-specific configuration for the NASA Power of 10 analyzer.

Every supported language is described by a :class:`LanguageSpec` that tells the
generic rule engine in :mod:`nasa_lsp.analyzer` how to recognise the syntactic
constructs the rules care about (functions, calls, loops, assertions). The rule
logic itself lives in the analyzer and operates on standard tree-sitter nodes,
so adding a language is a matter of describing it here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from collections.abc import Callable

    from tree_sitter import Node

_NAME_NODE_TYPES: Final = frozenset({"identifier", "field_identifier", "property_identifier", "type_identifier"})
_NAME_FIELDS: Final = ("attribute", "field", "property", "name")


def node_text(node: Node) -> str:
    assert node is not None
    assert isinstance(node.type, str)
    return node.text.decode("utf-8", "replace") if node.text is not None else ""


# --- name extraction -------------------------------------------------------


def _field_name(node: Node) -> Node | None:
    """Return the ``name`` field node (works for most C-family/script grammars)."""
    assert node is not None
    assert isinstance(node.type, str)
    return node.child_by_field_name("name")


def _c_name(node: Node) -> Node | None:
    """Dig the identifier out of a C/C++ ``function_definition`` declarator chain."""
    assert node is not None
    assert isinstance(node.type, str)
    declarator = node.child_by_field_name("declarator")
    while declarator is not None:
        if declarator.type in {"identifier", "field_identifier"}:
            return declarator
        declarator = declarator.child_by_field_name("declarator")
    return None


# --- callee extraction -----------------------------------------------------


def direct_callee_name(call: Node) -> str | None:
    """Name of a call whose callee is a bare identifier (used for recursion).

    Mirrors the original Python behaviour of only treating ``foo()`` as a
    recursive call, never ``obj.foo()``.
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


def _simple_name(node: Node) -> str | None:
    """Resolve a callee node to its simple name, following member/scope fields.

    Iterative (no recursion) to comply with the project's own Power of 10 rules.
    """
    assert node is not None
    assert isinstance(node.type, str)
    current: Node | None = node
    while current is not None:
        if current.type in _NAME_NODE_TYPES:
            return node_text(current)
        nxt: Node | None = None
        for fname in _NAME_FIELDS:
            child = current.child_by_field_name(fname)
            if child is not None:
                nxt = child
                break
        current = nxt
    return None


def _macro_name(node: Node) -> str | None:
    """Identifier of a rust ``macro_invocation`` (``assert!`` -> ``assert``)."""
    assert node is not None
    assert isinstance(node.type, str)
    macro = node.child_by_field_name("macro")
    return _simple_name(macro) if macro is not None else None


# --- unbounded-loop detection ----------------------------------------------


def _is_truthy_literal(node: Node | None) -> bool:
    if node is None:
        return False
    assert isinstance(node.type, str)
    text = node_text(node).strip()
    assert isinstance(text, str)
    if node.type in {"true", "boolean_literal"}:
        return text == "true"
    # C uses integer literals as booleans: while(1).
    return node.type == "number_literal" and text not in {"", "0"}


def _paren_inner(node: Node | None) -> Node | None:
    """Inner expression of a ``(...)``/``condition_clause`` wrapper."""
    if node is None:
        return None
    assert isinstance(node.type, str)
    assert node.child_count >= 0
    if node.type in {"parenthesized_expression", "condition_clause"}:
        named = node.named_children
        return named[0] if named else None
    return node


def _py_loop(node: Node) -> str | None:
    assert node is not None
    assert isinstance(node.type, str)
    if node.type == "while_statement":
        cond = node.child_by_field_name("condition")
        if cond is not None and cond.type == "true":
            return "while True"
    return None


def _c_loop(node: Node) -> str | None:
    assert node is not None
    assert isinstance(node.type, str)
    if node.type == "while_statement" and _is_truthy_literal(_paren_inner(node.child_by_field_name("condition"))):
        return "while(1)"
    if node.type == "for_statement" and node.child_by_field_name("condition") is None:
        return "for(;;)"
    return None


def _go_loop(node: Node) -> str | None:
    assert node is not None
    assert isinstance(node.type, str)
    if node.type != "for_statement":
        return None
    spec_children = [c for c in node.named_children if c.type != "block"]
    if not spec_children:
        return "for {}"
    if len(spec_children) == 1 and _is_truthy_literal(spec_children[0]):
        return "for true {}"
    return None


def _rust_loop(node: Node) -> str | None:
    assert node is not None
    assert isinstance(node.type, str)
    if node.type == "loop_expression":
        return "loop"
    if node.type == "while_expression" and _is_truthy_literal(node.child_by_field_name("condition")):
        return "while true"
    return None


def _js_loop(node: Node) -> str | None:
    assert node is not None
    assert isinstance(node.type, str)
    if node.type == "while_statement" and _is_truthy_literal(_paren_inner(node.child_by_field_name("condition"))):
        return "while (true)"
    if node.type == "for_statement":
        # for(;;) has no real condition: the field is absent or an empty statement.
        condition = node.child_by_field_name("condition")
        if condition is None or condition.type == "empty_statement":
            return "for (;;)"
    return None


# --- assertion detection ---------------------------------------------------


def _make_call_assert(names: frozenset[str]) -> Callable[[Node], bool]:
    assert names is not None
    assert isinstance(names, frozenset)

    def predicate(node: Node) -> bool:
        assert node is not None
        assert isinstance(node.type, str)
        return node.type == "call_expression" and resolved_callee_name(node) in names

    return predicate


def _make_macro_assert(names: frozenset[str]) -> Callable[[Node], bool]:
    assert names is not None
    assert isinstance(names, frozenset)

    def predicate(node: Node) -> bool:
        assert node is not None
        assert isinstance(node.type, str)
        return node.type == "macro_invocation" and _macro_name(node) in names

    return predicate


def _py_assert(node: Node) -> bool:
    assert node is not None
    assert isinstance(node.type, str)
    return node.type == "assert_statement"


def _never(node: Node) -> bool:
    assert node is not None
    assert isinstance(node.type, str)
    return False


# --- the spec --------------------------------------------------------------


@dataclass(frozen=True)
class LanguageSpec:
    """Describes how one language maps onto the NASA Power of 10 rule engine."""

    name: str
    function_nodes: frozenset[str]
    scope_nodes: frozenset[str]
    call_nodes: frozenset[str]
    forbidden_calls: frozenset[str]
    name_of: Callable[[Node], Node | None] = _field_name
    unbounded_loop: Callable[[Node], str | None] = field(default=lambda _node: None)
    is_assert: Callable[[Node], bool] = _never
    check_asserts: bool = True


_PY_FORBIDDEN: Final = frozenset({"eval", "exec", "compile", "globals", "locals", "__import__", "setattr", "getattr"})
_JS_FORBIDDEN: Final = frozenset({"eval", "Function"})

_JS_FUNCTIONS: Final = frozenset(
    {
        "function_declaration",
        "function_expression",
        "generator_function_declaration",
        "generator_function",
        "arrow_function",
        "method_definition",
    }
)
_JS_SCOPES: Final = _JS_FUNCTIONS | {"class_declaration", "class"}

SPECS: Final[dict[str, LanguageSpec]] = {
    "python": LanguageSpec(
        name="python",
        function_nodes=frozenset({"function_definition"}),
        scope_nodes=frozenset({"function_definition", "class_definition", "lambda"}),
        call_nodes=frozenset({"call"}),
        forbidden_calls=_PY_FORBIDDEN,
        unbounded_loop=_py_loop,
        is_assert=_py_assert,
    ),
    "c": LanguageSpec(
        name="c",
        function_nodes=frozenset({"function_definition"}),
        scope_nodes=frozenset({"function_definition"}),
        call_nodes=frozenset({"call_expression"}),
        forbidden_calls=frozenset({"gets", "longjmp", "setjmp"}),
        name_of=_c_name,
        unbounded_loop=_c_loop,
        is_assert=_make_call_assert(frozenset({"assert"})),
    ),
    "cpp": LanguageSpec(
        name="cpp",
        function_nodes=frozenset({"function_definition"}),
        scope_nodes=frozenset({"function_definition", "class_specifier", "struct_specifier"}),
        call_nodes=frozenset({"call_expression"}),
        forbidden_calls=frozenset({"gets", "longjmp", "setjmp"}),
        name_of=_c_name,
        unbounded_loop=_c_loop,
        is_assert=_make_call_assert(frozenset({"assert"})),
    ),
    "go": LanguageSpec(
        name="go",
        function_nodes=frozenset({"function_declaration", "method_declaration"}),
        scope_nodes=frozenset({"function_declaration", "method_declaration", "func_literal"}),
        call_nodes=frozenset({"call_expression"}),
        forbidden_calls=frozenset(),
        unbounded_loop=_go_loop,
        check_asserts=False,
    ),
    "rust": LanguageSpec(
        name="rust",
        function_nodes=frozenset({"function_item"}),
        scope_nodes=frozenset({"function_item", "impl_item", "trait_item", "closure_expression"}),
        call_nodes=frozenset({"call_expression"}),
        forbidden_calls=frozenset(),
        unbounded_loop=_rust_loop,
        is_assert=_make_macro_assert(
            frozenset({"assert", "assert_eq", "assert_ne", "debug_assert", "debug_assert_eq", "debug_assert_ne"})
        ),
    ),
    "javascript": LanguageSpec(
        name="javascript",
        function_nodes=_JS_FUNCTIONS,
        scope_nodes=_JS_SCOPES,
        call_nodes=frozenset({"call_expression"}),
        forbidden_calls=_JS_FORBIDDEN,
        unbounded_loop=_js_loop,
        check_asserts=False,
    ),
    "typescript": LanguageSpec(
        name="typescript",
        function_nodes=_JS_FUNCTIONS,
        scope_nodes=_JS_SCOPES,
        call_nodes=frozenset({"call_expression"}),
        forbidden_calls=_JS_FORBIDDEN,
        unbounded_loop=_js_loop,
        check_asserts=False,
    ),
}


# --- language detection ----------------------------------------------------

_EXTENSION_MAP: Final[dict[str, str]] = {
    ".py": "python",
    ".pyi": "python",
    ".c": "c",
    ".h": "c",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".cxx": "cpp",
    ".hpp": "cpp",
    ".hh": "cpp",
    ".hxx": "cpp",
    ".go": "go",
    ".rs": "rust",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

#: File extensions the linter will discover when scanning directories.
SUPPORTED_EXTENSIONS: Final = frozenset(_EXTENSION_MAP)


def language_for_suffix(suffix: str) -> str | None:
    """Map a file extension (including the leading dot) to a supported language."""
    assert isinstance(suffix, str)
    assert "/" not in suffix
    return _EXTENSION_MAP.get(suffix.lower())
