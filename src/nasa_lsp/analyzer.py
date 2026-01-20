from __future__ import annotations

import ast
from dataclasses import dataclass


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


class NasaVisitor(ast.NodeVisitor):
    def __init__(self, text: str):
        assert text
        self.text = text
        self.lines = text.splitlines()
        self.diagnostics: list[Diagnostic] = []

    @staticmethod
    def _pos(lineno: int, col: int) -> Position:
        assert lineno
        assert col >= 0
        return Position(line=lineno - 1, character=col)

    def _range_for_node(self, node: ast.AST) -> Range:
        assert node
        assert hasattr(node, "lineno")
        assert hasattr(node, "col_offset")
        assert hasattr(node, "end_lineno")
        assert hasattr(node, "end_col_offset")
        return Range(
            start=self._pos(node.lineno, node.col_offset),
            end=self._pos(node.end_lineno, node.end_col_offset),
        )

    def _range_for_func_name(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Range:
        assert node
        assert hasattr(node, "lineno")
        assert hasattr(node, "col_offset")
        lineno = node.lineno
        col = node.col_offset

        if not (0 <= lineno - 1 < len(self.lines)):
            return self._range_for_node(node)

        line_text = self.lines[lineno - 1]
        def_kw = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
        idx = line_text.find(def_kw, col)
        if idx == -1:
            return Range(
                start=self._pos(lineno, col),
                end=self._pos(lineno, col + len(node.name)),
            )

        name_start = idx + len(def_kw)
        while name_start < len(line_text) and line_text[name_start].isspace():
            name_start += 1

        return Range(
            start=self._pos(lineno, name_start),
            end=self._pos(lineno, name_start + len(node.name)),
        )

    def _add_diag(self, range: Range, message: str, code: str) -> None:
        assert range
        assert message
        assert code
        self.diagnostics.append(Diagnostic(range=range, message=message, code=code))

    def visit_Call(self, node: ast.Call) -> None:
        assert node
        name: str | None = None
        target_node: ast.AST | None = None

        if isinstance(node.func, ast.Name):
            name = node.func.id
            target_node = node.func
        elif isinstance(node.func, ast.Attribute):
            name = node.func.attr
            target_node = node.func

        if name and target_node:
            forbidden = {"eval", "exec", "compile", "globals", "locals", "__import__", "setattr", "getattr"}
            if name in forbidden:
                self._add_diag(
                    self._range_for_node(target_node),
                    f"Call to forbidden API '{name}' (NASA01: restricted subset)",
                    "NASA01-A",
                )

        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        assert node
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            self._add_diag(
                self._range_for_node(node),
                "Unbounded loop 'while True' (NASA02: loops must be bounded)",
                "NASA02",
            )
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        func_name = node.name
        assert func_name
        func_name_range = self._range_for_func_name(node)

        calls_self = False
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for sub_node in ast.walk(stmt):
                if isinstance(sub_node, ast.Call) and isinstance(sub_node.func, ast.Name) and sub_node.func.id == func_name:
                    calls_self = True
                    break
            if calls_self:
                break

        if calls_self:
            self._add_diag(func_name_range, f"Recursive call to '{func_name}' (NASA01: no recursion)", "NASA01-B")

        if node.end_lineno - node.lineno >= 60:
            self._add_diag(func_name_range, f"Function '{func_name}' longer than 60 lines (NASA04: No function longer than 60 lines)", "NASA04")

        assert_count = 0
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for sub_node in ast.walk(stmt):
                if isinstance(sub_node, ast.Assert):
                    assert_count += 1

        if assert_count < 2:
            self._add_diag(
                func_name_range,
                f"Function '{func_name}' has only {assert_count} assert(s); expected at least 2 asserts (NASA05: use assertions to detect impossible conditions)",
                "NASA05",
            )

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function(node)
        self.generic_visit(node)


def analyze(text: str) -> list[Diagnostic]:
    assert text
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return []
    visitor = NasaVisitor(text)
    visitor.visit(tree)
    return visitor.diagnostics
