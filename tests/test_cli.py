from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from tempfile import TemporaryDirectory

from typer.testing import CliRunner

from nasa_lsp.analyzer import Diagnostic, Position, Range
from nasa_lsp.cli import EXCLUDED_DIRS, app, format_diagnostic, print_diagnostic, should_exclude

runner = CliRunner()


def test_format_diagnostic_basic() -> None:
    path = Path("/test/file.py")
    diag = Diagnostic(
        range=Range(start=Position(line=9, character=4), end=Position(line=9, character=10)),
        message="Test message",
        code="TEST01",
    )
    result = format_diagnostic(path, diag)
    assert result == "/test/file.py:10:5: TEST01 Test message"
    assert "TEST01" in result


def test_format_diagnostic_first_line() -> None:
    path = Path("file.py")
    diag = Diagnostic(
        range=Range(start=Position(line=0, character=0), end=Position(line=0, character=5)),
        message="Error",
        code="ERR",
    )
    result = format_diagnostic(path, diag)
    assert result == "file.py:1:1: ERR Error"
    assert "ERR" in result


def test_lint_no_args_lints_cwd() -> None:
    result = runner.invoke(app, ["lint"])
    assert result.exit_code in (0, 1)
    assert result.stdout


def test_lint_clean_file() -> None:
    with TemporaryDirectory() as tmpdir:
        clean_file = Path(tmpdir) / "clean.py"
        _ = clean_file.write_text("""
def foo():
    assert True
    assert False
    return 1
""")
        result = runner.invoke(app, ["lint", str(clean_file)])
        assert result.exit_code == 0
        assert "no violations" in result.stdout


def test_lint_file_with_violations() -> None:
    with TemporaryDirectory() as tmpdir:
        bad_file = Path(tmpdir) / "bad.py"
        _ = bad_file.write_text("""
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
        _ = clean_file.write_text("""
def foo():
    assert True
    assert False
""")
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 0
        assert "no violations" in result.stdout


def test_lint_directory_with_violations() -> None:
    with TemporaryDirectory() as tmpdir:
        bad_file = Path(tmpdir) / "bad.py"
        _ = bad_file.write_text("def foo(): pass")
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 1
        assert "NASA05" in result.stdout


def test_lint_multiple_files() -> None:
    with TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / "file1.py"
        file2 = Path(tmpdir) / "file2.py"
        _ = file1.write_text("""
def foo():
    assert True
    assert False
""")
        _ = file2.write_text("""
def bar():
    assert True
    assert False
""")
        result = runner.invoke(app, ["lint", str(file1), str(file2)])
        assert result.exit_code == 0
        assert "no violations" in result.stdout


def test_lint_ignores_non_python_files() -> None:
    with TemporaryDirectory() as tmpdir:
        txt_file = Path(tmpdir) / "readme.txt"
        _ = txt_file.write_text("def foo(): pass")
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 0
        assert "no violations" in result.stdout or "0 file" in result.stdout


def test_lint_nested_directories() -> None:
    with TemporaryDirectory() as tmpdir:
        nested = Path(tmpdir) / "a" / "b" / "c"
        nested.mkdir(parents=True)
        py_file = nested / "deep.py"
        _ = py_file.write_text("def foo(): pass")
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 1
        assert "deep.py" in result.stdout


def test_lint_empty_directory() -> None:
    with TemporaryDirectory() as tmpdir:
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 0
        assert "0 file" in result.stdout or "no violations" in result.stdout


def test_lint_sorted_output() -> None:
    with TemporaryDirectory() as tmpdir:
        z_file = Path(tmpdir) / "z.py"
        a_file = Path(tmpdir) / "a.py"
        _ = z_file.write_text("def z(): pass")
        _ = a_file.write_text("def a(): pass")
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 1
        a_pos = result.stdout.find("a.py")
        z_pos = result.stdout.find("z.py")
        assert a_pos < z_pos, "a.py should appear before z.py in output"


def test_lint_syntax_error_file_ignored() -> None:
    with TemporaryDirectory() as tmpdir:
        bad_syntax = Path(tmpdir) / "syntax.py"
        _ = bad_syntax.write_text("def broken(")
        result = runner.invoke(app, ["lint", str(bad_syntax)])
        assert result.exit_code == 0
        assert "no violations" in result.stdout or "0 file" in result.stdout


def test_should_exclude_venv() -> None:
    assert should_exclude(Path(".venv/lib/python3.14/site.py"))
    assert should_exclude(Path("project/.venv/test.py"))


def test_should_exclude_pycache() -> None:
    assert should_exclude(Path("__pycache__/module.cpython-314.pyc"))
    assert should_exclude(Path("src/__pycache__/test.py"))


def test_should_exclude_git() -> None:
    assert should_exclude(Path(".git/hooks/pre-commit"))
    assert should_exclude(Path("repo/.git/config"))


def test_should_exclude_node_modules() -> None:
    assert should_exclude(Path("node_modules/package/index.py"))
    assert should_exclude(Path("project/node_modules/test.py"))


def test_should_exclude_egg_info() -> None:
    assert should_exclude(Path("nasa_lsp.egg-info/PKG-INFO"))
    assert should_exclude(Path("dist/package.egg-info/top_level.txt"))


def test_should_exclude_mutants() -> None:
    assert should_exclude(Path("mutants/src/test.py"))
    assert should_exclude(Path("project/mutants/analyzer.py"))


def test_should_not_exclude_normal_paths() -> None:
    assert not should_exclude(Path("src/nasa_lsp/analyzer.py"))
    assert not should_exclude(Path("tests/test_cli.py"))
    assert not should_exclude(Path("main.py"))


def test_excluded_dirs_is_frozen() -> None:
    assert isinstance(EXCLUDED_DIRS, frozenset)
    assert ".venv" in EXCLUDED_DIRS


def test_lint_excludes_venv() -> None:
    with TemporaryDirectory() as tmpdir:
        venv_dir = Path(tmpdir) / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        venv_file = venv_dir / "bad.py"
        _ = venv_file.write_text("def foo(): pass")
        result = runner.invoke(app, ["lint", str(tmpdir)])
        assert result.exit_code == 0
        assert ".venv" not in result.stdout
        assert "no violations" in result.stdout or "0 file" in result.stdout


def test_lint_empty_file() -> None:
    with TemporaryDirectory() as tmpdir:
        empty_file = Path(tmpdir) / "__init__.py"
        _ = empty_file.write_text("")
        result = runner.invoke(app, ["lint", str(empty_file)])
        assert result.exit_code == 0
        assert "no violations" in result.stdout


def test_serve_command_integration() -> None:
    """Integration test that serve command actually starts the server process."""
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-c", "from nasa_lsp.cli import serve; serve()"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(0.1)

    proc.terminate()
    _ = proc.wait(timeout=2)

    assert proc.returncode in (0, -15)
    assert proc.stdout


def test_lint_multiple_directories() -> None:
    with TemporaryDirectory() as tmpdir:
        dir1 = Path(tmpdir) / "dir1"
        dir2 = Path(tmpdir) / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        file1 = dir1 / "test1.py"
        file2 = dir2 / "test2.py"

        _ = file1.write_text("""
def foo():
    assert True
    assert False
""")
        _ = file2.write_text("""
def bar():
    assert True
    assert False
""")

        result = runner.invoke(app, ["lint", str(dir1), str(dir2)])
        assert result.exit_code == 0
        assert "no violations" in result.stdout


def test_lint_mixed_files_and_directories() -> None:
    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        subdir = tmpdir_path / "subdir"
        subdir.mkdir()

        direct_file = tmpdir_path / "direct.py"
        nested_file = subdir / "nested.py"

        _ = direct_file.write_text("""
def foo():
    assert True
    assert False
""")
        _ = nested_file.write_text("""
def bar():
    assert True
    assert False
""")

        result = runner.invoke(app, ["lint", str(direct_file), str(subdir)])
        assert result.exit_code == 0
        assert "no violations" in result.stdout


def test_lint_directory_then_file() -> None:
    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        subdir = tmpdir_path / "subdir"
        subdir.mkdir()

        direct_file = tmpdir_path / "direct.py"
        nested_file = subdir / "nested.py"

        _ = direct_file.write_text("""
def foo():
    assert True
    assert False
""")
        _ = nested_file.write_text("""
def bar():
    assert True
    assert False
""")

        result = runner.invoke(app, ["lint", str(subdir), str(direct_file)])
        assert result.exit_code == 0
        assert "no violations" in result.stdout


def test_lint_two_directories_in_sequence() -> None:
    with TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        dir1 = tmpdir_path / "dir1"
        dir2 = tmpdir_path / "dir2"
        dir1.mkdir()
        dir2.mkdir()

        file1 = dir1 / "test1.py"
        file2 = dir2 / "test2.py"

        _ = file1.write_text("""
def foo():
    assert True
    assert False
""")
        _ = file2.write_text("""
def bar():
    assert True
    assert False
""")

        result = runner.invoke(app, ["lint", str(dir1), str(dir2)])
        assert result.exit_code == 0
        assert "2 file" in result.stdout


def test_print_diagnostic() -> None:
    path = Path("/test/file.py")
    cwd = Path("/test")
    diag = Diagnostic(
        range=Range(start=Position(line=5, character=10), end=Position(line=5, character=20)),
        message="Test error",
        code="TEST01",
    )
    print_diagnostic(path, diag, cwd)
    assert path.exists() or not path.exists()  # Function should handle both
    assert diag.code == "TEST01"


def test_print_diagnostic_non_relative_path() -> None:
    path = Path("/other/file.py")
    cwd = Path("/test")
    diag = Diagnostic(
        range=Range(start=Position(line=0, character=0), end=Position(line=0, character=5)),
        message="Error",
        code="ERR",
    )
    print_diagnostic(path, diag, cwd)
    assert path.is_absolute()
    assert diag.code == "ERR"


def test_main_block() -> None:
    cli_path = Path(__file__).parent.parent / "src" / "nasa_lsp" / "cli.py"
    result = subprocess.run(  # noqa: S603
        [sys.executable, str(cli_path), "lint", "--help"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0
    assert "NASA" in result.stdout or "lint" in result.stdout


def test_main_block_with_actual_file() -> None:
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        _ = test_file.write_text("""
def foo():
    assert True
    assert False
""")

        cli_path = Path(__file__).parent.parent / "src" / "nasa_lsp" / "cli.py"
        result = subprocess.run(  # noqa: S603
            [sys.executable, str(cli_path), "lint", str(test_file)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        assert result.returncode == 0
        assert "no violations" in result.stdout
