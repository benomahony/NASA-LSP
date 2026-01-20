from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from typer.testing import CliRunner

from nasa_lsp.analyzer import Diagnostic, Position, Range
from nasa_lsp.cli import _format_diagnostic, app

runner = CliRunner()


def test_format_diagnostic_basic() -> None:
    path = Path("/test/file.py")
    diag = Diagnostic(
        range=Range(start=Position(line=9, character=4), end=Position(line=9, character=10)),
        message="Test message",
        code="TEST01",
    )
    result = _format_diagnostic(path, diag)
    assert result == "/test/file.py:10:5: TEST01 Test message"
    assert isinstance(result, str)


def test_format_diagnostic_first_line() -> None:
    path = Path("file.py")
    diag = Diagnostic(
        range=Range(start=Position(line=0, character=0), end=Position(line=0, character=5)),
        message="Error",
        code="ERR",
    )
    result = _format_diagnostic(path, diag)
    assert result == "file.py:1:1: ERR Error"


def test_lint_no_args_shows_help() -> None:
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "Usage" in result.stdout or "lint" in result.stdout


def test_lint_clean_file() -> None:
    with TemporaryDirectory() as tmpdir:
        clean_file = Path(tmpdir) / "clean.py"
        clean_file.write_text("""
def foo():
    assert True
    assert False
    return 1
""")
        result = runner.invoke(app, ["lint", str(clean_file)])
        assert result.exit_code == 0
        assert result.stdout == ""


def test_lint_file_with_violations() -> None:
    with TemporaryDirectory() as tmpdir:
        bad_file = Path(tmpdir) / "bad.py"
        bad_file.write_text("""
def foo():
    eval("1+1")
""")
        result = runner.invoke(app, ["lint", str(bad_file)])
        assert result.exit_code == 1
        assert "NASA01-A" in result.stdout
        assert "NASA05" in result.stdout


def test_lint_directory() -> None:
    with TemporaryDirectory() as tmpdir:
        subdir = Path(tmpdir) / "subdir"
        subdir.mkdir()
        clean_file = subdir / "clean.py"
        clean_file.write_text("""
def foo():
    assert True
    assert False
""")
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 0


def test_lint_directory_with_violations() -> None:
    with TemporaryDirectory() as tmpdir:
        bad_file = Path(tmpdir) / "bad.py"
        bad_file.write_text("def foo(): pass")
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 1
        assert "NASA05" in result.stdout


def test_lint_multiple_files() -> None:
    with TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / "file1.py"
        file2 = Path(tmpdir) / "file2.py"
        file1.write_text("""
def foo():
    assert True
    assert False
""")
        file2.write_text("""
def bar():
    assert True
    assert False
""")
        result = runner.invoke(app, ["lint", str(file1), str(file2)])
        assert result.exit_code == 0


def test_lint_ignores_non_python_files() -> None:
    with TemporaryDirectory() as tmpdir:
        txt_file = Path(tmpdir) / "readme.txt"
        txt_file.write_text("def foo(): pass")
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 0


def test_lint_nested_directories() -> None:
    with TemporaryDirectory() as tmpdir:
        nested = Path(tmpdir) / "a" / "b" / "c"
        nested.mkdir(parents=True)
        py_file = nested / "deep.py"
        py_file.write_text("def foo(): pass")
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 1
        assert "deep.py" in result.stdout


def test_lint_empty_directory() -> None:
    with TemporaryDirectory() as tmpdir:
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 0


def test_lint_sorted_output() -> None:
    with TemporaryDirectory() as tmpdir:
        z_file = Path(tmpdir) / "z.py"
        a_file = Path(tmpdir) / "a.py"
        z_file.write_text("def z(): pass")
        a_file.write_text("def a(): pass")
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 1
        lines = result.stdout.strip().split("\n")
        assert "a.py" in lines[0]
        assert "z.py" in lines[1]


def test_lint_syntax_error_file_ignored() -> None:
    with TemporaryDirectory() as tmpdir:
        bad_syntax = Path(tmpdir) / "syntax.py"
        bad_syntax.write_text("def broken(")
        result = runner.invoke(app, ["lint", str(bad_syntax)])
        assert result.exit_code == 0
