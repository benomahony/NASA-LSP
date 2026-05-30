"""Parser acquisition for the analyzer.

Production parsing uses ``tree-sitter-language-pack``, which downloads grammars
on first use. To keep the analyzer testable offline, parsers are looked up
through a small cache that tests (or any caller) can pre-seed via
:func:`register_language` using bundled grammar wheels. The rest of the codebase
only ever sees a standard ``tree_sitter.Parser``, regardless of where the
grammar came from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from tree_sitter import Language, Parser

_CACHE: dict[str, Parser | None] = {}


def register_language(name: str, language: Language) -> None:
    """Pre-seed the parser cache for ``name`` with an explicit grammar.

    Used by the test suite to supply bundled grammars without network access.
    """
    from tree_sitter import Parser  # noqa: PLC0415

    assert name
    assert language is not None
    _CACHE[name] = Parser(language)


def _load_from_pack(name: str) -> Parser | None:  # pragma: no cover - runtime grammar-download path
    assert name
    assert isinstance(name, str)
    try:
        import tree_sitter_language_pack as tslp  # noqa: PLC0415

        # tree-sitter-language-pack returns its own Parser binding, which is
        # structurally a tree_sitter.Parser; cast through object to bridge them.
        return cast("Parser", cast("object", tslp.get_parser(name)))
    except Exception:  # noqa: BLE001 - any failure (download, missing grammar) means no parser
        return None


def get_parser(language: str) -> Parser | None:
    """Return a parser for ``language``, or ``None`` if one cannot be obtained."""
    assert language
    assert isinstance(language, str)
    if language not in _CACHE:
        _CACHE[language] = _load_from_pack(language)  # pragma: no cover - runtime grammar-download path
    return _CACHE[language]
