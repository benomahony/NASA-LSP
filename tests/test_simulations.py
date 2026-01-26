"""Integration tests for NASA-LSP CLI behavior with multiple files."""

from __future__ import annotations

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from nasa_lsp.cli import app

runner = CliRunner()


def test_analyze_directory_with_mixed_files() -> None:
    """CLI analyzes directory with clean and violating files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        clean_file = tmp_path / "clean.py"
        _ = clean_file.write_text(
            """
def clean_function():
    assert True
    assert False
    return 42
"""
        )

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

        result = runner.invoke(app, ["lint", str(tmp_path)])

        assert result.exit_code == 1
        assert "violation" in result.stdout.lower()


def test_exclude_common_directories() -> None:
    """CLI excludes common directories from analysis."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        main_file = tmp_path / "main.py"
        _ = main_file.write_text(
            """
def bad():
    eval("test")
"""
        )

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

        result = runner.invoke(app, ["lint", str(tmp_path)])

        assert result.exit_code == 1
        assert "main.py" in result.stdout
        for excluded in [".venv", "__pycache__", "node_modules", ".git"]:
            assert excluded not in result.stdout or f"{excluded}/test.py" not in result.stdout
