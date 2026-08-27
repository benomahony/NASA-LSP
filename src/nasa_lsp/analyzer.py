from __future__ import annotations

import ast
import io
import re
import tokenize
import tomllib
from itertools import pairwise
from pathlib import Path
from typing import Final, cast, override

from nasa_lsp._languages import DEFAULT_LANGUAGE, language_for_path
from nasa_lsp._types import (
    MAX_FUNCTION_LINES,
    MIN_ASSERTS_PER_FUNCTION,
    Diagnostic,
    FunctionStat,
    Position,
    Range,
)

__all__ = [
    "ALL_RULES",
    "MAX_FUNCTION_LINES",
    "MIN_ASSERTS_PER_FUNCTION",
    "RULE_SEVERITY",
    "Diagnostic",
    "FunctionStat",
    "Position",
    "Range",
    "analyze",
    "load_enabled_rules",
    "load_exclude_patterns",
    "rule_severity",
]

IGNORE_COMMENT_PATTERN: Final = r"#\s*nasa:\s*ignore\b(?:\s*\[([^\]]*)\])?"

MAX_PARENT_DEPTH: Final = 20
ISINSTANCE_ARG_COUNT: Final = 2
CONSTANT_CONSTRUCTORS: Final = frozenset({"dict", "list", "set", "tuple", "frozenset"})
TOTAL_STR_OPS: Final = frozenset({"str", "repr", "format", "ascii"})
SEVERITY_LEVELS: Final = frozenset({"error", "warning", "information"})
# The one registry of every rule the linter can emit, with its severity. Adding a
# rule means adding it here; it is then known, severity-mapped, and on by default.
RULE_SEVERITY: Final[dict[str, str]] = {
    "NASA01-forbidden-api": "error",
    "NASA01-recursion": "error",
    "NASA02": "error",
    "NASA03": "error",
    "NASA04": "warning",
    "NASA05": "error",
    "NASA05-message": "warning",
    "NASA05-single-condition": "warning",
    "NASA05-constant-assert": "error",
    "NASA05-redundant-none": "warning",
    "NASA05-total-op": "information",
    "NASA05-guaranteed-len": "information",
    "NASA05-isinstance": "warning",
}

# Every rule is enabled; a project disables individual rules via config, never enables.
ALL_RULES: Final = frozenset(RULE_SEVERITY)

# Rules that flag an assertion as too weak to count toward NASA05.
WEAK_ASSERT_RULES: Final = frozenset(
    {
        "NASA05-single-condition",
        "NASA05-constant-assert",
        "NASA05-redundant-none",
        "NASA05-total-op",
        "NASA05-guaranteed-len",
        "NASA05-isinstance",
    }
)


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


def load_enabled_rules(start_path: Path | None = None) -> frozenset[str]:  # nasa: ignore[NASA05]
    """Return every rule except those disabled via [tool.nasa-lsp].disable in pyproject.toml."""
    raw = _nearest_nasa_config(start_path).get("disable")
    disabled = frozenset(cast("list[str]", raw)) if isinstance(raw, list) else frozenset[str]()
    return ALL_RULES - disabled


def load_exclude_patterns(start_path: Path | None = None) -> tuple[str, ...]:  # nasa: ignore[NASA05]
    """Return exclude glob patterns from [tool.nasa-lsp].exclude, or an empty tuple."""
    raw = _nearest_nasa_config(start_path).get("exclude")
    return tuple(cast("list[str]", raw)) if isinstance(raw, list) else ()


class NasaVisitor(ast.NodeVisitor):
    def __init__(self, text: str, enabled_rules: frozenset[str] | None = None) -> None:
        self.text: str = text
        self.lines: list[str] = text.splitlines()
        assert len(self.lines) <= len(text) + 1, "line count cannot exceed character count plus one"
        self.diagnostics: list[Diagnostic] = []
        self.stats: list[FunctionStat] = []
        self.enabled_rules: frozenset[str] = enabled_rules if enabled_rules is not None else ALL_RULES
        assert self.enabled_rules <= ALL_RULES, "enabled rules must be known rules"
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
        self.diagnostics.append(Diagnostic(range=rng, message=f"{message} ({code})", code=code))

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
                    f"Call to forbidden API '{name}'",
                    "NASA01-forbidden-api",
                )

        self.generic_visit(node)

    @override
    def visit_While(self, node: ast.While) -> None:
        assert node is not None, "While node must not be None"
        assert hasattr(node, "test"), "While node must have test attribute"
        if isinstance(node.test, ast.Constant) and node.test.value is True:
            self._add_diag(
                self._range_for_node(node),
                "Unbounded loop 'while True'",
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
                "Assert has no message; describe the invariant it checks",
                "NASA05-message",
            )
        self.generic_visit(node)

    def _iter_function_asserts(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Assert]:
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
        found: list[ast.Assert] = []
        for stmt in node.body:
            if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                continue
            found.extend(sub for sub in ast.walk(stmt) if isinstance(sub, ast.Assert))
        return found

    def _check_isinstance_assertion(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
        for stmt in self._iter_function_asserts(node):
            has_isinstance = any(
                isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "isinstance"
                for n in ast.walk(stmt.test)
            )
            if not has_isinstance:
                continue
            self._add_diag(
                self._range_for_node(stmt),
                "Assertion checks a type with isinstance(); assert a domain invariant instead",
                "NASA05-isinstance",
            )

    def _check_compound_assertion(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        assert node is not None, "Function node must not be None"
        assert node.body is not None, "Function must have a body"
        for stmt in self._iter_function_asserts(node):
            if not isinstance(stmt.test, ast.BoolOp):
                continue
            self._add_diag(
                self._range_for_node(stmt),
                "Compound assertion uses 'and'/'or'; assert one condition per statement",
                "NASA05-single-condition",
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
                    message = f"Assertion always holds: '{target}' was just assigned a literal; assert a runtime value"
                    self._add_diag(self._range_for_node(current), message, "NASA05-constant-assert")

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
                message = f"Redundant None check on '{subject}'; the isinstance below excludes None"
                self._add_diag(self._range_for_node(prev), message, "NASA05-redundant-none")

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
                    message = f"Assertion on total-op result '{target}' rarely fails; confirm the invariant"
                    self._add_diag(self._range_for_node(current), message, "NASA05-total-op")

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
                    message = f"Post-condition '{target}' is guaranteed by len() and cannot fail; assert a real bound"
                    self._add_diag(self._range_for_node(current), message, "NASA05-guaranteed-len")

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
        self._check_isinstance_assertion(node)
        self._check_compound_assertion(node)
        self._check_just_assigned(node)
        self._check_redundant_none(node)
        self._check_total_op_truthiness(node)
        self._check_guaranteed_length(node)
        flagged_lines = {d.range.start.line for d in self.diagnostics[before:] if d.code in WEAK_ASSERT_RULES}
        meaningful_asserts = max(0, assert_count - len(flagged_lines))

        if self._check_recursion(node):
            self._add_diag(
                func_name_range,
                f"Recursive call to '{func_name}'",
                "NASA01-recursion",
            )

        if line_count >= MAX_FUNCTION_LINES:
            self._add_diag(
                func_name_range,
                f"Function '{func_name}' longer than {MAX_FUNCTION_LINES} lines",
                "NASA04",
            )

        if meaningful_asserts < MIN_ASSERTS_PER_FUNCTION:
            self._add_diag(
                func_name_range,
                (
                    f"Function '{func_name}' has only {meaningful_asserts} assert(s) that can fail on a bug; "
                    f"expected at least {MIN_ASSERTS_PER_FUNCTION}"
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
    if enabled_rules is None:
        enabled_rules = load_enabled_rules(file_path)
    language = language_for_path(file_path)
    if language != DEFAULT_LANGUAGE:
        from nasa_lsp.generic import analyze_generic  # noqa: PLC0415

        return analyze_generic(text, language, enabled_rules)
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [], []
    visitor = NasaVisitor(text, enabled_rules)
    visitor.visit(tree)
    assert all(d.code for d in visitor.diagnostics), "every reported diagnostic must carry a rule code"
    assert all(d.code in enabled_rules for d in visitor.diagnostics), "diagnostics must stay within the enabled rules"
    return visitor.diagnostics, visitor.stats
