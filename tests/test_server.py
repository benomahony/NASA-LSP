from __future__ import annotations

from lsprotocol import types

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


def test_server_has_handlers_registered() -> None:
    from nasa_lsp.server import did_change, did_open

    assert callable(did_open)
    assert callable(did_change)
    assert did_open is not None
    assert did_change is not None


# Minimal simulation objects for testing run_checks
class SimulatedDocument:
    """Simulates a text document with just the attributes run_checks needs."""

    def __init__(self, source: str, uri: str = "file:///test.py", version: int = 1) -> None:
        self.source = source
        self.uri = uri
        self.version = version


class SimulatedLanguageServer:
    """Simulates a language server that captures diagnostic publications."""

    def __init__(self) -> None:
        self.published: list[types.PublishDiagnosticsParams] = []

    def text_document_publish_diagnostics(self, params: types.PublishDiagnosticsParams) -> None:
        self.published.append(params)


def test_run_checks_simulation_with_violations() -> None:
    """Simulation test: run_checks with code that has violations."""
    ls = SimulatedLanguageServer()
    doc = SimulatedDocument("def foo(): pass")

    run_checks(ls, doc)  # type: ignore[arg-type]

    assert len(ls.published) == 1
    assert ls.published[0].uri == "file:///test.py"
    assert ls.published[0].version == 1
    assert len(ls.published[0].diagnostics) > 0


def test_run_checks_simulation_without_violations() -> None:
    """Simulation test: run_checks with code that passes all checks."""
    ls = SimulatedLanguageServer()
    doc = SimulatedDocument(
        """
def foo():
    assert True
    assert False
"""
    )

    run_checks(ls, doc)  # type: ignore[arg-type]

    assert len(ls.published) == 1
    assert ls.published[0].uri == "file:///test.py"
    assert len(ls.published[0].diagnostics) == 0


class SimulatedWorkspace:
    """Simulates a workspace that returns documents by URI."""

    def __init__(self, doc: SimulatedDocument) -> None:
        self.doc = doc

    def get_text_document(self, uri: str) -> SimulatedDocument:
        assert uri == self.doc.uri
        return self.doc


def test_did_open_simulation() -> None:
    """Simulation test: did_open handler calls run_checks."""
    from nasa_lsp.server import did_open

    doc = SimulatedDocument("def foo(): pass")
    ls = SimulatedLanguageServer()
    ls.workspace = SimulatedWorkspace(doc)  # type: ignore[attr-defined]

    params = types.DidOpenTextDocumentParams(
        text_document=types.TextDocumentItem(
            uri="file:///test.py", language_id="python", version=1, text="def foo(): pass"
        )
    )

    did_open(ls, params)  # type: ignore[arg-type]

    assert len(ls.published) == 1


def test_did_change_simulation() -> None:
    """Simulation test: did_change handler calls run_checks."""
    from nasa_lsp.server import did_change

    doc = SimulatedDocument("def bar(): pass")
    ls = SimulatedLanguageServer()
    ls.workspace = SimulatedWorkspace(doc)  # type: ignore[attr-defined]

    params = types.DidChangeTextDocumentParams(
        text_document=types.VersionedTextDocumentIdentifier(uri="file:///test.py", version=2),
        content_changes=[],
    )

    did_change(ls, params)  # type: ignore[arg-type]

    assert len(ls.published) == 1


def test_serve_integration() -> None:
    """Integration test: serve() actually starts the server process."""
    import subprocess
    import sys
    import time

    proc = subprocess.Popen(
        [sys.executable, "-c", "from nasa_lsp.server import serve; serve()"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    time.sleep(0.1)

    proc.terminate()
    proc.wait(timeout=2)

    assert proc.returncode in (0, -15)
