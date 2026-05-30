# Development

## Requirements

Python 3.12+

## Setup

```bash
git clone https://github.com/benomahony/nasa-lsp
cd nasa-lsp
uv sync --extra dev
uv run nasa lint
```

## Project Structure

```
nasa-lsp/
├── src/
│   └── nasa_lsp/
│       ├── __init__.py
│       ├── analyzer.py       # Language-agnostic rule engine (tree-sitter)
│       ├── _parsers.py       # Parser acquisition / cache
│       ├── cli.py            # `nasa lint` / `nasa stats` / `nasa serve`
│       ├── server.py         # LSP server
│       └── languages/        # One module per language
│           ├── __init__.py   # Registry: assembles SPECS + extension map
│           ├── spec.py       # The LanguageSpec dataclass
│           ├── _nodes.py     # Shared tree-sitter node helpers
│           ├── python.py     # …c.py, cpp.py, go.py, rust.py,
│           └── zig.py        #    javascript.py, typescript.py, zig.py
├── docs/                    # Zensical documentation
├── pyproject.toml          # Project configuration
└── README.md
```

## Architecture

The analyzer parses source with [tree-sitter](https://tree-sitter.github.io/) and walks the
resulting syntax tree, applying the Power of 10 rules through a per-language `LanguageSpec`:

1. **`LanguageSpec`** (`languages/spec.py`) - describes how a language maps onto the rules:
   which node types are functions, calls and loops, how to detect unbounded loops and
   assertions, and which APIs are forbidden. Each language declares its own spec in
   `languages/<name>.py`; `languages/__init__.py` assembles them into `SPECS`.
2. **Rule engine** (`analyzer.py`) - generic logic that walks standard tree-sitter nodes and
   emits `Diagnostic`s. It never hard-codes a single language's grammar.
3. **Parsers** (`_parsers.py`) - grammars come from `tree-sitter-language-pack` at runtime;
   tests seed the cache from bundled grammar wheels for offline determinism.

The language for a file is inferred from its extension (`language_for_suffix`).

### Adding a New Language

1. Create `src/nasa_lsp/languages/<name>.py` exporting a `SPEC = LanguageSpec(...)` that
   describes the grammar's function/call/loop/assert node types and file extensions (use
   `tree-sitter` to inspect them; reuse helpers from `languages/_nodes.py`).
2. Add the module's `SPEC` to `_SPECS` in `src/nasa_lsp/languages/__init__.py`.
3. Seed the grammar wheel in `tests/conftest.py` and add cross-language tests.

### Adding a New Rule

1. Implement the check in `analyzer.py`, reading what it needs from the active `LanguageSpec`.
2. Expose any language-specific configuration the rule needs as `LanguageSpec` fields.
3. Update documentation with the new rule code.

## Dogfooding

NASA LSP lints its own source with its own rules via the `nasa-lsp` pre-commit hook, so all
analyzer code must itself satisfy the Power of 10 rules (no recursion, ≥2 assertions per
function, ≤60-line functions, and so on).

## Contributing

Contributions welcome for implementing additional NASA rules, supporting more languages, or
improving detection accuracy.

## License

MIT
