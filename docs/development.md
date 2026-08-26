# Development

## Requirements

Python 3.12+

## Setup

```bash
git clone https://github.com/benomahony/nasa-lsp
cd nasa-lsp
uv sync
uv run nasa lint
```

## Project Structure

```
nasa-lsp/
├── src/
│   └── nasa_lsp/
│       ├── __init__.py
│       ├── analyzer.py      # AST analysis and rule implementations
│       ├── cli.py           # `nasa` command-line entry point
│       └── server.py        # Language Server Protocol server
├── docs/                    # Zensical documentation
├── pyproject.toml          # Project configuration
└── README.md
```

## Architecture

The LSP uses Python's `ast` module to parse and analyze code:

1. **NasaVisitor** - AST visitor that walks the syntax tree
2. **Rule implementations** - Individual `visit_*` methods for each node type
3. **Diagnostics** - LSP diagnostics published to the editor

### Adding a New Rule

To add a new NASA rule:

1. Register the rule code and its severity in `RULE_SEVERITY` in `src/nasa_lsp/analyzer.py`
2. Add a `visit_*` or `_check_*` method to the `NasaVisitor` class that detects violations
3. Call `self._add_diag()` to report diagnostics, passing the rule code
4. Document the rule with an example in `docs/rules.md`

Example:

```python
def visit_While(self, node: ast.While) -> None:
    assert node
    if isinstance(node.test, ast.Constant) and node.test.value is True:
        range = self._range_for_node(node)
        assert range
        self._add_diag(
            range,
            "Unbounded loop 'while True' (NASA02)",
            "NASA02",
        )
    self.generic_visit(node)
```

## Contributing

Contributions welcome for implementing additional NASA rules or improving detection accuracy.

## License

MIT
