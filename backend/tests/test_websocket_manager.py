"""Story TEST-1 — `src.websocket.manager.ConnectionManager` coverage.

CLAUDE.md flagged this as a high-risk gap: the manager mediates
between asyncio websocket coroutines and background-thread broadcast
calls (via `asyncio.run_coroutine_threadsafe`), so a disconnected
client mid-broadcast or a concurrent connect during a snapshot
can corrupt internal state. Zero tests existed before.

These tests run *without* a real FastAPI / Starlette WebSocket — we
substitute a tiny stub that records `send_text` calls and can be
configured to raise (simulating a closed client). The manager only
relies on `accept()` and `send_text()` being awaitable; no further
WebSocket surface is needed.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from src.websocket.manager import ConnectionManager


# ---------------------------------------------------------------------------
# Tiny stub WebSocket: `accept()` is a no-op coro, `send_text` is an AsyncMock
# that the test can configure to raise.
# ---------------------------------------------------------------------------


class _StubWebSocket:
    def __init__(self, *, fail_on_send: bool = False) -> None:
        self.sent: list[str] = []
        self.fail_on_send = fail_on_send
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_text(self, data: str) -> None:
        if self.fail_on_send:
            raise ConnectionError("client gone")
        self.sent.append(data)


def _make_ws(**kw: Any) -> _StubWebSocket:
    return _StubWebSocket(**kw)


# ---------------------------------------------------------------------------
# connect / disconnect / counts
# ---------------------------------------------------------------------------


class TestConnectDisconnect:
    @pytest.mark.asyncio
    async def test_connect_appends_and_accepts(self):
        m = ConnectionManager()
        ws = _make_ws()
        await m.connect(ws)
        assert ws.accepted is True
        assert m.connection_count == 1

    @pytest.mark.asyncio
    async def test_disconnect_removes(self):
        m = ConnectionManager()
        ws = _make_ws()
        await m.connect(ws)
        m.disconnect(ws)
        assert m.connection_count == 0

    def test_disconnect_unknown_ws_is_noop(self):
        m = ConnectionManager()
        m.disconnect(_make_ws())  # doesn't raise
        assert m.connection_count == 0

    @pytest.mark.asyncio
    async def test_run_connection_lifecycle(self):
        m = ConnectionManager()
        ws_a = _make_ws()
        ws_b = _make_ws()
        await m.connect_to_run(ws_a, run_id=42)
        await m.connect_to_run(ws_b, run_id=42)
        assert m.run_connection_count == 2

        m.disconnect_from_run(ws_a, run_id=42)
        assert m.run_connection_count == 1
        m.disconnect_from_run(ws_b, run_id=42)
        # Bucket is cleaned up when empty.
        assert 42 not in m._run_connections
        assert m.run_connection_count == 0


# ---------------------------------------------------------------------------
# broadcast — happy path + dead-connection cleanup
# ---------------------------------------------------------------------------


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_general_connections(self):
        m = ConnectionManager()
        ws_a, ws_b = _make_ws(), _make_ws()
        await m.connect(ws_a)
        await m.connect(ws_b)

        await m.broadcast({"hello": "world"})

        assert ws_a.sent == ['{"hello": "world"}']
        assert ws_b.sent == ['{"hello": "world"}']

    @pytest.mark.asyncio
    async def test_broadcast_drops_failing_connection(self):
        m = ConnectionManager()
        good = _make_ws()
        bad = _make_ws(fail_on_send=True)
        await m.connect(good)
        await m.connect(bad)

        await m.broadcast({"k": 1})

        # Good ws got the message; bad ws was removed from the pool.
        assert good.sent == ['{"k": 1}']
        assert m.connection_count == 1
        assert good in m._connections
        assert bad not in m._connections

    @pytest.mark.asyncio
    async def test_broadcast_with_no_connections_is_noop(self):
        m = ConnectionManager()
        await m.broadcast({"x": 1})  # must not raise

    @pytest.mark.asyncio
    async def test_send_to_run_targets_only_that_run(self):
        m = ConnectionManager()
        ws_run1 = _make_ws()
        ws_run2 = _make_ws()
        ws_general = _make_ws()
        await m.connect_to_run(ws_run1, run_id=1)
        await m.connect_to_run(ws_run2, run_id=2)
        await m.connect(ws_general)

        await m.send_to_run(1, {"line": "hello"})

        assert ws_run1.sent == ['{"line": "hello"}']
        assert ws_run2.sent == []
        assert ws_general.sent == []

    @pytest.mark.asyncio
    async def test_send_to_run_unknown_id_is_noop(self):
        m = ConnectionManager()
        await m.send_to_run(999, {"x": 1})  # must not raise

    @pytest.mark.asyncio
    async def test_send_to_run_drops_failing_connection(self):
        m = ConnectionManager()
        good = _make_ws()
        bad = _make_ws(fail_on_send=True)
        await m.connect_to_run(good, run_id=7)
        await m.connect_to_run(bad, run_id=7)

        await m.send_to_run(7, {"line": "hi"})

        assert good.sent == ['{"line": "hi"}']
        assert bad not in m._run_connections.get(7, [])


# ---------------------------------------------------------------------------
# Convenience broadcasters — assert shape, not transport
# ---------------------------------------------------------------------------


class TestConvenienceBroadcasters:
    @pytest.mark.asyncio
    async def test_broadcast_run_status_hits_run_and_general(self):
        m = ConnectionManager()
        run_ws = _make_ws()
        gen_ws = _make_ws()
        await m.connect_to_run(run_ws, run_id=5)
        await m.connect(gen_ws)

        await m.broadcast_run_status(run_id=5, status="passed", extra_info="ok")

        # Both saw the same payload.
        for sent in (run_ws.sent, gen_ws.sent):
            assert len(sent) == 1
            payload = json.loads(sent[0])
            assert payload["type"] == "run_status_changed"
            assert payload["run_id"] == 5
            assert payload["status"] == "passed"
            assert payload["extra_info"] == "ok"

    @pytest.mark.asyncio
    async def test_send_run_output_only_run_watchers(self):
        m = ConnectionManager()
        watcher = _make_ws()
        outsider = _make_ws()
        await m.connect_to_run(watcher, run_id=11)
        await m.connect(outsider)

        await m.send_run_output(11, "log line")

        assert outsider.sent == []
        assert json.loads(watcher.sent[0]) == {
            "type": "run_output", "run_id": 11, "line": "log line",
        }

    @pytest.mark.asyncio
    async def test_broadcast_package_status_shape(self):
        m = ConnectionManager()
        ws = _make_ws()
        await m.connect(ws)
        await m.broadcast_package_status(
            env_id=3, package_name="robot", status="installed",
            installed_version="7.3",
        )
        payload = json.loads(ws.sent[0])
        assert payload == {
            "type": "package_status_changed",
            "environment_id": 3,
            "package_name": "robot",
            "status": "installed",
            "installed_version": "7.3",
        }

    @pytest.mark.asyncio
    async def test_broadcast_recording_event_shape(self):
        m = ConnectionManager()
        ws = _make_ws()
        await m.connect(ws)
        await m.broadcast_recording_event(
            recording_id=42, event_data={"action": "click", "selector": "#go"},
        )
        payload = json.loads(ws.sent[0])
        assert payload["type"] == "recording_event"
        assert payload["recording_id"] == 42
        assert payload["event"] == {"action": "click", "selector": "#go"}


# ---------------------------------------------------------------------------
# Concurrency — two coros mutating the manager at once
# ---------------------------------------------------------------------------


class TestThreadSafety:
    @pytest.mark.asyncio
    async def test_broadcast_concurrent_with_disconnect_does_not_corrupt(self):
        """A broadcast that crosses an await point while another task
        disconnects a websocket must not crash on the in-flight snapshot.
        """
        m = ConnectionManager()
        ws_a, ws_b, ws_c = _make_ws(), _make_ws(), _make_ws()
        await m.connect(ws_a)
        await m.connect(ws_b)
        await m.connect(ws_c)

        # Broadcast many times in one task while another task drops
        # connections — the snapshot-under-lock pattern must isolate
        # the broadcast from the mutation.
        async def spammer():
            for _ in range(50):
                await m.broadcast({"i": "ping"})

        async def churn():
            for _ in range(50):
                m.disconnect(ws_b)
                await m.connect(ws_b)

        await asyncio.gather(spammer(), churn())
        # No exception means the lock did its job; further state-shape
        # assertions would race the churn task.
        assert m.connection_count >= 1
