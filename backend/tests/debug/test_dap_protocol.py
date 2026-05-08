"""Wire-format unit tests for DAP framing helpers.

Scope: read/write a single message with various legitimate header
shapes plus every malformed-header / malformed-body case the
protocol layer is expected to detect. No higher-level routing.
"""

from __future__ import annotations

import asyncio
import json

import pytest

from src.debug.dap_protocol import (
    DapProtocolError,
    encode_message,
    read_message,
    write_message,
)


def _stream_from_bytes(data: bytes) -> asyncio.StreamReader:
    """Build a populated, EOF-marked StreamReader without an
    actual socket. Used pervasively below."""
    reader = asyncio.StreamReader()
    reader.feed_data(data)
    reader.feed_eof()
    return reader


class TestEncode:
    def test_round_trip_request(self) -> None:
        msg = {
            "seq": 1,
            "type": "request",
            "command": "initialize",
            "arguments": {"clientID": "roboscope"},
        }
        wire = encode_message(msg)
        assert wire.startswith(b"Content-Length: ")
        # Header terminator must be exactly CRLF CRLF.
        assert b"\r\n\r\n" in wire
        # Body parses back to the original dict.
        body = wire.split(b"\r\n\r\n", 1)[1]
        assert json.loads(body) == msg

    def test_unicode_payload_is_utf8_byte_counted(self) -> None:
        msg = {"seq": 2, "type": "event", "event": "output", "body": {"output": "übergröße"}}
        wire = encode_message(msg)
        body = wire.split(b"\r\n\r\n", 1)[1]
        # Content-Length header value matches the BYTE length (utf-8),
        # not the codepoint count.
        header = wire.split(b"\r\n\r\n", 1)[0]
        declared = int(header.removeprefix(b"Content-Length: "))
        assert declared == len(body)


class TestReadMessage:
    @pytest.mark.asyncio
    async def test_reads_minimal_request(self) -> None:
        body = b'{"seq":1,"type":"request"}'
        reader = _stream_from_bytes(
            f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body
        )
        msg = await read_message(reader)
        assert msg == {"seq": 1, "type": "request"}

    @pytest.mark.asyncio
    async def test_tolerates_lowercase_header_key(self) -> None:
        body = b'{"seq":1,"type":"event"}'
        reader = _stream_from_bytes(
            f"content-length: {len(body)}\r\n\r\n".encode("ascii") + body
        )
        msg = await read_message(reader)
        assert msg["type"] == "event"

    @pytest.mark.asyncio
    async def test_tolerates_extra_optional_header(self) -> None:
        body = b'{"seq":1,"type":"event"}'
        reader = _stream_from_bytes(
            b"Content-Type: application/json\r\n"
            + f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            + body
        )
        msg = await read_message(reader)
        assert msg["seq"] == 1

    @pytest.mark.asyncio
    async def test_round_trip_via_encode(self) -> None:
        original = {
            "seq": 7,
            "type": "response",
            "request_seq": 3,
            "success": True,
            "command": "stackTrace",
            "body": {"stackFrames": [{"id": 0, "name": "main"}]},
        }
        reader = _stream_from_bytes(encode_message(original))
        assert await read_message(reader) == original

    @pytest.mark.asyncio
    async def test_eof_mid_header_is_protocol_error(self) -> None:
        reader = _stream_from_bytes(b"Content-Lengt")
        with pytest.raises(DapProtocolError, match="mid-header"):
            await read_message(reader)

    @pytest.mark.asyncio
    async def test_missing_content_length_is_protocol_error(self) -> None:
        reader = _stream_from_bytes(b"X-Other: 1\r\n\r\nignored")
        with pytest.raises(DapProtocolError, match="missing Content-Length"):
            await read_message(reader)

    @pytest.mark.asyncio
    async def test_non_int_content_length_is_protocol_error(self) -> None:
        reader = _stream_from_bytes(b"Content-Length: not-a-number\r\n\r\nx")
        with pytest.raises(DapProtocolError, match="not an integer"):
            await read_message(reader)

    @pytest.mark.asyncio
    async def test_eof_mid_body_is_protocol_error(self) -> None:
        reader = _stream_from_bytes(b"Content-Length: 100\r\n\r\nshort")
        with pytest.raises(DapProtocolError, match="mid-body"):
            await read_message(reader)

    @pytest.mark.asyncio
    async def test_invalid_utf8_body_is_protocol_error(self) -> None:
        # Lone continuation byte → invalid UTF-8 sequence.
        body = b"\x80\x80"
        reader = _stream_from_bytes(
            b"Content-Length: 2\r\n\r\n" + body
        )
        with pytest.raises(DapProtocolError, match="not valid UTF-8 JSON"):
            await read_message(reader)

    @pytest.mark.asyncio
    async def test_invalid_json_body_is_protocol_error(self) -> None:
        body = b"{this is not json}"
        reader = _stream_from_bytes(
            f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body
        )
        with pytest.raises(DapProtocolError, match="not valid UTF-8 JSON"):
            await read_message(reader)

    @pytest.mark.asyncio
    async def test_array_body_is_protocol_error(self) -> None:
        body = b"[1,2,3]"
        reader = _stream_from_bytes(
            f"Content-Length: {len(body)}\r\n\r\n".encode("ascii") + body
        )
        with pytest.raises(DapProtocolError, match="not a JSON object"):
            await read_message(reader)


class TestWriteMessage:
    @pytest.mark.asyncio
    async def test_writes_framed_payload(self) -> None:
        # Use a pipe pair to exercise StreamWriter.drain.
        rd, wr = asyncio.StreamReader(), asyncio.StreamReader()  # placeholders
        del rd, wr
        # Simpler: direct in-memory transport.
        loop = asyncio.get_running_loop()
        host_reader = asyncio.StreamReader()

        class _SinkProtocol(asyncio.Protocol):
            def data_received(self, data: bytes) -> None:
                host_reader.feed_data(data)

            def connection_lost(self, exc: BaseException | None) -> None:
                host_reader.feed_eof()

        # Local TCP loopback for the test.
        srv = await asyncio.start_server(
            lambda r, w: None, host="127.0.0.1", port=0
        )
        port = srv.sockets[0].getsockname()[1]
        srv.close()
        await srv.wait_closed()

        # Reuse the explicit reader/writer pair via open_connection
        # against a fresh server that just relays bytes.
        captured: list[bytes] = []

        async def handle(r: asyncio.StreamReader, w: asyncio.StreamWriter) -> None:
            data = await r.read(-1)
            captured.append(data)
            w.close()

        server = await asyncio.start_server(handle, host="127.0.0.1", port=0)
        bound_port = server.sockets[0].getsockname()[1]
        client_reader, client_writer = await asyncio.open_connection(
            "127.0.0.1", bound_port
        )
        try:
            await write_message(client_writer, {"seq": 1, "type": "request"})
            client_writer.close()
            await client_writer.wait_closed()
        finally:
            server.close()
            await server.wait_closed()
            del client_reader  # silence "unused" warning
            del loop

        assert captured, "server received no bytes"
        wire = b"".join(captured)
        assert wire.startswith(b"Content-Length:")
        assert b"\r\n\r\n" in wire
