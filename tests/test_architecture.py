from __future__ import annotations

import ast
from pathlib import Path

SRC_DIR = Path(__file__).parent.parent / "src" / "nasa_lsp"


def get_imports(filepath: Path) -> set[str]:
    assert filepath.exists()
    assert filepath.is_file()
    tree = ast.parse(filepath.read_text())
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


def test_cli_does_not_import_server_at_module_level() -> None:
    cli_path = SRC_DIR / "cli.py"
    assert cli_path.exists()
    assert cli_path.is_file()
    tree = ast.parse(cli_path.read_text())

    top_level_imports: set[str] = set()
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top_level_imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module:
            top_level_imports.add(node.module)

    assert "nasa_lsp.server" not in top_level_imports, "cli.py must not import server at module level"
    assert "pygls" not in top_level_imports, "cli.py must not import pygls"
    assert "lsprotocol" not in top_level_imports, "cli.py must not import lsprotocol"


def test_analyzer_does_not_import_lsp_libraries() -> None:
    analyzer_path = SRC_DIR / "analyzer.py"
    assert analyzer_path.exists()
    assert analyzer_path.is_file()
    imports = get_imports(analyzer_path)

    assert "pygls" not in imports, "analyzer.py must not import pygls"
    assert "lsprotocol" not in imports, "analyzer.py must not import lsprotocol"
    assert "typer" not in imports, "analyzer.py must not import typer"


def test_server_imports_analyzer() -> None:
    server_path = SRC_DIR / "server.py"
    assert server_path.exists()
    assert server_path.is_file()
    tree = ast.parse(server_path.read_text())

    imports_analyzer = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module == "nasa_lsp.analyzer":
            imports_analyzer = True
            break

    assert imports_analyzer, "server.py must import from nasa_lsp.analyzer"


def test_no_mocks_in_tests() -> None:
    tests_dir = Path(__file__).parent
    assert tests_dir.exists()
    assert tests_dir.is_dir()

    mock_violations: list[tuple[Path, str]] = []
    mock_modules = {"mock", "unittest.mock", "pytest_mock", "mocker"}

    for test_file in tests_dir.glob("test_*.py"):
        assert test_file.exists()
        assert test_file.is_file()
        tree = ast.parse(test_file.read_text())

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    module = alias.name.split(".")[0]
                    full_module = alias.name
                    if module in mock_modules or full_module in mock_modules:
                        mock_violations.append((test_file, alias.name))
            elif isinstance(node, ast.ImportFrom) and node.module:
                module = node.module.split(".")[0]
                if module in mock_modules or node.module in mock_modules:
                    mock_violations.append((test_file, node.module))

    assert not mock_violations, f"Tests must not use mocks. Found: {mock_violations}"
