from __future__ import annotations

from pathlib import Path

import typer

from nasa_lsp.analyzer import analyze, Diagnostic

app = typer.Typer(no_args_is_help=True)


def _format_diagnostic(path: Path, diag: Diagnostic) -> str:
    assert path
    assert diag
    line = diag.range.start.line + 1
    col = diag.range.start.character + 1
    return f"{path}:{line}:{col}: {diag.code} {diag.message}"


@app.command()
def lint(paths: list[Path] = typer.Argument(..., help="Files or directories to lint")) -> None:
    """Check Python files for NASA Power of 10 rule violations."""
    files: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".py":
            files.append(p)
        elif p.is_dir():
            files.extend(p.rglob("*.py"))

    total_errors = 0
    for file in sorted(files):
        diagnostics = analyze(file.read_text())
        for diag in diagnostics:
            typer.echo(_format_diagnostic(file, diag))
        total_errors += len(diagnostics)

    if total_errors > 0:
        raise typer.Exit(1)


@app.command()
def serve() -> None:
    """Start the Language Server Protocol server."""
    from nasa_lsp.server import serve as start_server
    start_server()


if __name__ == "__main__":
    app()
