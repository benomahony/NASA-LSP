# Claude Development Notes

This file contains important information for AI assistants working on this project.

## Project Overview

NASA LSP is a Language Server Protocol implementation that enforces NASA's Power of 10 rules for safety-critical code in Python.

## Testing & Quality

### Running Tests Locally

Use the `test` command which runs pytest with coverage, then mutation tests:

```bash
uv run test
```

This command:
1. Runs pytest with 90% coverage requirement
2. Only if successful, runs mutmut
3. Fails if any mutations survive (100% mutation killing required)
4. Generates coverage.json for CI badges

### Pre-commit Hooks

This project uses **prek** (not pre-commit). Hooks are configured in `.pre-commit-config.yaml`:
- Install: `uv run prek install && uv run prek install --hook-type pre-push`
- Runs: ruff, basedpyright, nasa-lsp checks
- The nasa-lsp check applies to all Python files (no exclusions)

### CI/CD

- CI uses the same `uv run test` command as local development
- CI enforces 100% mutation killing - any surviving mutations fail the build
- On push to main: generates and commits SVG badges for coverage and mutation score
- Badges are self-hosted in `.github/badges/` (no external services)

## Important Decisions

### Coverage
- **No exclusions**: All code in `src/nasa_lsp` is covered, including `__init__.py` and `test_runner.py`
- Coverage reports saved as `.coverage` and `coverage.json` (gitignored)
- Minimum threshold: 100% (both line and branch coverage)

### Mutation Testing
- Runs after pytest succeeds
- 100% of mutations must be killed for CI to pass
- Results cached in `.mutmut-cache/` (gitignored)

### Fuzzing & Property-Based Testing
- **Hypothesis**: Property-based testing generates random valid Python code
- **AST Fuzzing**: Tests with various AST structures (empty, nested, large)
- **LSP Protocol Fuzzing**: Tests unicode handling, line endings, long lines
- Fuzzing tests in `tests/test_fuzzing.py`
- Ensures analyzer never crashes on any valid Python input

### Code Quality
- All Python code checked by nasa-lsp itself (dogfooding)
- test_runner.py needs 2+ asserts to satisfy NASA05 rule
- Uses prek for faster hook execution (Rust-based)

## Commands

```bash
# Run all tests locally (same as CI)
uv run test

# Run individual tools
uv run pytest --cov=src/nasa_lsp --cov-report=term-missing
uv run mutmut run
uv run nasa lint src/ tests/

# Install hooks
uv run prek install && uv run prek install --hook-type pre-push
```

## Structure

- `src/nasa_lsp/` - Main source code
  - `analyzer.py` - AST analysis and rule checking
  - `server.py` - LSP server implementation
  - `cli.py` - Command-line interface
  - `test_runner.py` - Test orchestration script
- `tests/` - Test suite
- `.github/` - CI workflows and badge generation
- `.pre-commit-config.yaml` - Prek hook configuration

## NASA Power of 10 Rules (Enforced)

This project enforces a subset of NASA's Power of 10 rules for safety-critical software:

### NASA01-A: Forbidden Dynamic APIs
Flags calls to dynamic APIs that make code difficult to analyze:
- `eval`, `exec`, `compile`
- `globals`, `locals`
- `__import__`
- `setattr`, `getattr`

### NASA01-B: No Recursion
Identifies direct recursive function calls where a function calls itself.

### NASA02: Bounded Loops
Detects unbounded `while True` loops that violate the fixed upper bound requirement.

### NASA04: Function Length Limit
Enforces strict 60-line limit per function for verifiability and code clarity.

### NASA05: Assertion Density
Enforces minimum of 2 assert statements per function to detect impossible conditions and verify invariants.

**Important**: When adding new functions, always include at least 2 meaningful assertions. The test_runner.py has assertions checking Python version and subprocess availability as examples.

## Never Do These

1. Don't exclude files from coverage without asking first
2. Don't switch from prek back to pre-commit
3. Don't make changes to README without being asked
4. Don't add external services (codecov, etc.) without permission
5. Don't duplicate test logic between `test_runner.py` and CI
