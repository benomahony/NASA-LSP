"""Language registry for the tree-sitter based, language-agnostic engine.

Each supported non-Python language is described by a small :class:`Language`
record: the file extensions that select it, the grammar node types that count as
a function (used for the length rule and to bound a function's scope), the APIs
banned under NASA01, and the callee names that act as assertions. Everything else
the engine needs -- where functions and calls live in the tree, and their names
-- is read generically from the grammar's bundled tree-sitter ``tags`` query, so
adding a language is a matter of data, not new traversal code.

Python is listed here only so its extensions map to the name ``"python"``; the
Python rules themselves keep running through the original ``ast`` analyzer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

DEFAULT_LANGUAGE: Final = "python"


@dataclass(frozen=True)
class Language:
    """A grammar's mapping onto the portable subset of the Power of 10 rules.

    Attributes:
        name: tree-sitter language name (also the parser/query key).
        extensions: file suffixes (with leading dot) that select this language.
        function_types: node types that are a whole function; a function's line
            count and scope are measured from the nearest such ancestor.
        forbidden_calls: callee names banned by NASA01-forbidden-api.
        assert_names: callee names treated as assertions for NASA05 density; an
            empty set disables the density rule for the language.
        tags_lack_calls: True when the grammar's tags query omits call
            references, so calls are recovered from a generic C-style fallback.
        call_query: a query capturing calls as ``@reference.call`` with a
            ``@name``, for a grammar whose calls the tags query cannot supply and
            the C-style fallback does not fit (Zig). Takes precedence over both.
        function_query: a query that captures function definitions, used instead
            of the tags query when the bundled one does not target real function
            bodies (TypeScript's, for instance, only matches ambient signatures).
            It must capture ``@definition.function``/``@definition.method`` and
            ``@name``, exactly like a tags query.
        allocation_names: callee names that allocate heap memory, banned by
            NASA03. This is allocation only, not deallocation: Rule 3 forbids
            dynamic allocation, so ``free`` and ``delete`` are not listed. Empty
            disables the rule for a managed-memory language (Python, Go, JS).
        allocation_query: a query capturing allocation expressions that are not
            plain calls -- C++ ``new``, Rust ``Box::new`` / ``vec!`` -- as
            ``@alloc`` (also NASA03); None if the language allocates only through
            named functions. When ``allocation_scoped``/``allocation_macros`` are
            both empty every ``@alloc`` is reported (C++ ``new``); otherwise a
            match is reported only when it passes one of those filters, which lets
            the query capture broadly and the data decide (Rust).
        allocation_scoped: ``Type::method`` allocators (from a query's ``@type``
            and ``@method`` captures) that count as heap allocation -- Rust's
            ``Box::new``, ``Vec::with_capacity``, and so on.
        allocation_macros: macro names (a query's ``@macro`` capture) that
            allocate -- Rust's ``vec!``.
        unbounded_loop_query: a query capturing loops with no fixed bound as
            ``@loop`` (NASA02); None disables the rule for the language.
        goto_query: a query capturing goto statements as ``@goto``
            (NASA01-goto); None for languages without goto.
    """

    name: str
    extensions: frozenset[str]
    function_types: frozenset[str]
    forbidden_calls: frozenset[str] = field(default_factory=frozenset)
    assert_names: frozenset[str] = field(default_factory=frozenset)
    tags_lack_calls: bool = False
    call_query: str | None = None
    function_query: str | None = None
    allocation_names: frozenset[str] = field(default_factory=frozenset)
    allocation_query: str | None = None
    allocation_scoped: frozenset[str] = field(default_factory=frozenset)
    allocation_macros: frozenset[str] = field(default_factory=frozenset)
    unbounded_loop_query: str | None = None
    goto_query: str | None = None


# TypeScript's bundled tags query only matches ambient signatures, so real
# function bodies need an explicit query against the same grammar.
_TS_FUNCTION_QUERY: Final = (
    "[(function_declaration name: (identifier) @name)"
    " (method_definition name: (property_identifier) @name)] @definition.function"
)


_C_FORBIDDEN: Final = frozenset({"gets", "longjmp", "setjmp"})
# goto is a goto_statement in C, C++, and Go alike.
_GOTO_QUERY: Final = "(goto_statement) @goto"
# Allocation only -- Rule 3 forbids allocating, so free/delete are not listed.
_C_ALLOC: Final = frozenset({"malloc", "calloc", "realloc", "reallocarray", "aligned_alloc", "valloc"})

# Unbounded loops: a constant-condition while, or a for with no condition clause.
# C wraps the while condition in a parenthesized_expression; C++ in a condition_clause.
_C_LOOP: Final = (
    "[(while_statement condition: (parenthesized_expression [(number_literal) (true)]))"
    " (for_statement !condition)] @loop"
)
_CPP_LOOP: Final = (
    "[(while_statement condition: (condition_clause value: [(number_literal) (true)]))"
    " (for_statement !condition)] @loop"
)
_RUST_LOOP: Final = "[(loop_expression) (while_expression condition: (boolean_literal))] @loop"

# Rust heap allocation: qualified constructors (Box::new, Vec::with_capacity, ...)
# and the vec! macro. The query captures the type, method, and macro name; the
# scoped/macro sets below decide which are allocations.
_RUST_ALLOC_QUERY: Final = (
    "[(call_expression function: (scoped_identifier"
    " path: [(identifier) @type (generic_type type: (type_identifier) @type)]"
    " name: (identifier) @method))"
    " (macro_invocation macro: (identifier) @macro)] @alloc"
)
_RUST_ALLOC_SCOPED: Final = frozenset(
    {
        "Box::new",
        "Box::from",
        "Vec::new",
        "Vec::with_capacity",
        "Vec::from",
        "String::new",
        "String::from",
        "String::with_capacity",
        "Rc::new",
        "Arc::new",
        "VecDeque::new",
        "VecDeque::with_capacity",
        "HashMap::new",
        "BTreeMap::new",
        "HashSet::new",
        "BTreeSet::new",
    }
)
_RUST_ALLOC_MACROS: Final = frozenset({"vec"})
_JS_LOOP: Final = (
    "[(while_statement condition: (parenthesized_expression (true)))"
    " (for_statement condition: (empty_statement))] @loop"
)

# Zig ships no tags query, so functions and calls need explicit queries. Calls
# come in two shapes: a bare call (SuffixExpr + args) and a method call
# (FieldOrFnCall + args); the name is the identifier that precedes the args.
_ZIG_FUNCTION_QUERY: Final = "(Decl (FnProto (IDENTIFIER) @name)) @definition.function"
_ZIG_CALL_QUERY: Final = (
    "[(SuffixExpr (IDENTIFIER) @name (FnCallArguments))"
    " (FieldOrFnCall (IDENTIFIER) @name (FnCallArguments))] @reference.call"
)
_ZIG_LOOP: Final = '(WhileStatement (WhilePrefix (ErrorUnionExpr (SuffixExpr ("true"))))) @loop'

_LANGUAGES: Final[tuple[Language, ...]] = (
    Language(name="python", extensions=frozenset({".py", ".pyi"}), function_types=frozenset({"function_definition"})),
    Language(
        name="c",
        extensions=frozenset({".c", ".h"}),
        function_types=frozenset({"function_definition"}),
        forbidden_calls=_C_FORBIDDEN,
        assert_names=frozenset({"assert"}),
        tags_lack_calls=True,
        allocation_names=_C_ALLOC,
        unbounded_loop_query=_C_LOOP,
        goto_query=_GOTO_QUERY,
    ),
    Language(
        name="cpp",
        extensions=frozenset({".cpp", ".cc", ".cxx", ".hpp", ".hh"}),
        function_types=frozenset({"function_definition"}),
        forbidden_calls=_C_FORBIDDEN,
        assert_names=frozenset({"assert"}),
        allocation_names=_C_ALLOC,
        allocation_query="(new_expression) @alloc",
        unbounded_loop_query=_CPP_LOOP,
        goto_query=_GOTO_QUERY,
    ),
    Language(
        name="rust",
        extensions=frozenset({".rs"}),
        function_types=frozenset({"function_item"}),
        assert_names=frozenset({"assert", "assert_eq", "assert_ne", "debug_assert"}),
        allocation_query=_RUST_ALLOC_QUERY,
        allocation_scoped=_RUST_ALLOC_SCOPED,
        allocation_macros=_RUST_ALLOC_MACROS,
        unbounded_loop_query=_RUST_LOOP,
    ),
    Language(
        name="go",
        extensions=frozenset({".go"}),
        function_types=frozenset({"function_declaration", "method_declaration"}),
        goto_query=_GOTO_QUERY,
    ),
    Language(
        name="javascript",
        extensions=frozenset({".js", ".mjs", ".cjs", ".jsx"}),
        function_types=frozenset({"function_declaration", "method_definition"}),
        unbounded_loop_query=_JS_LOOP,
        assert_names=frozenset({"assert"}),
    ),
    Language(
        name="typescript",
        extensions=frozenset({".ts", ".tsx"}),
        function_types=frozenset({"function_declaration", "method_definition"}),
        assert_names=frozenset({"assert"}),
        tags_lack_calls=True,
        function_query=_TS_FUNCTION_QUERY,
        unbounded_loop_query=_JS_LOOP,
    ),
    Language(
        name="zig",
        extensions=frozenset({".zig"}),
        function_types=frozenset({"Decl"}),
        assert_names=frozenset({"assert"}),
        call_query=_ZIG_CALL_QUERY,
        function_query=_ZIG_FUNCTION_QUERY,
        allocation_names=frozenset({"alloc", "create", "realloc", "dupe"}),
        unbounded_loop_query=_ZIG_LOOP,
    ),
)

#: Every language record, keyed by tree-sitter language name.
LANGUAGES: Final[dict[str, Language]] = {lang.name: lang for lang in _LANGUAGES}

_EXTENSION_MAP: Final[dict[str, str]] = {ext: lang.name for lang in _LANGUAGES for ext in lang.extensions}

#: File extensions the linter discovers when scanning directories.
SUPPORTED_EXTENSIONS: Final = frozenset(_EXTENSION_MAP)


def language_for_path(file_path: Path | None) -> str:
    """Pick a language for ``file_path``; falls back to Python for back-compat.

    Callers with no path -- or a path whose suffix is not recognised -- get the
    default (Python), so existing behaviour is unchanged; a recognised non-Python
    suffix selects that language instead.
    """
    if file_path is None:
        return DEFAULT_LANGUAGE
    assert DEFAULT_LANGUAGE in LANGUAGES, "default language must be registered"
    assert _EXTENSION_MAP, "the extension map must be populated"
    return _EXTENSION_MAP.get(file_path.suffix.lower(), DEFAULT_LANGUAGE)
