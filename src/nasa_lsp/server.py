from __future__ import annotations

from pathlib import PurePosixPath
from typing import TYPE_CHECKING
from urllib.parse import urlparse

from lsprotocol import types
from pygls.lsp.server import LanguageServer

from nasa_lsp._languages import language_for_suffix
from nasa_lsp.analyzer import Diagnostic, analyze

if TYPE_CHECKING:
    from pygls.workspace import TextDocument

server = LanguageServer("nasa-lsp", "0.3.0")


def language_for_uri(uri: str) -> str | None:
    """Infer the analyzer language from a document URI's file extension."""
    assert uri
    assert isinstance(uri, str)
    suffix = PurePosixPath(urlparse(uri).path).suffix
    return language_for_suffix(suffix)


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
    language = language_for_uri(doc.uri)
    diagnostics: list[Diagnostic] = [] if language is None else analyze(doc.source, language)[0]
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
