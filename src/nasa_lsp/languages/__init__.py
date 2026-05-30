"""Language registry for the NASA Power of 10 analyzer.

Each supported language lives in its own module (``python``, ``c``, … ``zig``)
and exports a :class:`LanguageSpec` named ``SPEC``. This package assembles those
specs into a lookup keyed by language name, and maps file extensions to
languages. To add a language, drop in a new module and list it in ``_MODULES``.
"""

from __future__ import annotations

from typing import Final

from nasa_lsp.languages import c, cpp, go, javascript, python, rust, typescript, zig
from nasa_lsp.languages._nodes import direct_callee_name, node_text, resolved_callee_name
from nasa_lsp.languages.spec import LanguageSpec

_SPECS: Final[tuple[LanguageSpec, ...]] = (
    python.SPEC,
    c.SPEC,
    cpp.SPEC,
    go.SPEC,
    rust.SPEC,
    javascript.SPEC,
    typescript.SPEC,
    zig.SPEC,
)

#: All language specs, keyed by tree-sitter language name.
SPECS: Final[dict[str, LanguageSpec]] = {spec.name: spec for spec in _SPECS}

_EXTENSION_MAP: Final[dict[str, str]] = {ext: spec.name for spec in _SPECS for ext in spec.extensions}

#: File extensions the linter will discover when scanning directories.
SUPPORTED_EXTENSIONS: Final = frozenset(_EXTENSION_MAP)


def language_for_suffix(suffix: str) -> str | None:
    """Map a file extension (including the leading dot) to a supported language."""
    assert isinstance(suffix, str)
    assert "/" not in suffix
    return _EXTENSION_MAP.get(suffix.lower())


__all__ = [
    "SPECS",
    "SUPPORTED_EXTENSIONS",
    "LanguageSpec",
    "direct_callee_name",
    "language_for_suffix",
    "node_text",
    "resolved_callee_name",
]
