from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

from lsprotocol import types
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument

from nasa_lsp.analyzer import Diagnostic, Position, Range
from nasa_lsp.server import run_checks, server, to_lsp_diagnostic


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
    ls = Mock(spec=LanguageServer)
    doc = Mock(spec=TextDocument)
    doc.source = "def foo(): pass"
    doc.uri = "file:///test.py"
    doc.version = 1

    run_checks(ls, doc)

    assert ls.text_document_publish_diagnostics.called
    args = ls.text_document_publish_diagnostics.call_args
    assert args is not None
    params = args[0][0]
    assert params.uri == "file:///test.py"
    assert params.version == 1
    assert len(params.diagnostics) > 0


def test_run_checks_without_violations() -> None:
    ls = Mock(spec=LanguageServer)
    doc = Mock(spec=TextDocument)
    doc.source = """
def foo():
    assert True
    assert False
"""
    doc.uri = "file:///test.py"
    doc.version = 1

    run_checks(ls, doc)

    assert ls.text_document_publish_diagnostics.called
    args = ls.text_document_publish_diagnostics.call_args
    assert args is not None
    params = args[0][0]
    assert params.uri == "file:///test.py"
    assert len(params.diagnostics) == 0


def test_did_open_handler() -> None:
    from nasa_lsp.server import did_open

    ls = Mock(spec=LanguageServer)
    workspace = Mock()
    ls.workspace = workspace
    doc = Mock(spec=TextDocument)
    doc.source = "def foo(): pass"
    doc.uri = "file:///test.py"
    doc.version = 1
    workspace.get_text_document.return_value = doc

    params = types.DidOpenTextDocumentParams(
        text_document=types.TextDocumentItem(
            uri="file:///test.py", language_id="python", version=1, text="def foo(): pass"
        )
    )

    did_open(ls, params)

    assert workspace.get_text_document.called
    assert ls.text_document_publish_diagnostics.called


def test_did_change_handler() -> None:
    from nasa_lsp.server import did_change

    ls = Mock(spec=LanguageServer)
    workspace = Mock()
    ls.workspace = workspace
    doc = Mock(spec=TextDocument)
    doc.source = "def bar(): pass"
    doc.uri = "file:///test.py"
    doc.version = 2
    workspace.get_text_document.return_value = doc

    params = types.DidChangeTextDocumentParams(
        text_document=types.VersionedTextDocumentIdentifier(uri="file:///test.py", version=2),
        content_changes=[],
    )

    did_change(ls, params)

    assert workspace.get_text_document.called
    assert ls.text_document_publish_diagnostics.called


def test_serve_function() -> None:
    from nasa_lsp.server import serve

    with patch.object(server, "start_io") as mock_start_io:
        serve()
        assert mock_start_io.called
