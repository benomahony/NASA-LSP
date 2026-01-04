# Development

## Requirements

Python 3.13+

## Setup

```bash
git clone https://github.com/benomahony/nasa-lsp
cd nasa-lsp
uv sync
python main.py
```

## Project Structure

```
nasa-lsp/
├── src/
│   └── nasa_lsp/
│       ├── __init__.py
│       └── main.py          # LSP server and rule implementations
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

1. Add a `visit_*` method to the `NasaVisitor` class in `src/nasa_lsp/main.py`
2. Use AST pattern matching to detect violations
3. Call `self._add_diag()` to report diagnostics
4. Update documentation with the new rule code

Example:

```python
def visit_While(self, node: ast.While) -> None:
    assert node
    if isinstance(node.test, ast.Constant) and node.test.value is True:
        range = self._range_for_node(node)
        assert range
        self._add_diag(
            range,
            "Unbounded loop 'while True' (NASA02: loops must be bounded)",
            "NASA02",
        )
    self.generic_visit(node)
```

## Contributing

Contributions welcome for implementing additional NASA rules or improving detection accuracy.

## License

MIT
