# NASA LSP

A Language Server Protocol implementation that enforces NASA's Power of 10 rules for safety-critical code in Python.

## Background

The Power of 10 rules were created in 2006 by Gerard J. Holzmann of NASA's Jet Propulsion Laboratory to improve the safety and reliability of mission-critical software. While originally designed for C, these principles apply broadly to writing verifiable, analyzable code in any language.

## What Makes NASA LSP Unique

While tools like Ruff handle general Python quality, **NASA LSP enforces safety-critical constraints** that mainstream linters deliberately don't include:

- ✅ **Recursion detection** - Ruff doesn't detect or forbid recursion
- ✅ **Bounded loop enforcement** - Ruff doesn't restrict `while True` or require loop bounds
- ✅ **Strict line limits** - Ruff has complexity metrics but not hard 60-line function limits
- ✅ **Assertion density** - Ruff doesn't enforce minimum assertions per function

**Use NASA LSP when:** Building safety-critical, embedded, or verifiable Python systems
**Use Ruff when:** General Python quality and best practices
**Use both when:** Maximum code quality and safety verification

## Quick Start

```bash
uv add nasa-lsp
```

See the [Getting Started](getting-started.md) guide for detailed installation and configuration instructions.

## References

- [The Power of 10: Rules for Developing Safety-Critical Code](https://spinroot.com/gerard/pdf/P10.pdf) by Gerard J. Holzmann
