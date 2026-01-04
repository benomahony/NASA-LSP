# CLAUDE.md - NASA LSP Development Guide for AI Assistants

## Project Overview

**NASA LSP** is a Language Server Protocol (LSP) implementation that enforces NASA's "Power of 10" rules for safety-critical code in Python. Originally designed for C by Gerard J. Holzmann at NASA's Jet Propulsion Laboratory in 2006, these rules ensure code is verifiable, analyzable, and suitable for mission-critical systems.

**Key Differentiators:**
- Enforces safety-critical constraints that mainstream linters (like Ruff) deliberately omit
- Focuses on verifiability and static analysis capabilities
- Provides real-time feedback via LSP in editors

**Repository:** https://github.com/benomahony/NASA-LSP
**Package Name:** `nasa-lsp`
**Python Version:** 3.13+
**Package Manager:** `uv` (modern Python package installer and resolver)

---

## Repository Structure

```
NASA-LSP/
├── .github/
│   └── workflows/
│       └── publish.yaml           # PyPI publishing workflow
├── docs/                          # Zensical documentation site
│   ├── index.md                   # Documentation home page
│   ├── getting-started.md         # Installation and editor setup
│   ├── rules.md                   # Detailed rule documentation
│   └── development.md             # Development guide
├── src/
│   └── nasa_lsp/
│       ├── __init__.py
│       └── main.py                # LSP server and all rule implementations
├── .gitignore                     # Git ignore patterns
├── .python-version                # Python 3.13
├── pyproject.toml                 # Project metadata and dependencies
├── uv.lock                        # Locked dependencies
├── zensical.toml                  # Zensical doc site configuration
└── README.md                      # Main project README
```

### Key Files

- **`src/nasa_lsp/main.py`** - The entire LSP implementation in a single file (~261 lines)
  - `NasaVisitor` class: AST visitor pattern for rule checking
  - `analyze()`: Entry point for diagnostics generation
  - `serve()`: LSP server entry point
  - All NASA rule implementations as `visit_*` methods

- **`pyproject.toml`** - Project configuration
  - Dependencies: `pygls>=2.0.0` (Python Language Server library)
  - Entry point: `nasa-lsp` command maps to `nasa_lsp.main:serve`
  - Package managed by `uv`

- **`docs/`** - Documentation built with Zensical (a documentation generator)

---

## Development Setup

### Prerequisites

- Python 3.13+
- `uv` package manager

### Initial Setup

```bash
# Clone the repository
git clone https://github.com/benomahony/nasa-lsp
cd nasa-lsp

# Sync dependencies (creates .venv automatically)
uv sync

# Run the LSP server directly
python src/nasa_lsp/main.py

# Or use the installed command
uv run nasa-lsp
```

### Development Workflow

1. **Make changes** to `src/nasa_lsp/main.py`
2. **Test locally** by running the LSP server
3. **Update documentation** in `docs/` if adding new rules
4. **Update version** in `pyproject.toml` for releases
5. **Commit and push** changes
6. **Create release** - triggers PyPI publishing workflow

### Package Management with `uv`

```bash
# Sync dependencies (like npm install)
uv sync

# Add a new dependency
uv add <package>

# Run commands in the virtual environment
uv run <command>

# Build the package
uv build
```

---

## Code Architecture

### LSP Implementation Pattern

The codebase uses the **pygls** library for LSP functionality and Python's **ast** module for code analysis.

```python
# High-level flow:
1. Editor opens/changes Python file
   ↓
2. LSP server receives notification (did_open/did_change)
   ↓
3. run_checks() is called with the document
   ↓
4. analyze() parses code with ast.parse()
   ↓
5. NasaVisitor walks the AST, detecting violations
   ↓
6. Diagnostics are published back to editor
```

### NasaVisitor Class Structure

```python
class NasaVisitor(ast.NodeVisitor):
    """Walk AST and collect NASA-style diagnostics."""

    def __init__(self, uri: str, text: str):
        # Stores file URI, source text, and diagnostics list

    def visit_Call(self, node):
        # NASA01-A: Detects forbidden dynamic APIs

    def visit_While(self, node):
        # NASA02: Detects unbounded while True loops

    def visit_FunctionDef(self, node):
        # NASA01-B: Detects direct recursion
        # NASA04: Enforces 60-line function limit
        # NASA05: Enforces assertion density (≥2 asserts)
```

### AST Visitor Pattern

- Each `visit_*` method corresponds to an AST node type
- Methods inspect nodes for rule violations
- Call `self._add_diag()` to report violations
- Always call `self.generic_visit(node)` to continue traversal

---

## NASA Rules Implementation

### Currently Implemented Rules

| Rule | Code | Detection Method | Lines in Code |
|------|------|------------------|---------------|
| **Simple Control Flow** | NASA01-A | `visit_Call()` | 103-134 |
| **No Recursion** | NASA01-B | `visit_FunctionDef()` | 158-178 |
| **Bounded Loops** | NASA02 | `visit_While()` | 137-148 |
| **Function Length ≤60** | NASA04 | `visit_FunctionDef()` | 180-186 |
| **Assertion Density** | NASA05 | `visit_FunctionDef()` | 188-206 |

### NASA01-A: Forbidden Dynamic APIs

**Rationale:** Dynamic APIs make static analysis impossible and obscure control flow.

**Forbidden APIs:**
- `eval`, `exec`, `compile` - Arbitrary code execution
- `globals`, `locals` - Namespace manipulation
- `__import__` - Dynamic imports
- `setattr`, `getattr` - Dynamic attribute access

**Implementation:** Checks `ast.Call` nodes for forbidden function names.

### NASA01-B: No Recursion

**Rationale:** Recursion prevents proving stack bounds. Acyclic call graphs enable better analysis.

**Detection:** Searches function body for calls to itself (direct recursion only).

**Limitation:** Does not detect indirect recursion (A→B→A).

### NASA02: Unbounded Loops

**Rationale:** Loops must have provable upper bounds to prevent runaway code.

**Detection:** Flags `while True` constructs.

**Better Pattern:** Use `for i in range(max_iterations)` with explicit bounds.

### NASA04: Function Length Limit

**Rationale:** Functions > 60 lines are hard to verify as logical units.

**Detection:** Checks `end_lineno - lineno >= 60`.

**Note:** Includes function signature in line count.

### NASA05: Assertion Density

**Rationale:** Minimum 2 assertions per function to catch impossible conditions.

**Detection:** Counts `ast.Assert` nodes, excluding nested function/class definitions.

**Best Practice:** Check preconditions, postconditions, and invariants.

### Not Yet Implemented

- **Rule 3:** Dynamic memory allocation (could detect unbounded `list.append()` in loops)
- **Rule 6:** Smallest scope (partially handled by Python scoping + Ruff)
- **Rule 7:** Check return values (use Ruff's `B018` rule)
- **Rule 8:** Limited preprocessor (NASA01-A bans `__import__`; use Ruff for imports)
- **Rule 9:** Pointer restrictions (N/A in Python)
- **Rule 10:** All warnings enabled (use Ruff + Mypy)

---

## Coding Conventions

### The Codebase Follows NASA Rules!

**Critical:** The LSP implementation itself adheres to NASA's Power of 10 rules. This is intentional and demonstrates the rules in practice.

#### Assertions Everywhere

Every function has ≥2 assertions. These verify:
- Parameter validity
- Preconditions
- Invariants
- Postconditions

```python
def _add_diag(self, range: types.Range, message: str, code: str) -> None:
    assert range      # Precondition: range must exist
    assert message    # Precondition: message must exist
    assert code       # Precondition: code must exist
    # ... function body
```

#### No Recursion

All algorithms use iteration, not recursion.

#### Bounded Loops

No `while True` loops. All loops have explicit bounds or termination conditions.

#### Small Functions

All functions are under 60 lines.

#### Simple Control Flow

No dynamic code execution, no complex metaprogramming.

### Code Style

- **Type hints:** Used throughout (via `from __future__ import annotations`)
- **Explicit over implicit:** Clear variable names, no abbreviations
- **Assertions as documentation:** Express invariants directly in code
- **Line length:** Keep reasonable (no strict limit, but maintain readability)

---

## Adding New Rules

### Step-by-Step Guide

1. **Add a `visit_*` method** to `NasaVisitor` class

```python
def visit_NodeType(self, node: ast.NodeType) -> None:
    assert node  # Always assert parameters

    # Check for violation condition
    if violates_rule(node):
        self._add_diag(
            self._range_for_node(node),
            "Violation message (NASAXX: rule description)",
            "NASAXX",
        )

    # Continue traversal
    self.generic_visit(node)
```

2. **Update documentation** in `docs/rules.md`

3. **Update README.md** NASA Rule Coverage table

4. **Test the rule** with example violations

### Example: Detecting `try/except` Overuse (Hypothetical Rule)

```python
def visit_Try(self, node: ast.Try) -> None:
    assert node

    # NASA06: No bare except clauses
    for handler in node.handlers:
        if handler.type is None:  # bare except:
            self._add_diag(
                self._range_for_node(handler),
                "Bare except clause hides errors (NASA06: explicit error handling)",
                "NASA06",
            )

    self.generic_visit(node)
```

---

## Testing Strategy

### Manual Testing

Currently, testing is manual:
1. Create a test Python file with violations
2. Run the LSP server
3. Connect from an editor
4. Verify diagnostics appear

### Example Test File

```python
# test_violations.py

def recursive_function(n):  # NASA01-B violation
    if n > 0:
        return recursive_function(n - 1)
    return 0

def process_forever():  # NASA02 violation
    while True:
        pass

def short_function():  # NASA05 violation (no asserts)
    return 42

def long_function():  # NASA04 violation if >60 lines
    # ... many lines of code
```

### Future Testing Improvements

- Add unit tests for `NasaVisitor` methods
- Create fixture files with known violations
- Automate diagnostic verification

---

## CI/CD and Publishing

### GitHub Workflow

**File:** `.github/workflows/publish.yaml`

**Triggers:**
- Manual workflow dispatch
- Release creation

**Steps:**
1. Checkout repository
2. Install `uv`
3. Sync dependencies (`uv sync`)
4. Build package (`uv build`)
5. Publish to PyPI (using trusted publisher)

### Release Process

1. Update version in `pyproject.toml`
2. Commit changes
3. Create GitHub release (tag format: `vX.Y.Z`)
4. Workflow automatically publishes to PyPI

---

## Editor Integration

### Neovim (with lazy.nvim)

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
      },
    },
  },
}
```

### VS Code

```json
{
  "python.languageServer": "None",
  "nasa-lsp.enabled": true,
  "nasa-lsp.path": ["uvx", "nasa_lsp"]
}
```

**Note:** VS Code integration requires manual LSP client configuration or a dedicated extension.

---

## Best Practices for AI Assistants

### When Modifying Code

1. **Always read the file first** before making changes
2. **Maintain NASA rule compliance** - the code self-enforces its own rules
3. **Add assertions** to all new functions (minimum 2)
4. **Keep functions under 60 lines**
5. **Use explicit loops** with known bounds
6. **Avoid adding dependencies** - keep the implementation minimal

### When Adding Features

1. **Single file architecture** - keep all LSP logic in `main.py`
2. **Follow the visitor pattern** - add `visit_*` methods for new rules
3. **Update all documentation** - README, docs/, and this file
4. **Test manually** with example violations
5. **Update version** in `pyproject.toml`

### When Fixing Bugs

1. **Understand the AST** - use `ast.dump()` to inspect nodes
2. **Check range calculations** - LSP uses 0-based line numbers, AST uses 1-based
3. **Verify assertions** - ensure they're meaningful, not just noise
4. **Test edge cases** - empty files, syntax errors, nested structures

### Code Review Checklist

- [ ] All new functions have ≥2 assertions
- [ ] All functions are <60 lines
- [ ] No recursion used
- [ ] No `while True` loops
- [ ] No forbidden dynamic APIs used
- [ ] Documentation updated
- [ ] Version bumped (if releasing)

---

## Common Pitfalls

### AST Line Number Confusion

- **AST uses 1-based line numbers** (`lineno` starts at 1)
- **LSP uses 0-based line numbers** (convert with `lineno - 1`)
- Helper method `_pos()` handles this conversion

### Range Calculation

- Use `_range_for_node()` for full node highlighting
- Use `_range_for_func_name()` for function definition highlighting
- Always assert ranges before using them

### Assertion Overload

The code has many assertions. This is **intentional** and **required** by NASA05. Don't remove them thinking they're excessive.

### Visitor Traversal

Always call `self.generic_visit(node)` at the end of visitor methods, or child nodes won't be visited.

---

## Diagnostic Codes

| Code | Severity | Message Pattern |
|------|----------|-----------------|
| NASA01-A | Warning | Call to forbidden API '{name}' (NASA01: restricted subset) |
| NASA01-B | Warning | Recursive call to '{name}' (NASA01: no recursion) |
| NASA02 | Warning | Unbounded loop 'while True' (NASA02: loops must be bounded) |
| NASA04 | Warning | Function '{name}' longer than 60 lines (NASA04: ...) |
| NASA05 | Warning | Function '{name}' has only {N} assert(s); expected at least 2 (NASA05: ...) |

---

## Documentation Site

Built with **Zensical** (configured in `zensical.toml`).

**Structure:**
- `docs/index.md` - Overview and quick start
- `docs/getting-started.md` - Installation and editor setup
- `docs/rules.md` - Detailed rule explanations
- `docs/development.md` - Development guide

**Building locally:**
```bash
# Install zensical
uv add --dev zensical

# Build and serve
zensical serve
```

---

## Recommended Complementary Tools

NASA LSP focuses on safety-critical rules. For comprehensive Python quality:

- **Ruff** - Fast Python linter (covers rules 6, 7, 8, 10)
- **Mypy** - Static type checker (rule 10)
- **Pytest** - Unit testing framework

**Ideal Setup:**
```bash
uv add --dev ruff mypy pytest
```

---

## References

- **Original Paper:** [The Power of 10: Rules for Developing Safety-Critical Code](https://spinroot.com/gerard/pdf/P10.pdf)
- **pygls Documentation:** https://pygls.readthedocs.io/
- **Python AST Module:** https://docs.python.org/3/library/ast.html
- **LSP Specification:** https://microsoft.github.io/language-server-protocol/

---

## Quick Reference Commands

```bash
# Development
uv sync                    # Install dependencies
python src/nasa_lsp/main.py  # Run LSP server directly
uv run nasa-lsp           # Run via installed command

# Building
uv build                   # Build package (creates dist/)

# Testing
# Create test file with violations, connect editor with LSP

# Documentation
# Edit files in docs/
# Deploy via zensical (configured in zensical.toml)

# Git workflow
git checkout -b feature/my-feature
# Make changes
git add .
git commit -m "description"
git push -u origin feature/my-feature
# Create PR to main branch
```

---

## Version History

- **0.1.2** - Current version
- **0.2.0** - LSP server version string in code

---

## License

MIT License - See repository for full license text.

---

## Contact and Contributing

Contributions welcome! Focus areas:
- Implementing remaining NASA rules (3, 6, 7, 8, 10)
- Indirect recursion detection
- More sophisticated loop bound analysis
- Automated testing
- VS Code extension

**Repository Issues:** https://github.com/benomahony/NASA-LSP/issues
