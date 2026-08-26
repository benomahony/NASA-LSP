# Conventions

## Linter rules ship enabled

`RULE_SEVERITY` is the single registry of every rule; `ALL_RULES` derives from
it and every rule is on by default. Config (`[tool.nasa-lsp].disable`) only
*removes* rules — there is no enable list. A new rule is added to
`RULE_SEVERITY` in the same change (which registers, severity-maps, and enables
it); `test_registry_matches_the_emittable_rules` fails otherwise. Do not add an
enabled-rules allowlist, and do not offer opt-in as a choice — "on by default,
disable to opt out" is the answer.

## Before pushing

Run the whole check suite, not just pytest: `uvx prek run --all-files`
(ruff check + format, basedpyright, `nasa lint`, pytest with coverage, dead).
CI also runs `ruff check .` and `mutmut run`. A push that turns CI red costs a
cycle; validate locally first.
