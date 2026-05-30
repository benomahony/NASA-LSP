"""Test configuration.

Seeds the analyzer's parser cache with bundled grammar wheels so the suite runs
deterministically and offline. Production code obtains the same grammars from
tree-sitter-language-pack at runtime; here we inject them directly.
"""

from __future__ import annotations

import tree_sitter_c
import tree_sitter_cpp
import tree_sitter_go
import tree_sitter_javascript
import tree_sitter_python
import tree_sitter_rust
import tree_sitter_typescript
import tree_sitter_zig
from tree_sitter import Language

from nasa_lsp._parsers import register_language

_GRAMMARS = {
    "python": tree_sitter_python.language,
    "c": tree_sitter_c.language,
    "cpp": tree_sitter_cpp.language,
    "go": tree_sitter_go.language,
    "rust": tree_sitter_rust.language,
    "javascript": tree_sitter_javascript.language,
    "typescript": tree_sitter_typescript.language_typescript,
    "zig": tree_sitter_zig.language,
}


def _seed_parsers() -> None:
    assert _GRAMMARS
    assert len(_GRAMMARS) == 8
    for name, grammar in _GRAMMARS.items():
        register_language(name, Language(grammar()))


_seed_parsers()
