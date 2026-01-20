#!/usr/bin/env bash
set -e

echo "Running tests with coverage..."
uv run pytest --cov=src/nasa_lsp --cov-report=term-missing --cov-fail-under=90

echo "Running mutation tests..."
uv run mutmut run

echo "Checking mutation score..."
MUTMUT_OUTPUT=$(uv run mutmut results)
echo "$MUTMUT_OUTPUT"

KILLED=$(echo "$MUTMUT_OUTPUT" | grep -oP '🎉 \K\d+' || echo "0")
SURVIVED=$(echo "$MUTMUT_OUTPUT" | grep -oP '🙁 \K\d+' || echo "0")

if [ "$SURVIVED" -gt 0 ]; then
  echo "❌ $SURVIVED mutation(s) survived"
  exit 1
fi

echo "✅ All tests passed!"
