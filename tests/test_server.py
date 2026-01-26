from __future__ import annotations

from lsprotocol import types
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument

from nasa_lsp.analyzer import Diagnostic, Position, Range
from nasa_lsp.server import run_checks, server, to_lsp_diagnostic

CLEAN_CODE_VERSION = 2


def test_to_lsp_diagnostic_basic() -> None:
    diag = Diagnostic(
        range=Range(start=Position(line=5, character=10), end=Position(line=5, character=20)),
        message="Test error",
        code="TEST01",
    )
    result = to_lsp_diagnostic(diag)
    assert isinstance(result, types.Diagnostic)
    assert result.message == "Test error"
    assert result.code == "TEST01"
    assert result.source == "NASA"
    assert result.severity == types.DiagnosticSeverity.Warning


def test_to_lsp_diagnostic_range_conversion() -> None:
    end_line = 10
    end_character = 5
    diag = Diagnostic(
        range=Range(start=Position(line=0, character=0), end=Position(line=end_line, character=end_character)),
        message="Multi-line",
        code="MULTI",
    )
    result = to_lsp_diagnostic(diag)
    assert result.range.start.line == 0
    assert result.range.start.character == 0
    assert result.range.end.line == end_line
    assert result.range.end.character == end_character


def test_to_lsp_diagnostic_preserves_all_fields() -> None:
    diag = Diagnostic(
        range=Range(start=Position(line=99, character=50), end=Position(line=100, character=0)),
        message="Long message with special chars: <>&\"'",
        code="NASA01-A",
    )
    result = to_lsp_diagnostic(diag)
    assert result.message == "Long message with special chars: <>&\"'"
    assert result.code == "NASA01-A"
    assert isinstance(result.range, types.Range)
    assert isinstance(result.range.start, types.Position)
    assert isinstance(result.range.end, types.Position)


def test_server_is_language_server() -> None:
    assert server is not None
    assert server.name == "nasa-python-lsp"


def test_server_version() -> None:
    assert server.version == "0.2.0"
    assert isinstance(server.version, str)


def test_run_checks_with_violations() -> None:
    ls = LanguageServer("test", "0.1")
    doc = TextDocument(uri="file:///test.py", source="def foo(): pass", version=1)

    published_diagnostics = None

    def capture_diagnostics(params: types.PublishDiagnosticsParams) -> None:
        assert params is not None
        assert isinstance(params, types.PublishDiagnosticsParams)
        nonlocal published_diagnostics
        published_diagnostics = params

    ls.text_document_publish_diagnostics = capture_diagnostics

    run_checks(ls, doc)

    assert published_diagnostics is not None
    assert isinstance(published_diagnostics, types.PublishDiagnosticsParams)
    assert published_diagnostics.uri == "file:///test.py"
    assert published_diagnostics.version == 1
    assert len(published_diagnostics.diagnostics) > 0


def test_run_checks_with_clean_code() -> None:
    ls = LanguageServer("test", "0.1")
    clean_source = """
def foo():
    assert True
    assert False
    return 1
"""
    doc = TextDocument(uri="file:///clean.py", source=clean_source, version=CLEAN_CODE_VERSION)

    published_diagnostics = None

    def capture_diagnostics(params: types.PublishDiagnosticsParams) -> None:
        assert params is not None
        assert isinstance(params, types.PublishDiagnosticsParams)
        nonlocal published_diagnostics
        published_diagnostics = params

    ls.text_document_publish_diagnostics = capture_diagnostics

    run_checks(ls, doc)

    assert published_diagnostics is not None
    assert published_diagnostics.uri == "file:///clean.py"
    assert published_diagnostics.version == CLEAN_CODE_VERSION
    assert len(published_diagnostics.diagnostics) == 0


def test_run_checks_with_syntax_error() -> None:
    ls = LanguageServer("test", "0.1")
    doc = TextDocument(uri="file:///broken.py", source="def broken(", version=1)

    published_diagnostics = None

    def capture_diagnostics(params: types.PublishDiagnosticsParams) -> None:
        assert params is not None
        assert isinstance(params, types.PublishDiagnosticsParams)
        nonlocal published_diagnostics
        published_diagnostics = params

    ls.text_document_publish_diagnostics = capture_diagnostics

    run_checks(ls, doc)

    assert published_diagnostics is not None
    assert len(published_diagnostics.diagnostics) == 0
