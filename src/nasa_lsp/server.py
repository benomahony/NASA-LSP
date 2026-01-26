from __future__ import annotations

from typing import TYPE_CHECKING

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from nasa_lsp.analyzer import Diagnostic, analyze

if TYPE_CHECKING:
    from pygls.workspace import TextDocument

server = LanguageServer("nasa-python-lsp", "0.2.0")


def to_lsp_diagnostic(diag: Diagnostic) -> types.Diagnostic:
    assert diag
    assert diag.range
    return types.Diagnostic(
        range=types.Range(
            start=types.Position(line=diag.range.start.line, character=diag.range.start.character),
            end=types.Position(line=diag.range.end.line, character=diag.range.end.character),
        ),
        message=diag.message,
        source="NASA",
        severity=types.DiagnosticSeverity.Warning,
        code=diag.code,
    )


def run_checks(ls: LanguageServer, doc: TextDocument) -> None:
    assert ls
    assert doc
    diagnostics, _ = analyze(doc.source)
    ls.text_document_publish_diagnostics(
        types.PublishDiagnosticsParams(
            uri=doc.uri,
            version=doc.version,
            diagnostics=[to_lsp_diagnostic(d) for d in diagnostics],
        )
    )


@server.feature(types.TEXT_DOCUMENT_DID_OPEN)
def did_open(ls: LanguageServer, params: types.DidOpenTextDocumentParams) -> None:
    assert ls
    assert ls.workspace
    run_checks(ls, ls.workspace.get_text_document(params.text_document.uri))


@server.feature(types.TEXT_DOCUMENT_DID_CHANGE)
def did_change(ls: LanguageServer, params: types.DidChangeTextDocumentParams) -> None:
    assert ls
    assert ls.workspace
    run_checks(ls, ls.workspace.get_text_document(params.text_document.uri))


def serve() -> None:
    assert server
    assert isinstance(server, LanguageServer)
    server.start_io()
