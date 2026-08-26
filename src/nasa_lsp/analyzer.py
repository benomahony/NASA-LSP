from __future__ import annotations

import ast
import io
import re
import tokenize
import tomllib
from dataclasses import dataclass
from itertools import pairwise
from pathlib import Path
from typing import Final, cast, override

IGNORE_COMMENT_PATTERN: Final = r"#\s*nasa:\s*ignore\b(?:\s*\[([^\]]*)\])?"

MAX_FUNCTION_LINES: Final = 60
MIN_ASSERTS_PER_FUNCTION: Final = 2
MAX_PARENT_DEPTH: Final = 20
ISINSTANCE_ARG_COUNT: Final = 2
CONSTANT_CONSTRUCTORS: Final = frozenset({"dict", "list", "set", "tuple", "frozenset"})
TOTAL_STR_OPS: Final = frozenset({"str", "repr", "format", "ascii"})
SEVERITY_LEVELS: Final = frozenset({"error", "warning", "information"})
RULE_SEVERITY: Final[dict[str, str]] = {
    "NASA05": "error",
    "NASA05-M1": "warning",
    "NASA05-M2": "error",
    "NASA05-M3": "warning",
    "NASA05-M4": "information",
    "NASA05-M5": "information",
    "NASA05-M6": "warning",
    "NASA05-M7": "warning",
}
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


def rule_severity(code: str) -> str:
    """Return the diagnostic severity level for a rule code."""
    assert code, "Rule code must not be empty"
    level = RULE_SEVERITY.get(code, "warning")
    assert level in SEVERITY_LEVELS, "severity must be a known LSP level"
    return level


def _read_nasa_table(pyproject: Path) -> dict[str, object]:
    """Parse the [tool.nasa-lsp] table from one pyproject.toml, or return an empty dict."""
    assert pyproject.is_file(), "config path must be an existing file"
    assert pyproject.suffix == ".toml", "config file must be a .toml file"
    try:
        with pyproject.open("rb") as f:
            data = tomllib.load(f)
    except (tomllib.TOMLDecodeError, OSError):
        return {}
    if not isinstance(data.get("tool"), dict):
        return {}
    tool = cast("dict[str, object]", data["tool"])
    nasa = tool.get("nasa-lsp")
    return cast("dict[str, object]", nasa) if isinstance(nasa, dict) else {}


def _nearest_nasa_config(start_path: Path | None) -> dict[str, object]:  # nasa: ignore[NASA05]
    """Return the [tool.nasa-lsp] table from the nearest pyproject.toml, or an empty dict."""
    search_dir = Path.cwd() if start_path is None else start_path
    if start_path is not None:
        try:
            search_dir = start_path.resolve()
        except (OSError, RuntimeError):
            return {}
    if not search_dir.exists():
        return {}
    if search_dir.is_file():
        search_dir = search_dir.parent
    assert not search_dir.is_file(), "search_dir must be a directory before walking parents"

    current = search_dir
    for _ in range(MAX_PARENT_DEPTH):
        pyproject = current / "pyproject.toml"
        if pyproject.is_file() and (table := _read_nasa_table(pyproject)):
            return table
        if current.parent == current:
            break
        current = current.parent

    return {}


def load_enabled_rules(start_path: Path | None = None) -> frozenset[str]:
    """Load enabled rules from pyproject.toml, searching up from start_path."""
    config = _nearest_nasa_config(start_path)
    raw = config.get("rules")
    if isinstance(raw, list) and raw:
        rules = cast("list[str]", raw)
        assert all(isinstance(r, str) for r in rules), "NASA rule entries must be strings"
        assert all(rules), "NASA rule names must be non-empty"
        return frozenset(rules)
    return DEFAULT_ENABLED_RULES


def load_exclude_patterns(start_path: Path | None = None) -> tuple[str, ...]:
    """Load exclude glob patterns from pyproject.toml, searching up from start_path."""
    config = _nearest_nasa_config(start_path)
    raw = config.get("exclude")
    if isinstance(raw, list) and raw:
        patterns = cast("list[str]", raw)
        assert all(isinstance(p, str) for p in patterns), "exclude patterns must be strings"
        assert all(patterns), "exclude patterns must be non-empty"
        return tuple(patterns)
    return ()


class NasaVisitor(ast.NodeVisitor):
    def __init__(self, text: str, enabled_rules: frozenset[str] | None = None) -> None:
        self.text: str = text
        self.lines: list[str] = text.splitlines()
        assert len(self.lines) <= len(text) + 1, "line count cannot exceed character count plus one"
        self.diagnostics: list[Diagnostic] = []
        self.stats: list[FunctionStat] = []
        self.enabled_rules: frozenset[str] = enabled_rules if enabled_rules is not None else DEFAULT_ENABLED_RULES
        assert self.enabled_rules, "resolved rule set must not be empty"
        self.ignored: dict[int, frozenset[str] | None] = self._parse_suppressions(text)

    @staticmethod
    def _parse_suppressions(text: str) -> dict[int, frozenset[str] | None]:
        result: dict[int, frozenset[str] | None] = {}
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except (tokenize.TokenError, SyntaxError, ValueError):
            return result
        for token in tokens:
            if token.type != tokenize.COMMENT:
                continue
            match = re.search(IGNORE_COMMENT_PATTERN, token.string, re.IGNORECASE)
            if match is None:
                continue
            raw = match.group(1)
            codes = frozenset(c.strip() for c in raw.split(",") if c.strip()) if raw else None
            result[token.start[0] - 1] = codes
        assert all(line >= 0 for line in result), "suppression line indices must be non-negative"
        assert all(codes is None or codes for codes in result.values()), "specific suppressions list >= 1 code"
        return result

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
        if code not in self.enabled_rules:
            return
        if rng.start.line in self.ignored:
            suppressed = self.ignored[rng.start.line]
            if suppressed is None or code in suppressed:
                return
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

    def _restates_param_annotation(self, subject: ast.expr, type_node: ast.expr, params: dict[str, ast.expr]) -> bool:
        """Return True when isinstance(subject, type_node) merely restates subject's parameter annotation."""
        assert subject is not None, "isinstance subject must not be None"
        assert type_node is not None, "isinstance type node must not be None"
        if not (isinstance(subject, ast.Name) and subject.id in params):
            return False
        return self._annotation_matches_type(params[subject.id], type_node)

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
            if self._restates_param_annotation(subject, type_node, params):
                self._add_diag(
                    self._range_for_node(stmt),
                    (
                        f"Assertion restates parameter type '{ast.unparse(type_node)}'; "
                        "assert a domain invariant instead (NASA05-M1)"
                    ),
                    "NASA05-M1",
                )

    def _check_simple_isinstance(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
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
            if self._restates_param_annotation(subject, type_node, params):
                continue  # NASA05-M1 already reports annotation restatements
            self._add_diag(
                self._range_for_node(stmt),
                (
                    f"Assertion is a simple isinstance() type check on '{ast.unparse(subject)}'; "
                    "assert a domain invariant instead (NASA05-M6)"
                ),
                "NASA05-M6",
            )

    def _check_compound_assertion(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
        for stmt in self._iter_function_asserts(node):
            if not any(isinstance(sub, ast.BoolOp) for sub in ast.walk(stmt.test)):
                continue
            self._add_diag(
                self._range_for_node(stmt),
                "Compound assertion uses 'and'/'or'; assert one condition per statement (NASA05-M7)",
                "NASA05-M7",
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

    def _check_guaranteed_length(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
        for body in self._statement_lists(node):
            for prev, current in pairwise(body):
                if not (isinstance(current, ast.Assert) and isinstance(prev, ast.Assign) and len(prev.targets) == 1):
                    continue
                value = prev.value
                if not (isinstance(value, ast.Call) and isinstance(value.func, ast.Name) and value.func.id == "len"):
                    continue
                test = current.test
                if not (isinstance(test, ast.Compare) and len(test.ops) == 1):
                    continue
                target = ast.unparse(prev.targets[0])
                bound = test.comparators[0]
                if ast.unparse(test.left) != target or not isinstance(bound, ast.Constant):
                    continue
                non_negative = (isinstance(test.ops[0], ast.GtE) and bound.value == 0) or (
                    isinstance(test.ops[0], ast.Gt) and bound.value == -1
                )
                if non_negative:
                    message = f"Post-condition '{target}' is guaranteed by len() and can never fail (NASA05-M5)"
                    self._add_diag(self._range_for_node(current), message, "NASA05-M5")

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

        before = len(self.diagnostics)
        self._check_restated_type(node)
        self._check_simple_isinstance(node)
        self._check_compound_assertion(node)
        self._check_just_assigned(node)
        self._check_redundant_none(node)
        self._check_total_op_truthiness(node)
        self._check_guaranteed_length(node)
        flagged_lines = {d.range.start.line for d in self.diagnostics[before:] if d.code.startswith("NASA05-M")}
        meaningful_asserts = max(0, assert_count - len(flagged_lines))

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

        if meaningful_asserts < MIN_ASSERTS_PER_FUNCTION:
            self._add_diag(
                func_name_range,
                (
                    f"Function '{func_name}' has only {meaningful_asserts} assert(s) that can fail on a bug; "
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
    assert all(d.code for d in visitor.diagnostics), "every reported diagnostic must carry a rule code"
    assert all(d.code in enabled_rules for d in visitor.diagnostics), "diagnostics must stay within the enabled rules"
    return visitor.diagnostics, visitor.stats
