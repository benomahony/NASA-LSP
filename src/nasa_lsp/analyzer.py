from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Final, override

MAX_FUNCTION_LINES: Final = 60
MIN_ASSERTS_PER_FUNCTION: Final = 2


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


@dataclass
class FunctionStat:
    name: str
    line_start: int
    line_count: int
    assert_count: int


class NasaVisitor(ast.NodeVisitor):
    def __init__(self, text: str) -> None:
        assert text
        assert isinstance(text, str)
        self.text: str = text
        self.lines: list[str] = text.splitlines()
        self.diagnostics: list[Diagnostic] = []
        self.stats: list[FunctionStat] = []

    @staticmethod
    def _pos(lineno: int, col: int) -> Position:
        assert lineno
        assert col >= 0
        return Position(line=lineno - 1, character=col)

    def _range_for_node(self, node: ast.expr | ast.stmt) -> Range:
        assert node
        assert node.end_lineno is not None
        assert node.end_col_offset is not None
        return Range(
            start=self._pos(node.lineno, node.col_offset),
            end=self._pos(node.end_lineno, node.end_col_offset),
        )

    def _range_for_func_name(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Range:
        assert node
        assert node.end_lineno is not None
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

    def _add_diag(self, rng: Range, message: str, code: str) -> None:
        assert rng
        assert message
        assert code
        self.diagnostics.append(Diagnostic(range=rng, message=message, code=code))

    @override
    def visit_Call(self, node: ast.Call) -> None:
        assert node
        assert hasattr(node, "func")
        name: str | None = None
        target_node: ast.expr | None = None

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

    @override
    def visit_While(self, node: ast.While) -> None:
        assert node
        assert hasattr(node, "test")
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            self._add_diag(
                self._range_for_node(node),
                "Unbounded loop 'while True' (NASA02: loops must be bounded)",
                "NASA02",
            )
        self.generic_visit(node)

    def _check_recursion(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        func_name = node.name
        assert func_name
        assert node.body
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for sub_node in ast.walk(stmt):
                if (
                    isinstance(sub_node, ast.Call)
                    and isinstance(sub_node.func, ast.Name)
                    and sub_node.func.id == func_name
                ):
                    return True
        return False

    def _count_asserts(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> int:
        assert node
        assert node.body is not None
        assert_count = 0
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            for sub_node in ast.walk(stmt):
                if isinstance(sub_node, ast.Assert):
                    assert_count += 1
        return assert_count

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        func_name = node.name
        assert func_name
        assert node.end_lineno is not None
        func_name_range = self._range_for_func_name(node)

        # Statistics
        line_count = node.end_lineno - node.lineno + 1
        assert_count = self._count_asserts(node)
        self.stats.append(FunctionStat(func_name, node.lineno, line_count, assert_count))

        if self._check_recursion(node):
            self._add_diag(
                func_name_range,
                f"Recursive call to '{func_name}' (NASA01: no recursion)",
                "NASA01-B",
            )

        if line_count >= MAX_FUNCTION_LINES:
            self._add_diag(
                func_name_range,
                f"Function '{func_name}' longer than {MAX_FUNCTION_LINES} lines (NASA04)",
                "NASA04",
            )

        if assert_count < MIN_ASSERTS_PER_FUNCTION:
            self._add_diag(
                func_name_range,
                (
                    f"Function '{func_name}' has only {assert_count} assert(s); "
                    f"expected at least {MIN_ASSERTS_PER_FUNCTION} (NASA05)"
                ),
                "NASA05",
            )

    @override
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        assert node
        assert hasattr(node, "name")
        self._check_function(node)
        self.generic_visit(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        assert node
        assert hasattr(node, "name")
        self._check_function(node)
        self.generic_visit(node)


def analyze(text: str) -> tuple[list[Diagnostic], list[FunctionStat]]:
    assert isinstance(text, str)
    assert text is not None
    if not text.strip():
        return [], []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], []
    visitor = NasaVisitor(text)
    visitor.visit(tree)
    return visitor.diagnostics, visitor.stats
