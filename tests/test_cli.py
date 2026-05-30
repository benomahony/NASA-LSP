from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from typer.testing import CliRunner

from nasa_lsp.analyzer import Diagnostic, Position, Range
from nasa_lsp.cli import (
    EXCLUDED_DIRS,
    analyze_file,
    app,
    discover_files,
    format_diagnostic,
    is_supported,
    should_exclude,
)

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
    assert isinstance(result, str)


def test_format_diagnostic_first_line() -> None:
    path = Path("file.py")
    diag = Diagnostic(
        range=Range(start=Position(line=0, character=0), end=Position(line=0, character=5)),
        message="Error",
        code="ERR",
    )
    result = format_diagnostic(path, diag)
    assert result == "file.py:1:1: ERR Error"
    assert isinstance(result, str)


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


def test_stats_no_args() -> None:
    result = runner.invoke(app, ["stats"])
    assert result.exit_code == 0
    assert "NASA Function Audit" in result.stdout


def test_stats_single_file() -> None:
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        _ = test_file.write_text("""
def foo():
    assert True
    assert False
    return 1

def bar():
    assert True
    return 2
""")
        result = runner.invoke(app, ["stats", str(test_file)])
        assert result.exit_code == 0
        assert "NASA Function Audit" in result.stdout
        assert "foo" in result.stdout
        assert "bar" in result.stdout


def test_stats_directory() -> None:
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        _ = test_file.write_text("""
def example():
    assert True
    assert False
""")
        result = runner.invoke(app, ["stats", str(tmpdir)])
        assert result.exit_code == 0
        assert "example" in result.stdout


def test_stats_excludes_venv() -> None:
    with TemporaryDirectory() as tmpdir:
        venv_dir = Path(tmpdir) / ".venv" / "lib"
        venv_dir.mkdir(parents=True)
        venv_file = venv_dir / "bad.py"
        _ = venv_file.write_text("def foo(): pass")
        result = runner.invoke(app, ["stats", str(tmpdir)])
        assert result.exit_code == 0
        assert ".venv" not in result.stdout


def test_stats_multiple_files() -> None:
    with TemporaryDirectory() as tmpdir:
        file1 = Path(tmpdir) / "file1.py"
        file2 = Path(tmpdir) / "file2.py"
        _ = file1.write_text("def func1(): assert True; assert False")
        _ = file2.write_text("def func2(): assert True; assert False")
        result = runner.invoke(app, ["stats", str(file1), str(file2)])
        assert result.exit_code == 0
        assert "func1" in result.stdout
        assert "func2" in result.stdout


def test_stats_shows_line_counts() -> None:
    with TemporaryDirectory() as tmpdir:
        test_file = Path(tmpdir) / "test.py"
        _ = test_file.write_text("""
def short():
    assert True
    assert False
    return 1
""")
        result = runner.invoke(app, ["stats", str(test_file)])
        assert result.exit_code == 0
        assert "short" in result.stdout


def test_stats_empty_directory() -> None:
    with TemporaryDirectory() as tmpdir:
        result = runner.invoke(app, ["stats", str(tmpdir)])
        assert result.exit_code == 0
        assert "NASA Function Audit" in result.stdout


def test_serve_command_imports() -> None:
    result = runner.invoke(app, ["serve", "--help"])
    assert result.exit_code == 0
    assert "Language Server Protocol" in result.stdout


def test_is_supported_recognises_multiple_languages() -> None:
    assert is_supported(Path("main.py"))
    assert is_supported(Path("lib.rs"))
    assert is_supported(Path("server.go"))
    assert is_supported(Path("app.ts"))
    assert not is_supported(Path("notes.txt"))


def test_discover_files_mixed_languages() -> None:
    with TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        _ = (root / "a.py").write_text("def f(): pass")
        _ = (root / "b.rs").write_text("fn f() {}")
        _ = (root / "c.go").write_text("func f() {}")
        _ = (root / "ignore.txt").write_text("nope")
        found = {p.name for p in discover_files([root])}
        assert found == {"a.py", "b.rs", "c.go"}
        assert "ignore.txt" not in found


def test_analyze_file_uses_extension_language() -> None:
    with TemporaryDirectory() as tmpdir:
        rust_file = Path(tmpdir) / "spin.rs"
        _ = rust_file.write_text("fn spin() {\n    loop {}\n}")
        diagnostics, _ = analyze_file(rust_file)
        assert any(d.code == "NASA02" for d in diagnostics)
        assert isinstance(diagnostics, list)


def test_lint_rust_file_with_violations() -> None:
    with TemporaryDirectory() as tmpdir:
        rust_file = Path(tmpdir) / "spin.rs"
        _ = rust_file.write_text("fn spin() {\n    loop {}\n}")
        result = runner.invoke(app, ["lint", str(rust_file)])
        assert result.exit_code == 1
        assert "NASA02" in result.stdout


def test_lint_clean_go_file() -> None:
    with TemporaryDirectory() as tmpdir:
        go_file = Path(tmpdir) / "ok.go"
        _ = go_file.write_text("func f(n int) {\n\tfor i := 0; i < n; i++ {\n\t}\n}")
        result = runner.invoke(app, ["lint", str(go_file)])
        assert result.exit_code == 0
        assert "no violations" in result.stdout


def test_stats_rust_file() -> None:
    with TemporaryDirectory() as tmpdir:
        rust_file = Path(tmpdir) / "lib.rs"
        _ = rust_file.write_text("fn compute(a: i32) -> i32 {\n    a + 1\n}")
        result = runner.invoke(app, ["stats", str(rust_file)])
        assert result.exit_code == 0
        assert "compute" in result.stdout
