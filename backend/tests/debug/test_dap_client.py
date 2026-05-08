"""DapClient routing tests.

Spins up an in-process asyncio TCP server that plays the DAP-server
side, exercises every request/response/event path the production
code uses, then asserts the client's behavior. No subprocess, no
real Robot Framework, no network access beyond loopback.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from src.debug.dap_client import DapApplicationError, DapClient
from src.debug.dap_protocol import encode_message


# ---------------------------------------------------------------------------
# Test harness — minimal DAP fake server
# ---------------------------------------------------------------------------


class _FakeServer:
    """Bare DAP server. Tests register handlers per `command`; the
    server reads framed requests, calls the handler with the
    `arguments` dict, and writes a framed response back."""

    def __init__(self) -> None:
        self.handlers: dict[str, Any] = {}
        self.unsolicited_events: list[dict[str, Any]] = []
        self.received_requests: list[dict[str, Any]] = []
        self._server: asyncio.AbstractServer | None = None
        self._client_writer: asyncio.StreamWriter | None = None

    async def start(self) -> int:
        self._server = await asyncio.start_server(
            self._handle, host="127.0.0.1", port=0
        )
        return self._server.sockets[0].getsockname()[1]  # type: ignore[no-any-return]

    async def stop(self) -> None:
        if self._client_writer is not None:
            self._client_writer.close()
            try:
                await self._client_writer.wait_closed()
            except Exception:  # noqa: BLE001
                pass
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

    async def push_event(self, event: str, body: dict[str, Any]) -> None:
        if self._client_writer is None:
            self.unsolicited_events.append({"event": event, "body": body})
            return
        msg = {
            "seq": 999_000,
            "type": "event",
            "event": event,
            "body": body,
        }
        self._client_writer.write(encode_message(msg))  # type: ignore[arg-type]
        await self._client_writer.drain()

    async def _handle(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self._client_writer = writer
        # Drain any unsolicited events queued before the connection.
        for evt in self.unsolicited_events:
            await self.push_event(evt["event"], evt["body"])
        self.unsolicited_events = []

        while True:
            try:
                line = await reader.readuntil(b"\r\n\r\n")
            except (asyncio.IncompleteReadError, ConnectionError):
                return
            content_length = 0
            for hdr_line in line[:-4].split(b"\r\n"):
                if hdr_line.lower().startswith(b"content-length:"):
                    content_length = int(hdr_line.split(b":", 1)[1].strip())
            try:
                body = await reader.readexactly(content_length)
            except (asyncio.IncompleteReadError, ConnectionError):
                return
            req = json.loads(body)
            self.received_requests.append(req)

            handler = self.handlers.get(req.get("command"))
            if handler is None:
                # Default: success with empty body.
                response = {
                    "seq": 0,
                    "type": "response",
                    "request_seq": req["seq"],
                    "success": True,
                    "command": req["command"],
                    "body": {},
                }
            else:
                response = await handler(req)
            writer.write(encode_message(response))  # type: ignore[arg-type]
            await writer.drain()


@pytest.fixture
async def fake() -> Any:
    srv = _FakeServer()
    port = await srv.start()
    yield srv, port
    await srv.stop()


async def _connect(port: int) -> DapClient:
    reader, writer = await asyncio.open_connection("127.0.0.1", port)
    return DapClient(reader, writer, request_timeout=2.0)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestRequestResponse:
    @pytest.mark.asyncio
    async def test_request_returns_body_on_success(self, fake) -> None:
        srv, port = fake

        async def handle_initialize(req):  # type: ignore[no-untyped-def]
            return {
                "seq": 0,
                "type": "response",
                "request_seq": req["seq"],
                "success": True,
                "command": "initialize",
                "body": {"supportsConfigurationDoneRequest": True},
            }

        srv.handlers["initialize"] = handle_initialize
        client = await _connect(port)
        client.start()
        try:
            body = await client.request("initialize", {"clientID": "x"})
            assert body == {"supportsConfigurationDoneRequest": True}
            # The fake server saw exactly one request with the
            # arguments we sent.
            assert srv.received_requests[0]["arguments"] == {"clientID": "x"}
        finally:
            await client.stop()

    @pytest.mark.asyncio
    async def test_request_failure_raises_dap_application_error(self, fake) -> None:
        srv, port = fake

        async def handle(req):  # type: ignore[no-untyped-def]
            return {
                "seq": 0,
                "type": "response",
                "request_seq": req["seq"],
                "success": False,
                "command": "setBreakpoints",
                "message": "file not found: /etc/passwd",
            }

        srv.handlers["setBreakpoints"] = handle
        client = await _connect(port)
        client.start()
        try:
            with pytest.raises(DapApplicationError) as ei:
                await client.request("setBreakpoints", {"source": {"path": "x"}})
            assert ei.value.command == "setBreakpoints"
            assert "file not found" in ei.value.message
        finally:
            await client.stop()

    @pytest.mark.asyncio
    async def test_request_timeout_raises_timeout(self, fake) -> None:
        srv, port = fake

        async def handle(_req):  # type: ignore[no-untyped-def]
            await asyncio.sleep(5.0)
            return {}

        srv.handlers["evaluate"] = handle
        client = await _connect(port)
        client.start()
        try:
            with pytest.raises(asyncio.TimeoutError):
                await client.request("evaluate", {})
        finally:
            await client.stop()


class TestEventDispatch:
    @pytest.mark.asyncio
    async def test_event_handlers_fire_in_registration_order(self, fake) -> None:
        srv, port = fake
        client = await _connect(port)
        client.start()
        order: list[str] = []
        client.on_event("stopped", lambda b: order.append("first"))
        client.on_event("stopped", lambda b: order.append("second"))
        try:
            await srv.push_event("stopped", {"reason": "breakpoint"})
            # Give the read loop a tick to dispatch.
            for _ in range(20):
                if order:
                    break
                await asyncio.sleep(0.01)
            assert order == ["first", "second"]
        finally:
            await client.stop()

    @pytest.mark.asyncio
    async def test_raising_handler_is_isolated(self, fake) -> None:
        srv, port = fake
        client = await _connect(port)
        client.start()
        ok_called: list[int] = []

        def boom(_b: Any) -> None:
            raise RuntimeError("oops")

        def ok(_b: Any) -> None:
            ok_called.append(1)

        client.on_event("output", boom)
        client.on_event("output", ok)
        try:
            await srv.push_event("output", {"output": "hi"})
            for _ in range(20):
                if ok_called:
                    break
                await asyncio.sleep(0.01)
            assert ok_called == [1]
        finally:
            await client.stop()


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_stop_rejects_pending_futures(self, fake) -> None:
        srv, port = fake
        client = await _connect(port)
        client.start()

        async def slow(_req):  # type: ignore[no-untyped-def]
            await asyncio.sleep(10.0)
            return {}

        srv.handlers["evaluate"] = slow
        # Fire-and-forget a request; we'll cancel it via stop().
        task = asyncio.create_task(client.request("evaluate", {}))
        await asyncio.sleep(0.05)
        await client.stop()
        with pytest.raises((ConnectionResetError, asyncio.CancelledError)):
            await task

    @pytest.mark.asyncio
    async def test_idempotent_start(self, fake) -> None:
        _srv, port = fake
        client = await _connect(port)
        try:
            client.start()
            client.start()
            client.start()
            # No exceptions; one read task only.
            assert client._read_task is not None  # noqa: SLF001
        finally:
            await client.stop()

    @pytest.mark.asyncio
    async def test_request_after_close_raises(self, fake) -> None:
        _srv, port = fake
        client = await _connect(port)
        client.start()
        await client.stop()
        with pytest.raises(ConnectionResetError):
            await client.request("noop", {})
