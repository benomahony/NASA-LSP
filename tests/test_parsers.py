"""Tests for the parser cache.

The test suite seeds the cache with bundled grammars in ``conftest.py``; here we
verify the registration/lookup behaviour directly.
"""

from __future__ import annotations

import tree_sitter_python
from tree_sitter import Language, Parser

from nasa_lsp._parsers import get_parser, register_language


def test_get_parser_returns_seeded_parser() -> None:
    parser = get_parser("python")
    assert parser is not None
    assert isinstance(parser, Parser)


def test_get_parser_is_cached() -> None:
    first = get_parser("python")
    second = get_parser("python")
    assert first is second
    assert first is not None


def test_register_language_seeds_cache() -> None:
    register_language("python-clone", Language(tree_sitter_python.language()))
    parser = get_parser("python-clone")
    assert parser is not None
    assert isinstance(parser, Parser)


def test_registered_parser_actually_parses() -> None:
    register_language("py-parse-check", Language(tree_sitter_python.language()))
    parser = get_parser("py-parse-check")
    assert parser is not None
    tree = parser.parse(b"def f():\n    pass\n")
    assert tree.root_node.type == "module"
    assert not tree.root_node.has_error
