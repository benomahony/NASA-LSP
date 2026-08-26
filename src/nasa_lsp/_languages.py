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
            references, so calls must be recovered from a supplemental query.
        function_query: a query that captures function definitions, used instead
            of the tags query when the bundled one does not target real function
            bodies (TypeScript's, for instance, only matches ambient signatures).
            It must capture ``@definition.function``/``@definition.method`` and
            ``@name``, exactly like a tags query.
    """

    name: str
    extensions: frozenset[str]
    function_types: frozenset[str]
    forbidden_calls: frozenset[str] = field(default_factory=frozenset)
    assert_names: frozenset[str] = field(default_factory=frozenset)
    tags_lack_calls: bool = False
    function_query: str | None = None


# TypeScript's bundled tags query only matches ambient signatures, so real
# function bodies need an explicit query against the same grammar.
_TS_FUNCTION_QUERY: Final = (
    "[(function_declaration name: (identifier) @name)"
    " (method_definition name: (property_identifier) @name)] @definition.function"
)


_C_FORBIDDEN: Final = frozenset({"gets", "longjmp", "setjmp"})

_LANGUAGES: Final[tuple[Language, ...]] = (
    Language(name="python", extensions=frozenset({".py", ".pyi"}), function_types=frozenset({"function_definition"})),
    Language(
        name="c",
        extensions=frozenset({".c", ".h"}),
        function_types=frozenset({"function_definition"}),
        forbidden_calls=_C_FORBIDDEN,
        assert_names=frozenset({"assert"}),
        tags_lack_calls=True,
    ),
    Language(
        name="cpp",
        extensions=frozenset({".cpp", ".cc", ".cxx", ".hpp", ".hh"}),
        function_types=frozenset({"function_definition"}),
        forbidden_calls=_C_FORBIDDEN,
        assert_names=frozenset({"assert"}),
    ),
    Language(
        name="rust",
        extensions=frozenset({".rs"}),
        function_types=frozenset({"function_item"}),
        assert_names=frozenset({"assert", "assert_eq", "assert_ne", "debug_assert"}),
    ),
    Language(
        name="go",
        extensions=frozenset({".go"}),
        function_types=frozenset({"function_declaration", "method_declaration"}),
    ),
    Language(
        name="javascript",
        extensions=frozenset({".js", ".mjs", ".cjs", ".jsx"}),
        function_types=frozenset({"function_declaration", "method_definition"}),
        assert_names=frozenset({"assert"}),
    ),
    Language(
        name="typescript",
        extensions=frozenset({".ts", ".tsx"}),
        function_types=frozenset({"function_declaration", "method_definition"}),
        assert_names=frozenset({"assert"}),
        tags_lack_calls=True,
        function_query=_TS_FUNCTION_QUERY,
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
