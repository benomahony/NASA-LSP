from __future__ import annotations

import ast
import tomllib
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Final, cast, override

MAX_FUNCTION_LINES: Final = 60
MIN_ASSERTS_PER_FUNCTION: Final = 2
ISINSTANCE_ARG_COUNT: Final = 2
CONSTANT_CONSTRUCTORS: Final = frozenset({"dict", "list", "set", "tuple", "frozenset"})
TOTAL_STR_OPS: Final = frozenset({"str", "repr", "format", "ascii"})
DEFAULT_ENABLED_RULES: Final = frozenset(
    {
        "NASA01-A",
        "NASA01-B",
        "NASA02",
        "NASA04",
        "NASA05",
        "NASA05-A",
    }
)


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


def _extract_rules_from_toml(data: dict[str, object]) -> frozenset[str] | None:
    """Extract NASA rules list from parsed TOML data."""
    if "tool" in data and isinstance(data["tool"], dict):
        tool = cast("dict[str, object]", data["tool"])
        if "nasa-lsp" in tool and isinstance(tool["nasa-lsp"], dict):
            nasa = cast("dict[str, object]", tool["nasa-lsp"])
            if "rules" in nasa and isinstance(nasa["rules"], list):
                rules = cast("list[str]", nasa["rules"])
                assert all(isinstance(r, str) for r in rules), "NASA rule entries must be strings"
                assert all(rules), "NASA rule names must be non-empty"
                return frozenset(rules)
    return None


def load_enabled_rules(start_path: Path | None = None) -> frozenset[str]:
    """Load enabled rules from pyproject.toml, searching up from start_path."""

    search_dir = Path.cwd() if start_path is None else start_path
    if start_path is not None:
        try:
            search_dir = start_path.resolve()
        except (OSError, RuntimeError):
            return DEFAULT_ENABLED_RULES

    if not search_dir.exists():
        return DEFAULT_ENABLED_RULES
    if search_dir.is_file():
        search_dir = search_dir.parent
    assert not search_dir.is_file(), "search_dir must be a directory before walking parents"

    current = search_dir
    for _ in range(20):
        pyproject = current / "pyproject.toml"
        if pyproject.is_file():
            try:
                with pyproject.open("rb") as f:
                    data = tomllib.load(f)
                rules = _extract_rules_from_toml(data)
                if rules is not None:
                    assert rules, "empty rules list would silently disable every NASA check"
                    return rules
            except (tomllib.TOMLDecodeError, OSError):
                pass
        if current.parent == current:
            break
        current = current.parent

    return DEFAULT_ENABLED_RULES


class NasaVisitor(ast.NodeVisitor):
    def __init__(self, text: str, enabled_rules: frozenset[str] | None = None) -> None:
        assert enabled_rules is None or enabled_rules, "enabled_rules, if provided, must be non-empty"
        self.text: str = text
        self.lines: list[str] = text.splitlines()
        assert len(self.lines) <= len(text) + 1, "line count cannot exceed character count plus one"
        self.diagnostics: list[Diagnostic] = []
        self.stats: list[FunctionStat] = []
        self.enabled_rules: frozenset[str] = enabled_rules if enabled_rules is not None else DEFAULT_ENABLED_RULES

    @staticmethod
    def _pos(lineno: int, col: int) -> Position:
        assert lineno, "Line number must not be empty"
        assert col >= 0, "Column offset must be non-negative"
        return Position(line=lineno - 1, character=col)

    def _range_for_node(self, node: ast.expr | ast.stmt) -> Range:
        assert node is not None, "AST node must not be None"
        assert node.end_lineno is not None, "Node must have end line number"
        assert node.end_col_offset is not None, "Node must have end column offset"
        return Range(
            start=self._pos(node.lineno, node.col_offset),
            end=self._pos(node.end_lineno, node.end_col_offset),
        )

    def _range_for_func_name(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Range:
        assert node is not None, "Function node must not be None"
        assert node.end_lineno is not None, "Function node must have end line number"
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
        assert rng is not None, "Range must not be None"
        assert message, "Message must not be empty"
        assert code, "Code must not be empty"
        if code in self.enabled_rules:
            self.diagnostics.append(Diagnostic(range=rng, message=message, code=code))

    @override
    def visit_Call(self, node: ast.Call) -> None:
        assert node is not None, "Call node must not be None"
        assert hasattr(node, "func"), "Call node must have func attribute"
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
        assert node is not None, "While node must not be None"
        assert hasattr(node, "test"), "While node must have test attribute"
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            self._add_diag(
                self._range_for_node(node),
                "Unbounded loop 'while True' (NASA02: loops must be bounded)",
                "NASA02",
            )
        self.generic_visit(node)

    @override
    def visit_Assert(self, node: ast.Assert) -> None:
        assert node is not None, "Assert node must not be None"
        assert hasattr(node, "test"), "Assert node must have test attribute"
        if node.msg is None:
            self._add_diag(
                self._range_for_node(node),
                "Assert statement missing descriptive error message (NASA05: assertions must explain invariant)",
                "NASA05-A",
            )
        self.generic_visit(node)

    @staticmethod
    def _param_annotations(node: ast.FunctionDef | ast.AsyncFunctionDef) -> dict[str, ast.expr]:
        assert node is not None, "Function node must not be None"
        assert node.args is not None, "Function node must have arguments"
        args = node.args
        return {a.arg: a.annotation for a in (*args.posonlyargs, *args.args, *args.kwonlyargs) if a.annotation}

    def _iter_function_asserts(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Assert]:
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
        found: list[ast.Assert] = []
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            found.extend(sub for sub in ast.walk(stmt) if isinstance(sub, ast.Assert))
        return found

    @staticmethod
    def _annotation_matches_type(annotation: ast.expr, type_node: ast.expr) -> bool:
        assert annotation is not None, "Annotation node must not be None"
        assert type_node is not None, "Type node must not be None"
        target = ast.unparse(type_node)
        parts: list[ast.expr] = []
        stack = [annotation]
        while stack:
            current = stack.pop()
            if isinstance(current, ast.BinOp) and isinstance(current.op, ast.BitOr):
                stack.extend((current.left, current.right))
            else:
                parts.append(current)
        non_none = [ast.unparse(p) for p in parts if ast.unparse(p) != "None"]
        return non_none == [target]

    def _check_restated_type(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
        params = self._param_annotations(node)
        for stmt in self._iter_function_asserts(node):
            test = stmt.test
            if not (isinstance(test, ast.Call) and isinstance(test.func, ast.Name) and test.func.id == "isinstance"):
                continue
            if len(test.args) != ISINSTANCE_ARG_COUNT:
                continue
            subject, type_node = test.args
            if not (isinstance(subject, ast.Name) and subject.id in params):
                continue
            if self._annotation_matches_type(params[subject.id], type_node):
                self._add_diag(
                    self._range_for_node(stmt),
                    (
                        f"Assertion restates parameter type '{ast.unparse(type_node)}'; "
                        "assert a domain invariant instead (NASA05-M1)"
                    ),
                    "NASA05-M1",
                )

    @staticmethod
    def _statement_lists(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[list[ast.stmt]]:
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
        lists: list[list[ast.stmt]] = []
        stack: list[list[ast.stmt]] = [node.body]
        while stack:
            body = stack.pop()
            lists.append(body)
            for stmt in body:
                match stmt:
                    case ast.FunctionDef() | ast.AsyncFunctionDef() | ast.ClassDef():
                        pass
                    case ast.If() | ast.For() | ast.AsyncFor() | ast.While():
                        stack.extend([stmt.body, stmt.orelse])
                    case ast.With() | ast.AsyncWith():
                        stack.append(stmt.body)
                    case ast.Try() | ast.TryStar():
                        stack.extend([stmt.body, stmt.orelse, stmt.finalbody])
                        stack.extend([handler.body for handler in stmt.handlers])
                    case ast.Match():
                        stack.extend([branch.body for branch in stmt.cases])
                    case _:
                        pass
        return lists

    def _assert_always_holds(self, test: ast.expr, target: str, value: ast.expr) -> bool:
        assert test is not None, "Assert test node must not be None"
        assert target, "Assignment target text must not be empty"
        if isinstance(test, (ast.Name, ast.Attribute)) and ast.unparse(test) == target:
            return isinstance(value, ast.Constant) and bool(value.value)
        if not (isinstance(test, ast.Compare) and len(test.ops) == 1 and ast.unparse(test.left) == target):
            return False
        op, comparator = test.ops[0], test.comparators[0]
        if isinstance(op, ast.IsNot) and isinstance(comparator, ast.Constant) and comparator.value is None:
            return not (isinstance(value, ast.Constant) and value.value is None)
        return isinstance(op, ast.Eq) and ast.unparse(comparator) == ast.unparse(value)

    def _check_just_assigned(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
        for body in self._statement_lists(node):
            for prev, current in pairwise(body):
                if not (isinstance(current, ast.Assert) and isinstance(prev, ast.Assign) and len(prev.targets) == 1):
                    continue
                value = prev.value
                is_literal = isinstance(value, (ast.Constant, ast.Dict, ast.List, ast.Set, ast.Tuple)) or (
                    isinstance(value, ast.Call)
                    and isinstance(value.func, ast.Name)
                    and value.func.id in CONSTANT_CONSTRUCTORS
                )
                if not is_literal:
                    continue
                target = ast.unparse(prev.targets[0])
                if self._assert_always_holds(current.test, target, prev.value):
                    message = f"Assertion always holds: '{target}' was just assigned a constant literal (NASA05-M2)"
                    self._add_diag(self._range_for_node(current), message, "NASA05-M2")

    def _check_redundant_none(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
        for body in self._statement_lists(node):
            for prev, current in pairwise(body):
                if not (isinstance(prev, ast.Assert) and isinstance(current, ast.Assert)):
                    continue
                check, nxt = prev.test, current.test
                if not (isinstance(check, ast.Compare) and len(check.ops) == 1 and isinstance(check.ops[0], ast.IsNot)):
                    continue
                end = check.comparators[0]
                if not (isinstance(end, ast.Constant) and end.value is None):
                    continue
                if not (isinstance(nxt, ast.Call) and isinstance(nxt.func, ast.Name) and nxt.func.id == "isinstance"):
                    continue
                subject = ast.unparse(check.left)
                if len(nxt.args) != ISINSTANCE_ARG_COUNT or subject != ast.unparse(nxt.args[0]):
                    continue
                message = f"Redundant None check on '{subject}'; the isinstance below already excludes None (NASA05-M3)"
                self._add_diag(self._range_for_node(prev), message, "NASA05-M3")

    def _check_total_op_truthiness(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
        for body in self._statement_lists(node):
            for prev, current in pairwise(body):
                if not (isinstance(current, ast.Assert) and isinstance(prev, ast.Assign) and len(prev.targets) == 1):
                    continue
                value = prev.value
                is_str_call = (
                    isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id in TOTAL_STR_OPS
                )
                if not (isinstance(value, ast.JoinedStr) or is_str_call):
                    continue
                test = current.test
                target = ast.unparse(prev.targets[0])
                if isinstance(test, (ast.Name, ast.Attribute)) and ast.unparse(test) == target:
                    message = f"Assertion on total-op result '{target}' rarely fails; confirm the invariant (NASA05-M4)"
                    self._add_diag(self._range_for_node(current), message, "NASA05-M4")

    def _check_recursion(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
        func_name = node.name
        assert func_name, "Function must have a name"
        assert node.body, "Function must have a body"
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
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
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
        assert func_name, "Function must have a name"
        assert node.end_lineno is not None, "Function node must have end line number"
        func_name_range = self._range_for_func_name(node)

        # Statistics
        line_count = node.end_lineno - node.lineno + 1
        assert_count = self._count_asserts(node)
        self.stats.append(FunctionStat(func_name, node.lineno, line_count, assert_count))

        self._check_restated_type(node)
        self._check_just_assigned(node)
        self._check_redundant_none(node)
        self._check_total_op_truthiness(node)

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
        assert node is not None, "FunctionDef node must not be None"
        assert hasattr(node, "name"), "FunctionDef node must have name attribute"
        self._check_function(node)
        self.generic_visit(node)

    @override
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        assert node is not None, "AsyncFunctionDef node must not be None"
        assert hasattr(node, "name"), "AsyncFunctionDef node must have name attribute"
        self._check_function(node)
        self.generic_visit(node)


def analyze(
    text: str,
    file_path: Path | None = None,
    enabled_rules: frozenset[str] | None = None,
) -> tuple[list[Diagnostic], list[FunctionStat]]:
    assert isinstance(text, str), "Text must be a string"
    assert text is not None, "Text must not be None"
    if not text.strip():
        return [], []
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], []
    if enabled_rules is None:
        enabled_rules = load_enabled_rules(file_path)
    visitor = NasaVisitor(text, enabled_rules)
    visitor.visit(tree)
    return visitor.diagnostics, visitor.stats
