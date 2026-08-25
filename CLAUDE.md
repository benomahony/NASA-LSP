# Conventions

## Linter rules ship enabled

Every rule the linter can emit is enabled by default. Configuration
(`[tool.nasa-lsp].rules`) only *narrows* the set — it never *enables*. A new
rule goes into `DEFAULT_ENABLED_RULES` in the same change that adds it.
Enforced by `test_every_rule_is_enabled_by_default`. Do not ship a rule
opt-in, and do not offer opt-in as a choice — "on by default" is the answer.

## Before pushing

Run the whole check suite, not just pytest: `uvx prek run --all-files`
(ruff check + format, basedpyright, `nasa lint`, pytest with coverage, dead).
CI also runs `ruff check .` and `mutmut run`. A push that turns CI red costs a
cycle; validate locally first.
