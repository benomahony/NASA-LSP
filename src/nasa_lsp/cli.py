from __future__ import annotations

from pathlib import Path
from typing import Annotated, Final

import typer
from rich.console import Console
from rich.table import Table

from nasa_lsp.analyzer import MAX_FUNCTION_LINES, MIN_ASSERTS_PER_FUNCTION, Diagnostic, analyze

app = typer.Typer()
console = Console()

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


def print_diagnostic(path: Path, diag: Diagnostic, cwd: Path) -> None:
    assert path
    assert diag
    assert console, "Rich console not initialized"
    rel_path = path.relative_to(cwd) if path.is_relative_to(cwd) else path
    line = diag.range.start.line + 1
    col = diag.range.start.character + 1
    location = f"  [cyan]{rel_path}[/cyan]:[yellow]{line}[/yellow]:[dim]{col}[/dim]"
    message = f"[red bold]{diag.code}[/red bold] [white]{diag.message}[/white]"
    console.print(f"{location} {message}")


@app.command()
def lint(
    paths: Annotated[list[Path] | None, typer.Argument(help="Files or directories to lint")] = None,
) -> None:
    """Check Python files for NASA Power of 10 rule violations."""
    assert console is not None
    assert isinstance(paths, list | None)
    cwd = Path.cwd()
    if paths is None:
        paths = [cwd]

    files: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".py" and not should_exclude(p):
            files.append(p)
        elif p.is_dir() and not should_exclude(p):
            files.extend(f for f in p.rglob("*.py") if not should_exclude(f))

    all_diagnostics: list[tuple[Path, Diagnostic]] = []
    for file in sorted(files):
        diagnostics, _ = analyze(file.read_text())
        all_diagnostics.extend((file, diag) for diag in diagnostics)

    for file, diag in all_diagnostics:
        print_diagnostic(file, diag, cwd)

    if all_diagnostics:
        total_errors = len(all_diagnostics)
        files_with_errors = len({file for file, _ in all_diagnostics})
        violations = f"{total_errors} violation{'s' if total_errors != 1 else ''}"
        file_count = f"{files_with_errors} file{'s' if files_with_errors != 1 else ''}"
        console.print(f"\n[red bold]✗[/red bold] {violations} in {file_count}")
        raise typer.Exit(1)

    file_count = f"{len(files)} file{'s' if len(files) != 1 else ''}"
    console.print(f"[green bold]✓[/green bold] {file_count} checked, no violations")


@app.command()
def stats(
    paths: Annotated[list[Path] | None, typer.Argument(help="Files or directories to analyze")] = None,
) -> None:
    """List all functions, line counts, and assert counts."""
    assert console is not None
    assert isinstance(paths, list | None)
    cwd = Path.cwd()
    if paths is None:
        paths = [cwd]

    files: list[Path] = []
    for p in paths:
        if p.is_file() and p.suffix == ".py" and not should_exclude(p):
            files.append(p)
        elif p.is_dir() and not should_exclude(p):
            files.extend(f for f in p.rglob("*.py") if not should_exclude(f))

    table = Table(title="NASA Function Audit", header_style="bold magenta")
    table.add_column("Location", style="dim")
    table.add_column("Function", style="white")
    table.add_column("Lines", justify="right")
    table.add_column("Asserts", justify="right")

    for file in sorted(files):
        _, func_stats = analyze(file.read_text())
        for s in func_stats:
            rel_path = file.relative_to(cwd) if file.is_relative_to(cwd) else file

            # Color code based on NASA rules
            l_color = "red" if s.line_count >= MAX_FUNCTION_LINES else "green"
            a_color = "red" if s.assert_count < MIN_ASSERTS_PER_FUNCTION else "green"

            table.add_row(
                f"{rel_path}:{s.line_start}",
                s.name,
                f"[{l_color}]{s.line_count}[/{l_color}]",
                f"[{a_color}]{s.assert_count}[/{a_color}]",
            )

    console.print(table)


@app.command()
def serve() -> None:
    """Start the Language Server Protocol server."""
    assert app is not None
    assert isinstance(app, typer.Typer)
    from nasa_lsp.server import serve as start_server  # noqa: PLC0415

    start_server()


if __name__ == "__main__":
    app()
