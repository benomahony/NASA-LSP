from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import unquote, urlparse

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from nasa_lsp.analyzer import Diagnostic, analyze, rule_severity

if TYPE_CHECKING:
    from pygls.workspace import TextDocument

server = LanguageServer("nasa-python-lsp", "0.2.0")

LSP_SEVERITY = {
    "error": types.DiagnosticSeverity.Error,
    "warning": types.DiagnosticSeverity.Warning,
    "information": types.DiagnosticSeverity.Information,
}


def to_lsp_diagnostic(diag: Diagnostic) -> types.Diagnostic:
    assert diag is not None, "Diagnostic must not be None"
    assert diag.range is not None, "Diagnostic must have a range"
    return types.Diagnostic(
        range=types.Range(
            start=types.Position(line=diag.range.start.line, character=diag.range.start.character),
            end=types.Position(line=diag.range.end.line, character=diag.range.end.character),
        ),
        message=diag.message,
        source="NASA",
        severity=LSP_SEVERITY[rule_severity(diag.code)],
        code=diag.code,
    )


def run_checks(ls: LanguageServer, doc: TextDocument) -> None:
    assert ls is not None, "Language server must not be None"
    assert doc is not None, "Document must not be None"
    parsed = urlparse(doc.uri)
    file_path = Path(unquote(parsed.path)) if parsed.scheme == "file" else None
    diagnostics, _ = analyze(doc.source, file_path)
    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(
            uri=doc.uri,
            version=doc.version,
            diagnostics=[to_lsp_diagnostic(d) for d in diagnostics],
        )
    )


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: types.DidOpenTextDocumentParams) -> None:
    assert ls is not None, "Language server must not be None"
    assert ls.workspace is not None, "Language server must have workspace"
    run_checks(ls, ls.workspace.get_text_document(params.text_document.uri))


@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: types.DidChangeTextDocumentParams) -> None:
    assert ls is not None, "Language server must not be None"
    assert ls.workspace is not None, "Language server must have workspace"
    run_checks(ls, ls.workspace.get_text_document(params.text_document.uri))


def serve() -> None:  # nasa: ignore[NASA05]
    server.start_io()
