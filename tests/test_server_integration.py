"""End-to-end tests that drive the real LSP server process over stdio.

These exercise `nasa serve` for real -- the stdio transport, the initialize
handshake, pygls' own workspace management, and the did_open/did_change
handlers -- rather than calling the handlers in-process. No stubbing.
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
from contextlib import contextmanager
from typing import IO, TYPE_CHECKING

import coverage

if TYPE_CHECKING:
    from collections.abc import Iterator

READ_TIMEOUT_SECONDS = 10.0
MAX_MESSAGES_BEFORE_DIAGNOSTICS = 10


def _subprocess_env() -> dict[str, str]:
    env = dict(os.environ)
    # Let the child record coverage too, but only when the parent run is
    # measuring -- otherwise a plain `pytest` run would litter .coverage.* files.
    if coverage.Coverage.current() is not None:
        env["COVERAGE_PROCESS_START"] = "pyproject.toml"
    return env


def _frame(payload: dict[str, object]) -> bytes:
    body = json.dumps(payload).encode()
    return b"Content-Length: %d\r\n\r\n%s" % (len(body), body)


_HEADER_SEPARATOR = b"\r\n\r\n"


class _Client:
    def __init__(self, proc: subprocess.Popen[bytes]) -> None:
        assert proc.stdin is not None, "server stdin must be a pipe"
        assert proc.stdout is not None, "server stdout must be a pipe"
        self._stdin: IO[bytes] = proc.stdin
        # Read from the raw fd with os.read so select() reflects the OS pipe.
        # Reading via the BufferedReader would pre-buffer bytes that select()
        # can no longer see, and the next select() would block forever.
        self._fd = proc.stdout.fileno()
        self._buffer = bytearray()

    def send(self, payload: dict[str, object]) -> None:
        self._stdin.write(_frame(payload))
        self._stdin.flush()

    def _fill(self, size: int) -> None:
        while len(self._buffer) < size:
            if not select.select([self._fd], [], [], READ_TIMEOUT_SECONDS)[0]:
                msg = "timed out waiting for a message from the server"
                raise TimeoutError(msg)
            chunk = os.read(self._fd, 65536)
            if not chunk:
                msg = "server closed stdout before a full message arrived"
                raise EOFError(msg)
            self._buffer.extend(chunk)

    def receive(self) -> dict[str, object]:
        while _HEADER_SEPARATOR not in self._buffer:
            self._fill(len(self._buffer) + 1)
        raw_headers, _, rest = self._buffer.partition(_HEADER_SEPARATOR)
        self._buffer = bytearray(rest)
        length = next(
            int(line.split(b":", 1)[1])
            for line in raw_headers.split(b"\r\n")
            if line.lower().startswith(b"content-length:")
        )
        self._fill(length)
        body = bytes(self._buffer[:length])
        self._buffer = bytearray(self._buffer[length:])
        return json.loads(body)

    def receive_diagnostics(self) -> list[dict[str, object]]:
        for _ in range(MAX_MESSAGES_BEFORE_DIAGNOSTICS):
            message = self.receive()
            if message.get("method") == "textDocument/publishDiagnostics":
                params = message["params"]
                assert isinstance(params, dict), "publishDiagnostics params must be an object"
                diagnostics = params["diagnostics"]
                assert isinstance(diagnostics, list), "diagnostics must be a list"
                return diagnostics
        msg = "server never published diagnostics"
        raise AssertionError(msg)


@contextmanager
def server_session() -> Iterator[_Client]:
    proc = subprocess.Popen(  # noqa: S603
        [sys.executable, "-m", "nasa_lsp.cli", "serve"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=_subprocess_env(),
    )
    try:
        client = _Client(proc)
        client.send(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"processId": None, "rootUri": None, "capabilities": {}},
            }
        )
        assert "result" in client.receive(), "server must answer initialize with a result"
        client.send({"jsonrpc": "2.0", "method": "initialized", "params": {}})

        yield client

        client.send({"jsonrpc": "2.0", "id": 99, "method": "shutdown", "params": None})
        _ = client.receive()
        client.send({"jsonrpc": "2.0", "method": "exit", "params": None})
        assert proc.wait(timeout=READ_TIMEOUT_SECONDS) == 0, "server must exit cleanly after the exit notification"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=READ_TIMEOUT_SECONDS)


def test_did_open_reports_diagnostics_over_stdio() -> None:
    with server_session() as client:
        client.send(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": "file:///open.py",
                        "languageId": "python",
                        "version": 1,
                        "text": "def foo(): pass",
                    },
                },
            }
        )
        diagnostics = client.receive_diagnostics()

    assert len(diagnostics) == 1
    assert diagnostics[0]["source"] == "NASA"


def test_did_change_reports_diagnostics_over_stdio() -> None:
    with server_session() as client:
        client.send(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didOpen",
                "params": {
                    "textDocument": {
                        "uri": "file:///change.py",
                        "languageId": "python",
                        "version": 1,
                        "text": "x = 1\n",
                    },
                },
            }
        )
        _ = client.receive_diagnostics()

        client.send(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/didChange",
                "params": {
                    "textDocument": {"uri": "file:///change.py", "version": 2},
                    "contentChanges": [{"text": "def foo(): pass"}],
                },
            }
        )
        diagnostics = client.receive_diagnostics()

    assert len(diagnostics) == 1
    assert diagnostics[0]["source"] == "NASA"
