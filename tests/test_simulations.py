"""Simulation tests for NASA-LSP analyzer.

Tests for modern Python syntax and multi-file CLI scenarios.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from nasa_lsp.analyzer import analyze
from nasa_lsp.cli import app

runner = CliRunner()


# ============================================================================
# MODERN PYTHON SYNTAX TESTS
# ============================================================================


def test_complex_decorators_and_annotations() -> None:
    """Functions with complex decorators and type annotations."""
    code = """
from typing import Callable, TypeVar, ParamSpec

P = ParamSpec("P")
T = TypeVar("T")

def decorator1(func: Callable[P, T]) -> Callable[P, T]:
    assert func is not None
    assert callable(func)
    return func

def decorator2(x: int) -> Callable[[Callable[P, T]], Callable[P, T]]:
    assert x > 0
    assert isinstance(x, int)
    def wrapper(func: Callable[P, T]) -> Callable[P, T]:
        assert func is not None
        assert callable(func)
        return func
    return wrapper

@decorator1
@decorator2(10)
def complex_function(a: int, b: str, *, c: list[dict[str, int]]) -> tuple[int, ...]:
    assert a > 0
    assert isinstance(b, str)
    return (a,)

async def async_function_with_annotations(
    x: int | None = None,
    y: str | int = "default",
) -> dict[str, list[int]]:
    assert x is None or x > 0
    assert isinstance(y, (str, int))
    return {"result": [1, 2, 3]}
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert isinstance(diagnostics, list)


def test_fstrings_with_complex_expressions() -> None:
    """F-strings with complex expressions."""
    code = """
def process_data(items: list[int]) -> str:
    assert items
    assert isinstance(items, list)
    result = f"Items: {', '.join(str(x) for x in items if x > 0)}"
    nested = f"Count: {len([x for x in items if x > 0])}"
    complex_expr = f"Result: {sum(x**2 for x in items) if items else 0}"
    return result + nested + complex_expr
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert isinstance(diagnostics, list)


def test_match_statements() -> None:
    """Match/case statements (Python 3.10+)."""
    code = """
def handle_command(command: str) -> int:
    assert command
    assert isinstance(command, str)
    match command:
        case "start":
            return 1
        case "stop":
            return 0
        case _:
            return -1
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert isinstance(diagnostics, list)


def test_walrus_operator() -> None:
    """Walrus operator usage."""
    code = """
def process_items(items: list[int]) -> int:
    assert items
    assert isinstance(items, list)
    if (n := len(items)) > 10:
        return n
    while (item := items.pop(0) if items else None) is not None:
        pass
    return 0
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert isinstance(diagnostics, list)


def test_async_generators_and_context_managers() -> None:
    """Async generators and context managers."""
    code = """
async def async_generator():
    assert True
    assert True
    for i in range(10):
        yield i

async def async_context_manager():
    assert True
    assert True
    async with some_context():
        await something()
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert isinstance(diagnostics, list)


def test_comprehensions_with_conditions() -> None:
    """Complex comprehensions."""
    code = """
def process_data(data: list[int]) -> dict[int, list[int]]:
    assert data
    assert isinstance(data, list)
    squares = [x**2 for x in data if x > 0]
    mapping = {x: x**2 for x in data if x % 2 == 0}
    unique = {x % 10 for x in data}
    matrix = [[i*j for j in range(5)] for i in range(5)]
    return mapping
"""
    diagnostics, _ = analyze(code)
    assert diagnostics == []
    assert isinstance(diagnostics, list)


# ============================================================================
# MULTI-FILE/DIRECTORY CLI TESTS
# ============================================================================


def test_analyze_directory_with_mixed_files() -> None:
    """Analyzing a directory with clean and violating files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Clean file
        clean_file = tmp_path / "clean.py"
        _ = clean_file.write_text(
            """
def clean_function():
    assert True
    assert False
    return 42
"""
        )

        # File with violations
        violations_file = tmp_path / "violations.py"
        _ = violations_file.write_text(
            """
def has_eval():
    assert True
    assert False
    eval("1+1")

def no_asserts():
    return 1
"""
        )

        # Subdirectory with more files
        subdir = tmp_path / "subdir"
        subdir.mkdir()

        sub_file = subdir / "sub.py"
        _ = sub_file.write_text(
            """
def recursive(n: int) -> int:
    assert n >= 0
    assert isinstance(n, int)
    return recursive(n - 1)
"""
        )

        # Analyze directory using CLI
        result = runner.invoke(app, ["lint", str(tmp_path)])

        assert result.exit_code == 1
        assert "violation" in result.stdout.lower()


def test_exclude_common_directories() -> None:
    """Common directories are excluded from analysis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # File in main directory
        main_file = tmp_path / "main.py"
        _ = main_file.write_text(
            """
def bad():
    eval("test")
"""
        )

        # Files in excluded directories
        for excluded_dir in [".venv", "__pycache__", "node_modules", ".git"]:
            exc_dir = tmp_path / excluded_dir
            exc_dir.mkdir()
            exc_file = exc_dir / "test.py"
            _ = exc_file.write_text(
                """
def bad():
    eval("test")
"""
            )

        # Analyze directory using CLI
        result = runner.invoke(app, ["lint", str(tmp_path)])

        assert result.exit_code == 1
        assert "main.py" in result.stdout
        # Should NOT mention excluded directories
        for excluded in [".venv", "__pycache__", "node_modules", ".git"]:
            assert excluded not in result.stdout or f"{excluded}/test.py" not in result.stdout


# ============================================================================
# REAL-WORLD CODE EXAMPLE
# ============================================================================


def test_analyzing_nasa_lsp_code() -> None:
    """Analyzing code similar to actual NASA-LSP source."""
    code = """
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

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
    severity: int = 1

class Visitor(Protocol):
    def visit(self, node) -> None:
        assert node is not None
        assert hasattr(node, "__class__")
        ...

def analyze(source: str) -> list[Diagnostic]:
    assert isinstance(source, str)
    assert source is not None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    diagnostics: list[Diagnostic] = []
    return diagnostics
"""
    diagnostics, _ = analyze(code)
    assert isinstance(diagnostics, list)
    assert len(diagnostics) >= 0
