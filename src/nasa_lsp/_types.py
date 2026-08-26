"""Shared value types and thresholds for the analyzers.

Both the Python ``ast`` analyzer and the tree-sitter :mod:`nasa_lsp.generic`
engine produce the same diagnostics and statistics, so those dataclasses -- and
the per-function thresholds the rules compare against -- live here, in a module
neither analyzer depends on. That keeps the two engines free of an import cycle
while presenting one diagnostic type to callers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

MAX_FUNCTION_LINES: Final = 60
MIN_ASSERTS_PER_FUNCTION: Final = 2


@dataclass
class Position:
    line: int
    character: int


@dataclass
class Range:
    start: Position
    end: Position


@dataclass
class Diagnostic:
    range: Range
    message: str
    code: str


@dataclass
class FunctionStat:
    name: str
    line_start: int
    line_count: int
    assert_count: int
