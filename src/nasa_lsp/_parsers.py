"""Tree-sitter parser and query acquisition.

Grammars and their bundled ``tags`` queries come from ``tree-sitter-language-pack``,
which ships pre-compiled parsers for every supported language -- no runtime
download and no per-grammar build step. Parsers and compiled queries are cached
per language, since compiling a query is not free and the same handful are reused
for every file. The rest of the codebase only ever sees standard ``tree_sitter``
objects, so this module is the single point that depends on the pack.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from tree_sitter import Query, QueryCursor

if TYPE_CHECKING:
    from tree_sitter import Node, Parser, Tree

_PARSERS: Final[dict[str, Parser]] = {}
_TAGS_QUERIES: Final[dict[str, Query | None]] = {}
_EXTRA_QUERIES: Final[dict[tuple[str, str], Query]] = {}


def _parser(language: str) -> Parser:
    """Return a cached parser for ``language`` from the language pack."""
    assert language, "language name must not be empty"
    cached = _PARSERS.get(language)
    if cached is not None:
        return cached
    from tree_sitter_language_pack import get_parser  # noqa: PLC0415

    parser = get_parser(language)
    assert parser is not None, "language pack returned no parser"
    _PARSERS[language] = parser
    return parser


def parse(text: str, language: str) -> Tree:
    """Parse ``text`` as ``language`` and return the tree-sitter tree."""
    assert language, "language name must not be empty"
    tree = _parser(language).parse(text.encode("utf-8"))
    assert tree is not None, "parser returned no tree"
    return tree


def tags_query(language: str) -> Query | None:
    """Return the compiled ``tags`` query for ``language``, or None if it has none.

    Some grammars ship no tags query; those callers get None and skip the
    tags-driven rules rather than failing.
    """
    assert language, "language name must not be empty"
    if language in _TAGS_QUERIES:
        return _TAGS_QUERIES[language]
    from tree_sitter_language_pack import get_language, get_tags_query  # noqa: PLC0415

    source = get_tags_query(language)
    if not source:
        _TAGS_QUERIES[language] = None
        return None
    compiled = Query(get_language(language), source)
    assert compiled is not None, "a non-empty tags source must compile to a query"
    _TAGS_QUERIES[language] = compiled
    return compiled


def compile_query(language: str, source: str) -> Query:
    """Compile ``source`` against ``language``'s grammar, cached per pair."""
    assert language, "language name must not be empty"
    assert source, "query source must not be empty"
    key = (language, source)
    cached = _EXTRA_QUERIES.get(key)
    if cached is not None:
        return cached
    from tree_sitter_language_pack import get_language  # noqa: PLC0415

    compiled = Query(get_language(language), source)
    _EXTRA_QUERIES[key] = compiled
    return compiled


def run_query(query: Query, root: Node) -> list[dict[str, list[Node]]]:
    """Run ``query`` over ``root`` and return each match's captures, keyed by name."""
    assert query is not None, "query must not be None"
    assert root is not None, "root node must not be None"
    matches = QueryCursor(query).matches(root)
    return [captures for _pattern_index, captures in matches]
