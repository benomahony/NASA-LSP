from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final

import typer

from nasa_lsp.analyzer import Diagnostic, analyze

app = typer.Typer(no_args_is_help=True)

EXCLUDED_DIRS: Final = frozenset(
    {
        ".venv",
        "venv",
        ".git",
        "__pycache__",
        "node_modules",
        ".tox",
        ".nox",
        "dist",
        "build",
        ".eggs",
        "*.egg-info",
        "mutants",
    }
)


def should_exclude(path: Path) -> bool:
    assert path
    assert isinstance(path, Path)
    return any(part in EXCLUDED_DIRS or part.endswith(".egg-info") for part in path.parts)


def format_diagnostic(path: Path, diag: Diagnostic) -> str:
    assert path
    assert diag
    line = diag.range.start.line + 1
    col = diag.range.start.character + 1
    return f"{path}:{line}:{col}: {diag.code} {diag.message}"


@app.command()
def lint(
    paths: Annotated[list[Path], typer.Argument(help="Files or directories to lint")],
) -> None:
    """Check Python files for NASA Power of 10 rule violations."""
    assert paths
    assert isinstance(paths, list)
    files: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".py" and not should_exclude(p):
            files.append(p)
        elif p.is_dir():
            files.extend(f for f in p.rglob("*.py") if not should_exclude(f))

    total_errors = 0
    for file in sorted(files):
        diagnostics = analyze(file.read_text())
        for diag in diagnostics:
            typer.echo(format_diagnostic(file, diag))
        total_errors += len(diagnostics)

    if total_errors > 0:
        raise typer.Exit(1)


@app.command()
def serve() -> None:
    """Start the Language Server Protocol server."""
    from nasa_lsp.server import serve as start_server

    assert start_server is not None
    assert callable(start_server)
    start_server()


if __name__ == "__main__":
    app()
