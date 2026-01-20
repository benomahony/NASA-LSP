"""Fuzzing tests using hypothesis for property-based testing."""
# ruff: noqa: PLR2004, ANN401
# pyright: reportAny=false, reportExplicitAny=false, reportUnknownVariableType=false, reportOperatorIssue=false

import sys
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from nasa_lsp.analyzer import analyze


# Strategy for generating valid Python identifiers
@st.composite
def python_identifiers(draw: Any) -> str:
    """Generate valid Python identifiers."""
    assert draw is not None, "Draw function must be provided"
    assert callable(draw), "Draw must be callable"

    first_char = draw(st.sampled_from("abcdefghijklmnopqrstuvwxyz_"))
    rest = draw(st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789_", max_size=20))
    return first_char + rest


# Strategy for generating simple Python code
@st.composite
def simple_python_code(draw: Any) -> str:
    """Generate simple but valid Python code."""
    assert draw is not None, "Draw function must be provided"
    assert callable(draw), "Draw must be callable"

    func_name = draw(python_identifiers())
    param_name = draw(python_identifiers())

    # Generate a simple function with assertions
    return f"""def {func_name}({param_name}):
    assert {param_name} is not None
    assert isinstance({param_name}, (int, str, list))
    return {param_name}
"""


class TestHypothesisFuzzing:
    """Hypothesis-based property testing."""

    @given(code=simple_python_code())
    @settings(max_examples=50, deadline=1000)
    def test_analyzer_never_crashes_on_valid_code(self, code: str) -> None:
        """Analyzer should never crash on syntactically valid Python code."""
        assert code is not None, "Code must not be None"
        assert isinstance(code, str), "Code must be a string"

        # The analyzer should handle any valid Python code without crashing
        try:
            result = analyze(code)
            # Result should always be a list
            assert isinstance(result, list), "analyze() must return a list"
        except SyntaxError:
            # Syntax errors are acceptable if the generated code is invalid
            pass

    @given(
        func_name=python_identifiers(),
        line_count=st.integers(min_value=1, max_value=100),
    )
    @settings(max_examples=50)
    def test_nasa04_function_length_detection(self, func_name: str, line_count: int) -> None:
        """NASA04 rule should correctly detect function length violations."""
        assert func_name is not None, "Function name must not be None"
        assert isinstance(line_count, int), "Line count must be an integer"

        # Generate a function with exactly line_count lines
        lines = [
            f"def {func_name}():",
            "    assert True",
            "    assert sys.version_info",
        ]

        # Add filler lines
        filler_count = max(0, line_count - 3)
        lines.extend([f"    x{i} = {i}" for i in range(filler_count)])

        code = "\n".join(lines)
        diagnostics = analyze(code)

        # Check if NASA04 violation is correctly reported
        nasa04_violations = [d for d in diagnostics if d.code == "NASA04"]

        if line_count > 60:
            assert len(nasa04_violations) > 0, f"Should detect NASA04 for {line_count} lines"
        else:
            assert len(nasa04_violations) == 0, f"Should not detect NASA04 for {line_count} lines"


class TestASTFuzzing:
    """AST-level fuzzing tests."""

    def test_analyzer_handles_empty_module(self) -> None:
        """Analyzer should handle empty modules."""
        empty_code = ""
        assert empty_code is not None, "Empty string must not be None"
        assert isinstance(empty_code, str), "Empty string must be a string"

        result = analyze(empty_code)
        assert isinstance(result, list), "Result must be a list"
        assert len(result) == 0, "Empty module should have no diagnostics"

    def test_analyzer_handles_only_comments(self) -> None:
        """Analyzer should handle files with only comments."""
        code = "# This is a comment\n# Another comment\n"
        assert code is not None, "Code must not be None"
        assert isinstance(code, str), "Code must be a string"

        result = analyze(code)
        assert isinstance(result, list), "Result must be a list"

    def test_analyzer_handles_nested_functions(self) -> None:
        """Analyzer should handle deeply nested functions."""
        assert sys is not None, "sys module must be available"
        assert callable(analyze), "analyze must be callable"

        code = """
def outer():
    assert True
    assert sys
    def middle():
        assert True
        assert sys
        def inner():
            assert True
            assert sys
            return 42
        return inner()
    return middle()
"""
        result = analyze(code)
        assert isinstance(result, list), "Result must be a list"

    def test_analyzer_handles_large_ast(self) -> None:
        """Analyzer should handle large AST structures."""
        num_functions = 100
        assert num_functions > 0, "Test size must be positive"
        assert isinstance(num_functions, int), "Test size must be an integer"

        # Generate a file with many small functions
        functions = [
            f"""
def func_{i}():
    assert True
    assert {i} >= 0
    return {i}
"""
            for i in range(num_functions)
        ]

        code = "\n".join(functions)
        result = analyze(code)
        assert isinstance(result, list), "Result must be a list"


class TestLSPProtocolFuzzing:
    """LSP protocol-level fuzzing tests."""

    def test_analyze_handles_invalid_unicode(self) -> None:
        """Analyzer should handle invalid unicode gracefully."""
        replacement_char = "\ufffd"
        assert replacement_char is not None, "Replacement character must not be None"
        assert isinstance(replacement_char, str), "Replacement character must be a string"

        # Unicode replacement character
        code = "def test():\n    assert True\n    assert '\ufffd' is not None\n    return '\ufffd'"
        result = analyze(code)
        assert isinstance(result, list), "Result must be a list"

    def test_analyze_handles_mixed_line_endings(self) -> None:
        """Analyzer should handle different line ending styles."""
        crlf = "\r\n"
        lf = "\n"
        assert crlf is not None, "CRLF must not be None"
        assert lf is not None, "LF must not be None"

        # Mix of CRLF and LF
        code = "def test():\r\n    assert True\n    assert sys\r\n    return 42"
        result = analyze(code)
        assert isinstance(result, list), "Result must be a list"

    def test_analyze_handles_very_long_lines(self) -> None:
        """Analyzer should handle very long lines."""
        line_length = 1000
        assert line_length > 0, "Line length must be positive"
        assert isinstance(line_length, int), "Line length must be an integer"

        long_string = "x" * line_length
        code = f"""
def test():
    assert True
    assert len("{long_string}") == {line_length}
    return "{long_string}"
"""
        result = analyze(code)
        assert isinstance(result, list), "Result must be a list"
