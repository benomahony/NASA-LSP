# Getting Started

## Installation

### From PyPI

```bash
uv add nasa-lsp
```

### From Source

```bash
git clone https://github.com/benomahony/nasa-lsp
cd nasa-lsp
uv pip install -e .
```

## Editor Configuration

### Neovim

Using lazy.nvim:

```lua
{
  "neovim/nvim-lspconfig",
  opts = {
    servers = {
      nasa_lsp = {
        cmd = { "uvx", "nasa_lsp" },
        filetypes = { "python" },
        root_dir = function(fname)
          return require("lspconfig.util").find_git_ancestor(fname)
        end,
        settings = {},
      },
    },
  },
}
```

Or with manual configuration:

```lua
require("lspconfig").nasa_lsp.setup({
  cmd = { "uvx", "nasa_lsp" },
  filetypes = { "python" },
  root_dir = require("lspconfig.util").find_git_ancestor,
})
```

### VS Code

Create or edit `.vscode/settings.json`:

```json
{
  "python.linting.enabled": true,
  "python.languageServer": "None",
  "nasa-lsp.enabled": true,
  "nasa-lsp.path": ["uvx", "nasa_lsp"]
}
```

## Usage

The LSP runs automatically on Python files and provides inline diagnostics as you type. Violations appear as warnings with diagnostic codes:

- `NASA01-A`: Use of forbidden dynamic API
- `NASA01-B`: Direct recursive function call
- `NASA02`: Unbounded while True loop
- `NASA04`: Function exceeds 60-line limit
- `NASA05`: Insufficient assertions in function

## Example Violations

```python
def process_data(items):
    while True:
        item = items.pop()
        if not item:
            break
```

This code violates NASA02 with an unbounded loop and NASA05 with no assertions.

Fixed version:

```python
def process_data(items):
    assert items is not None
    assert isinstance(items, list)

    max_iterations = len(items)
    for i in range(max_iterations):
        if i >= len(items):
            break
        item = items[i]
```
