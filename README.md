# NASA LSP

A Language Server Protocol implementation that enforces NASA's Power of 10 rules for safety-critical code in Python.

## Background

The Power of 10 rules were created in 2006 by Gerard J. Holzmann of NASA's Jet Propulsion Laboratory to improve the safety and reliability of mission-critical software. While originally designed for C, these principles apply broadly to writing verifiable, analyzable code in any language.

## NASA's 10 Rules for Safety-Critical Code

1. Restrict all code to very simple control flow constructs—do not use goto statements, setjmp or longjmp constructs, or direct or indirect recursion.2. **Bounded loops**: All loops must have a fixed upper bound provable by static analysis
2. Give all loops a fixed upper bound. It must be trivially possible for a checking tool to prove statically that the loop cannot exceed a preset upper bound on the number of iterations. If a tool cannot prove the loop bound statically, the rule is considered violated.4. **Function length**: No function should exceed what fits on a single printed page
3. Do not use dynamic memory allocation after initialization.
4. No function should be longer than what can be printed on a single sheet of paper in a standard format with one line per statement and one line per declaration. Typically, this means no more than about 60 lines of code per function.
5. The code's assertions density should average to minimally two assertions per function. Assertions must be used to check for anomalous conditions that should never happen in real-life executions. Assertions must be side-effect free and should be defined as Boolean tests. When an assertion fails, an explicit recovery action must be taken such as returning an error condition to the caller of the function that executes the failing assertion. Any assertion for which a static checking tool can prove that it can never fail or never hold violates this rule.
6. Declare all data objects at the smallest possible level of scope.
7. Each calling function must check the return value of nonvoid functions, and each called function must check the validity of all parameters provided by the caller.
8. The use of the preprocessor must be limited to the inclusion of header files and simple macros definitions. Token pasting, variable argument lists (ellipses), and recursive macro calls are not allowed. All macros must expand into complete syntactic units. The use of conditional compilation directives must be kept to a minimum.
9. The use of pointers must be restricted. Specifically, no more than one level of dereference should be used. Pointer dereference operations may not be hidden in macro definitions or inside typedef declarations. function pointers are not permitted.
10. All code must be compiled, from the first day of development, with all compiler warnings enabled at the most pedantic setting available. All code must compile without warnings. All code must also be checked daily with at least one, but preferably more than one, strong static source code analyzer and should pass all analyses with zero warnings.

## Currently Implemented Rules

This LSP currently detects violations of the following rules adapted for Python:

### Rule 1: Simple Control Flow

**NASA01-A: Forbidden Dynamic APIs**

Flags calls to dynamic APIs that make code difficult to analyze:

- `eval`, `exec`, `compile`
- `globals`, `locals`
- `__import__`
- `setattr`, `getattr`

**NASA01-B: No Recursion**

Identifies direct recursive function calls where a function calls itself.

### Rule 2: Bounded Loops

**NASA02: Unbounded Loops**

Detects unbounded `while True` loops that violate the fixed upper bound requirement.

### Rule 5: Assertion Density

**NASA05: Assertion Count**

Enforces minimum of 2 assert statements per function to detect impossible conditions and verify invariants.

## Installation

```bash
uv add nasa-lsp
```

Or from source:

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

For a VS Code extension, install from the marketplace or configure manually by adding to your Python language server settings.

## Usage

The LSP runs automatically on Python files and provides inline diagnostics as you type. Violations appear as warnings with diagnostic codes:

- `NASA01-A`: Use of forbidden dynamic API
- `NASA01-B`: Direct recursive function call
- `NASA02`: Unbounded while True loop
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

## Development

Requirements: Python 3.13+

```bash
git clone https://github.com/benomahony/nasa-lsp
cd nasa-lsp
uv sync
python main.py
```

## Contributing

Contributions welcome for implementing additional NASA rules or improving detection accuracy.

## License

MIT

## References

- [The Power of 10: Rules for Developing Safety-Critical Code](https://spinroot.com/gerard/pdf/P10.pdf) by Gerard J. Holzmann
