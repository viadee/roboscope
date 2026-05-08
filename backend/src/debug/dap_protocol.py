"""Microsoft Debug Adapter Protocol — wire format helpers.

DAP messages are JSON objects framed with an HTTP-like header:

    Content-Length: <bytes>\\r\\n\\r\\n<utf-8-json-payload>

Spec: https://microsoft.github.io/debug-adapter-protocol/overview

Three message kinds, distinguished by the top-level ``type`` field:

* ``request`` — outbound from us, has ``seq`` + ``command``.
* ``response`` — inbound, refers back to a request via ``request_seq``,
  carries ``success`` and (optionally) ``body``.
* ``event`` — inbound, no request correlation; uses ``event`` field as
  discriminator (``stopped``, ``output``, ``terminated``, …).

This module is wire-format-only: it knows how to serialize, parse,
and frame messages. Everything higher-level (request/response
correlation, event subscriptions, lifecycle) lives in ``dap_client``
and ``robot_debug_session``.

Pure asyncio I/O — every helper takes/returns ``bytes`` or works
against an ``asyncio.StreamReader`` / ``StreamWriter``. No DB, no
threads, no Robot Framework imports.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Literal, NotRequired, TypedDict

# DAP message structure. The protocol allows any JSON, but every
# message we send / receive obeys this minimum shape.


class DapMessage(TypedDict):
    """Common envelope shared by request / response / event."""

    seq: int
    type: Literal["request", "response", "event"]
    # Request / response specifics
    command: NotRequired[str]
    request_seq: NotRequired[int]
    success: NotRequired[bool]
    arguments: NotRequired[dict[str, Any]]
    body: NotRequired[dict[str, Any]]
    # Event specifics
    event: NotRequired[str]
    # Error-response specifics
    message: NotRequired[str]


class DapProtocolError(RuntimeError):
    """Raised on framing / JSON-parse failures so callers can
    distinguish protocol errors from transport (``OSError``) and
    application (``DapApplicationError`` in dap_client) failures."""


# ---------------------------------------------------------------------------
# Frame helpers
# ---------------------------------------------------------------------------

# DAP only specifies ``Content-Length``; some implementations write
# ``Content-Type`` too but it's optional and we ignore it.
_HEADER_TERMINATOR = b"\r\n\r\n"
_CONTENT_LENGTH_PREFIX = b"Content-Length:"


def encode_message(msg: DapMessage) -> bytes:
    """Serialize a DAP message to wire-format bytes (header + body).

    Caller-supplied ``msg`` MUST already have a ``seq`` field set;
    sequence allocation is the client's job, not the wire layer's.
    """
    body = json.dumps(msg, separators=(",", ":")).encode("utf-8")
    header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
    return header + body


async def read_message(reader: asyncio.StreamReader) -> DapMessage:
    """Read one framed DAP message from the stream.

    Resilient to header-key casing variants and to multiple optional
    headers preceding the terminator (some servers emit ``Content-
    Type`` first). Raises :class:`DapProtocolError` on:

    * EOF before the header completes,
    * missing or unparseable ``Content-Length``,
    * EOF before the body completes,
    * JSON parse failure on the body,
    * the parsed body not being a JSON object.

    Plain ``OSError`` from the underlying stream still propagates so
    callers can distinguish "peer crashed" from "peer sent garbage".
    """
    # Read until the blank-line terminator. ``readuntil`` raises
    # IncompleteReadError on EOF — re-raise as protocol error.
    try:
        header_block = await reader.readuntil(_HEADER_TERMINATOR)
    except asyncio.IncompleteReadError as e:
        raise DapProtocolError(
            f"DAP peer closed connection mid-header (got {len(e.partial)} bytes)"
        ) from e

    # Header lines are CRLF-separated; drop the trailing empty line.
    raw_lines = header_block[:-len(_HEADER_TERMINATOR)].split(b"\r\n")
    content_length: int | None = None
    for line in raw_lines:
        if line[: len(_CONTENT_LENGTH_PREFIX)].lower() == _CONTENT_LENGTH_PREFIX.lower():
            value = line[len(_CONTENT_LENGTH_PREFIX):].strip()
            try:
                content_length = int(value)
            except ValueError as e:
                raise DapProtocolError(
                    f"DAP Content-Length is not an integer: {value!r}"
                ) from e
            break
    if content_length is None:
        raise DapProtocolError(
            f"DAP frame missing Content-Length header: {header_block!r}"
        )

    try:
        body_bytes = await reader.readexactly(content_length)
    except asyncio.IncompleteReadError as e:
        raise DapProtocolError(
            f"DAP peer closed connection mid-body "
            f"(declared {content_length} bytes, got {len(e.partial)})"
        ) from e

    try:
        parsed = json.loads(body_bytes.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise DapProtocolError(f"DAP body is not valid UTF-8 JSON: {e}") from e

    if not isinstance(parsed, dict):
        raise DapProtocolError(
            f"DAP body is not a JSON object: {type(parsed).__name__}"
        )

    return parsed  # type: ignore[return-value]


async def write_message(writer: asyncio.StreamWriter, msg: DapMessage) -> None:
    """Serialize and flush one DAP message to the stream."""
    writer.write(encode_message(msg))
    await writer.drain()
