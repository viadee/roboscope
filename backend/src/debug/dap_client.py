"""DAP request/response/event router.

Sits one level above ``dap_protocol`` (which only knows wire bytes).
Responsibilities:

* Allocate ``seq`` numbers monotonically.
* Match incoming responses to outstanding ``request`` futures by
  ``request_seq``.
* Dispatch incoming events to registered handlers by ``event`` name.
* Surface application-level errors (``response.success == false``)
  as :class:`DapApplicationError` so callers can ``except`` them.

A single read loop pumps the underlying stream — clients must call
:meth:`DapClient.start` once after connecting and :meth:`stop` on
shutdown. The loop logs and re-raises protocol errors; transport
errors close the client and reject all pending futures.

Event handlers are sync callables ``(event_body) -> None``. We don't
do async handlers here; the caller can spawn its own task from inside
the handler if needed. Keeping handlers sync simplifies cleanup
semantics during ``stop()``.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from src.debug.dap_protocol import (
    DapMessage,
    DapProtocolError,
    read_message,
    write_message,
)

logger = logging.getLogger("roboscope.debug.dap")

EventHandler = Callable[[dict[str, Any]], None]


class DapApplicationError(RuntimeError):
    """Raised when DAP returns ``success=false`` for a request."""

    def __init__(self, command: str, message: str) -> None:
        super().__init__(f"{command}: {message}")
        self.command = command
        self.message = message


class DapClient:
    """Async DAP request/response/event router."""

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        *,
        request_timeout: float = 30.0,
    ) -> None:
        self._reader = reader
        self._writer = writer
        self._request_timeout = request_timeout

        self._next_seq = 1
        self._pending: dict[int, asyncio.Future[dict[str, Any]]] = {}
        self._event_handlers: dict[str, list[EventHandler]] = {}
        self._read_task: asyncio.Task[None] | None = None
        self._closed = False

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> None:
        """Spawn the read pump. Idempotent — calling twice is a no-op."""
        if self._read_task is None:
            self._read_task = asyncio.create_task(self._read_loop())

    async def stop(self) -> None:
        """Cancel the read loop and reject every pending future."""
        self._closed = True
        if self._read_task is not None:
            self._read_task.cancel()
            try:
                await self._read_task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
            self._read_task = None
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:  # noqa: BLE001 — best-effort close
            pass
        for fut in self._pending.values():
            if not fut.done():
                fut.set_exception(ConnectionResetError("DAP client stopped"))
        self._pending.clear()

    # -- request / response ------------------------------------------------

    async def request(
        self, command: str, arguments: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Send a DAP request and await its response body.

        Raises :class:`DapApplicationError` on ``success=false`` so the
        caller can branch on protocol-level vs application-level
        failures. Times out per ``request_timeout``.
        """
        if self._closed:
            raise ConnectionResetError("DAP client is closed")
        seq = self._next_seq
        self._next_seq += 1
        fut: asyncio.Future[dict[str, Any]] = (
            asyncio.get_running_loop().create_future()
        )
        self._pending[seq] = fut
        msg: DapMessage = {
            "seq": seq,
            "type": "request",
            "command": command,
            "arguments": arguments or {},
        }
        try:
            await write_message(self._writer, msg)
            return await asyncio.wait_for(fut, timeout=self._request_timeout)
        except asyncio.TimeoutError:
            self._pending.pop(seq, None)
            raise
        except Exception:
            self._pending.pop(seq, None)
            raise

    # -- event subscription ------------------------------------------------

    def on_event(self, event: str, handler: EventHandler) -> None:
        """Register a handler for ``event``. Multiple handlers per
        event are fine; they fire in registration order. Handlers
        run inside the read loop's task — keep them fast."""
        self._event_handlers.setdefault(event, []).append(handler)

    # -- internals ---------------------------------------------------------

    async def _read_loop(self) -> None:
        try:
            while True:
                msg = await read_message(self._reader)
                self._dispatch(msg)
        except asyncio.CancelledError:
            raise
        except (DapProtocolError, ConnectionError, asyncio.IncompleteReadError) as e:
            logger.warning("DAP read loop ended: %s", e)
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(e)
            self._pending.clear()
        except Exception as e:  # noqa: BLE001 — last-resort guard
            logger.exception("DAP read loop crashed")
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(e)
            self._pending.clear()
            raise

    def _dispatch(self, msg: DapMessage) -> None:
        kind = msg.get("type")
        if kind == "response":
            req_seq = msg.get("request_seq")
            if req_seq is None:
                logger.warning("DAP response without request_seq: %s", msg)
                return
            fut = self._pending.pop(req_seq, None)
            if fut is None or fut.done():
                return
            if msg.get("success", False):
                fut.set_result(dict(msg.get("body") or {}))
            else:
                fut.set_exception(
                    DapApplicationError(
                        msg.get("command", "?"),
                        msg.get("message", "unknown error"),
                    )
                )
        elif kind == "event":
            event = msg.get("event") or ""
            handlers = self._event_handlers.get(event, [])
            body = dict(msg.get("body") or {})
            for h in handlers:
                try:
                    h(body)
                except Exception:  # noqa: BLE001
                    logger.exception(
                        "DAP event handler for %r raised", event
                    )
        else:
            # Unknown message types are logged and ignored — DAP is
            # forward-extensible and we don't want to crash the loop
            # on a future spec addition.
            logger.debug("Ignoring DAP message of unknown type: %s", msg)
