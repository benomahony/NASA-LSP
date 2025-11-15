from __future__ import annotations

import ast
import logging
from typing import List

from lsprotocol import types
from pygls.cli import start_server
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument


server = LanguageServer("nasa-python-lsp", "0.2.0")


class NasaVisitor(ast.NodeVisitor):
    """Walk AST and collect NASA-style diagnostics."""

    def __init__(self, uri: str, text: str):
        self.uri = uri
        self.text = text
        self.lines = text.splitlines()
        self.diagnostics: List[types.Diagnostic] = []
        assert self.uri
        assert self.text
        assert self.diagnostics == []

    @staticmethod
    def _pos(lineno: int, col: int) -> types.Position:
        # ast lineno is 1-based, LSPa is 0-based
        assert lineno
        assert col
        return types.Position(line=lineno - 1, character=col)

    def _range_for_node(self, node: ast.AST) -> types.Range:
        assert node
        assert hasattr(node, "lineno")
        assert hasattr(node, "col_offset")
        assert hasattr(node, "end_lineno")
        assert hasattr(node, "end_col_offset")

        lineno = node.lineno
        col = node.col_offset
        end_lineno = node.end_lineno
        end_col = node.end_col_offset

        return types.Range(
            start=self._pos(lineno, col),
            end=self._pos(end_lineno, end_col),
        )

    def _range_for_func_name(self, node: ast.FunctionDef) -> types.Range:
        """Highlight just the function name in 'def foo(...)'."""
        assert node
        assert hasattr(node, "lineno")
        assert hasattr(node, "col_offset")
        lineno = node.lineno
        col = node.col_offset

        if not (0 <= lineno - 1 < len(self.lines)):
            return self._range_for_node(node)

        line_text = self.lines[lineno - 1]

        def_kw = "def"
        idx = line_text.find(def_kw, col)
        if idx == -1:
            # fallback: underline from col_offset with name length
            name = node.name
            start_col = col
            end_col = start_col + len(name)
            return types.Range(
                start=self._pos(lineno, start_col),
                end=self._pos(lineno, end_col),
            )

        name_start = idx + len(def_kw)
        while name_start < len(line_text) and line_text[name_start].isspace():
            name_start += 1

        name = node.name
        name_end = name_start + len(name)

        return types.Range(
            start=self._pos(lineno, name_start),
            end=self._pos(lineno, name_end),
        )

    def _add_diag(self, range: types.Range, message: str, code: str) -> None:
        assert range
        assert message
        assert code
        self.diagnostics.append(
            types.Diagnostic(
                range=range,
                message=message,
                source="NASA",
                severity=types.DiagnosticSeverity.Warning,
                code=code,
            )
        )

    # NASA01-A — restricted subset (forbidden builtins)
    def visit_Call(self, node: ast.Call) -> None:
        assert node

        if isinstance(node.func, ast.Name):
            name = node.func.id
            target_node = node.func
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
            target_node = node.func

        assert name
        assert target_node

        forbidden = {
            "eval",
            "exec",
            "compile",
            "globals",
            "locals",
            "__import__",
            "setattr",
            "getattr",
        }

        if name in forbidden:
            self._add_diag(
                self._range_for_node(target_node),
                f"Call to forbidden API '{name}' (NASA01: restricted subset)",
                "NASA01-A",
            )

        self.generic_visit(node)

    # NASA02 — flag while True
    def visit_While(self, node: ast.While) -> None:
        assert node
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            range = self._range_for_node(node)
            assert range
            self._add_diag(
                range,
                "Unbounded loop 'while True' (NASA02: loops must be bounded)",
                "NASA02",
            )

        self.generic_visit(node)

    # NASA01-B — forbid direct recursion
    # NASA05 — require ≥2 assert statements in every function
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        func_name = node.name
        assert func_name
        func_name_range = self._range_for_func_name(node)
        assert func_name_range

        # NASA01-B: direct recursion detection
        calls_self = False
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.ClassDef)):
                continue
            for sub_node in ast.walk(stmt):
                if (
                    isinstance(sub_node, ast.Call)
                    and isinstance(sub_node.func, ast.Name)
                    and sub_node.func.id == func_name
                ):
                    calls_self = True
                    break
            if calls_self:
                break
        if calls_self:
            self._add_diag(
                func_name_range,
                f"Recursive call to '{func_name}' (NASA01: no recursion)",
                "NASA01-B",
            )

        # NASA04: No function longer that 60 lines
        if node.end_lineno - node.lineno >= 60:
            self._add_diag(
                func_name_range,
                f"Function '{func_name}' longer than 60 lines (NASA04: No function longer than 60 lines)",
                "NASA04",
            )

        # NASA05: at least 2 assert statements
        assert_count = 0
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.ClassDef)):
                continue  # Skip nested function/class definitions; their asserts are counted when they are visited as separate nodes
            for sub_node in ast.walk(stmt):
                if isinstance(sub_node, ast.Assert):
                    assert_count += 1

        if assert_count < 2:
            self._add_diag(
                func_name_range,
                (
                    f"Function '{func_name}' has only {assert_count} assert(s); "
                    f"expected at least {2} asserts "
                    f"(NASA05: use assertions to detect impossible conditions)"
                ),
                "NASA05",
            )

        self.generic_visit(node)


def analyze(uri: str, text: str) -> List[types.Diagnostic]:
    """Return NASA-style diagnostics for valid Python code."""
    assert uri
    assert text
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []

    visitor = NasaVisitor(uri, text)
    visitor.visit(tree)
    return visitor.diagnostics


def run_checks(ls: LanguageServer, doc: TextDocument) -> None:
    assert ls
    assert doc
    text = doc.source
    diagnostics = analyze(doc.uri, text)

    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(
            uri=doc.uri,
            version=doc.version,
            diagnostics=diagnostics,
        )
    )


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params) -> None:
    assert ls
    assert ls.workspace
    run_checks(ls, ls.workspace.get_text_document(params.text_document.uri))


@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params) -> None:
    assert ls
    assert ls.workspace
    run_checks(ls, ls.workspace.get_text_document(params.text_document.uri))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    start_server(server)
