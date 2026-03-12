"""Tests for WebSocket ConnectionManager."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.websocket.manager import ConnectionManager


def _make_ws() -> MagicMock:
    """Create a mock WebSocket with async accept/send_text methods."""
    ws = MagicMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


class TestConnect:
    @pytest.mark.asyncio
    async def test_connect_accepts_and_adds(self):
        mgr = ConnectionManager()
        ws = _make_ws()

        await mgr.connect(ws)

        ws.accept.assert_awaited_once()
        assert mgr.connection_count == 1

    @pytest.mark.asyncio
    async def test_connect_multiple(self):
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()

        await mgr.connect(ws1)
        await mgr.connect(ws2)

        assert mgr.connection_count == 2


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_disconnect_removes_connection(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws)
        assert mgr.connection_count == 1

        mgr.disconnect(ws)

        assert mgr.connection_count == 0

    def test_disconnect_nonexistent_is_noop(self):
        mgr = ConnectionManager()
        ws = _make_ws()

        # Should not raise
        mgr.disconnect(ws)
        assert mgr.connection_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_only_removes_target(self):
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect(ws1)
        await mgr.connect(ws2)

        mgr.disconnect(ws1)

        assert mgr.connection_count == 1


class TestConnectToRun:
    @pytest.mark.asyncio
    async def test_connect_to_run_accepts_and_adds(self):
        mgr = ConnectionManager()
        ws = _make_ws()

        await mgr.connect_to_run(ws, run_id=42)

        ws.accept.assert_awaited_once()
        assert mgr.run_connection_count == 1

    @pytest.mark.asyncio
    async def test_connect_multiple_to_same_run(self):
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()

        await mgr.connect_to_run(ws1, run_id=1)
        await mgr.connect_to_run(ws2, run_id=1)

        assert mgr.run_connection_count == 2

    @pytest.mark.asyncio
    async def test_connect_to_different_runs(self):
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()

        await mgr.connect_to_run(ws1, run_id=1)
        await mgr.connect_to_run(ws2, run_id=2)

        assert mgr.run_connection_count == 2


class TestDisconnectFromRun:
    @pytest.mark.asyncio
    async def test_disconnect_from_run_removes(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect_to_run(ws, run_id=5)

        mgr.disconnect_from_run(ws, run_id=5)

        assert mgr.run_connection_count == 0

    @pytest.mark.asyncio
    async def test_disconnect_from_run_cleans_up_empty_list(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect_to_run(ws, run_id=5)

        mgr.disconnect_from_run(ws, run_id=5)

        # Internal dict should have removed the key
        assert 5 not in mgr._run_connections

    def test_disconnect_from_run_nonexistent_run_is_noop(self):
        mgr = ConnectionManager()
        ws = _make_ws()

        # Should not raise
        mgr.disconnect_from_run(ws, run_id=999)

    @pytest.mark.asyncio
    async def test_disconnect_from_run_nonexistent_ws_is_noop(self):
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect_to_run(ws1, run_id=5)

        # ws2 was never connected — should not raise
        mgr.disconnect_from_run(ws2, run_id=5)
        assert mgr.run_connection_count == 1


class TestBroadcast:
    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all(self):
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect(ws1)
        await mgr.connect(ws2)

        msg = {"type": "test", "data": "hello"}
        await mgr.broadcast(msg)

        expected = json.dumps(msg)
        ws1.send_text.assert_awaited_once_with(expected)
        ws2.send_text.assert_awaited_once_with(expected)

    @pytest.mark.asyncio
    async def test_broadcast_no_connections_is_noop(self):
        mgr = ConnectionManager()
        # Should not raise
        await mgr.broadcast({"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_removes_failed_connections(self):
        mgr = ConnectionManager()
        ws_good = _make_ws()
        ws_bad = _make_ws()
        ws_bad.send_text = AsyncMock(side_effect=Exception("connection closed"))
        await mgr.connect(ws_good)
        await mgr.connect(ws_bad)
        assert mgr.connection_count == 2

        await mgr.broadcast({"type": "test"})

        # Bad connection should have been removed
        assert mgr.connection_count == 1
        ws_good.send_text.assert_awaited_once()


class TestSendToRun:
    @pytest.mark.asyncio
    async def test_send_to_run_delivers(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect_to_run(ws, run_id=10)

        msg = {"type": "run_output", "line": "test line"}
        await mgr.send_to_run(10, msg)

        ws.send_text.assert_awaited_once_with(json.dumps(msg))

    @pytest.mark.asyncio
    async def test_send_to_run_no_watchers_is_noop(self):
        mgr = ConnectionManager()
        # Should not raise
        await mgr.send_to_run(999, {"type": "test"})

    @pytest.mark.asyncio
    async def test_send_to_run_only_targets_correct_run(self):
        mgr = ConnectionManager()
        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect_to_run(ws1, run_id=1)
        await mgr.connect_to_run(ws2, run_id=2)

        await mgr.send_to_run(1, {"type": "test"})

        ws1.send_text.assert_awaited_once()
        ws2.send_text.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_to_run_removes_failed_connections(self):
        mgr = ConnectionManager()
        ws_bad = _make_ws()
        ws_bad.send_text = AsyncMock(side_effect=Exception("closed"))
        await mgr.connect_to_run(ws_bad, run_id=7)

        await mgr.send_to_run(7, {"type": "test"})

        assert mgr.run_connection_count == 0


class TestBroadcastRunStatus:
    @pytest.mark.asyncio
    async def test_broadcast_run_status_sends_to_both(self):
        mgr = ConnectionManager()
        ws_general = _make_ws()
        ws_run = _make_ws()
        await mgr.connect(ws_general)
        await mgr.connect_to_run(ws_run, run_id=3)

        await mgr.broadcast_run_status(3, "passed")

        expected = json.dumps({
            "type": "run_status_changed",
            "run_id": 3,
            "status": "passed",
        })
        ws_general.send_text.assert_awaited_once_with(expected)
        ws_run.send_text.assert_awaited_once_with(expected)

    @pytest.mark.asyncio
    async def test_broadcast_run_status_with_extra(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws)

        await mgr.broadcast_run_status(1, "failed", error="timeout")

        expected = json.dumps({
            "type": "run_status_changed",
            "run_id": 1,
            "status": "failed",
            "error": "timeout",
        })
        ws.send_text.assert_awaited_once_with(expected)


class TestBroadcastDockerBuildLog:
    @pytest.mark.asyncio
    async def test_broadcast_docker_build_log(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws)

        await mgr.broadcast_docker_build_log(env_id=2, line="Step 1/5", done=False)

        expected = json.dumps({
            "type": "docker_build_log",
            "environment_id": 2,
            "line": "Step 1/5",
            "done": False,
        })
        ws.send_text.assert_awaited_once_with(expected)

    @pytest.mark.asyncio
    async def test_broadcast_docker_build_log_done(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws)

        await mgr.broadcast_docker_build_log(env_id=2, line="Complete", done=True)

        call_data = json.loads(ws.send_text.call_args[0][0])
        assert call_data["done"] is True


class TestBroadcastNotification:
    @pytest.mark.asyncio
    async def test_broadcast_notification(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws)

        await mgr.broadcast_notification("Build done", "Image ready", level="success")

        call_data = json.loads(ws.send_text.call_args[0][0])
        assert call_data["type"] == "notification"
        assert call_data["title"] == "Build done"
        assert call_data["message"] == "Image ready"
        assert call_data["level"] == "success"

    @pytest.mark.asyncio
    async def test_broadcast_notification_default_level(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws)

        await mgr.broadcast_notification("Info", "msg")

        call_data = json.loads(ws.send_text.call_args[0][0])
        assert call_data["level"] == "info"


class TestBroadcastPackageStatus:
    @pytest.mark.asyncio
    async def test_broadcast_package_status(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws)

        await mgr.broadcast_package_status(env_id=1, package_name="robotframework", status="installed")

        call_data = json.loads(ws.send_text.call_args[0][0])
        assert call_data["type"] == "package_status_changed"
        assert call_data["environment_id"] == 1
        assert call_data["package_name"] == "robotframework"
        assert call_data["status"] == "installed"

    @pytest.mark.asyncio
    async def test_broadcast_package_status_with_extra(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect(ws)

        await mgr.broadcast_package_status(
            env_id=1, package_name="requests", status="error", error="network timeout"
        )

        call_data = json.loads(ws.send_text.call_args[0][0])
        assert call_data["error"] == "network timeout"


class TestSendRunOutput:
    @pytest.mark.asyncio
    async def test_send_run_output(self):
        mgr = ConnectionManager()
        ws = _make_ws()
        await mgr.connect_to_run(ws, run_id=10)

        await mgr.send_run_output(10, "PASS :: Test Suite")

        call_data = json.loads(ws.send_text.call_args[0][0])
        assert call_data["type"] == "run_output"
        assert call_data["run_id"] == 10
        assert call_data["line"] == "PASS :: Test Suite"


class TestConnectionCounts:
    @pytest.mark.asyncio
    async def test_connection_count(self):
        mgr = ConnectionManager()
        assert mgr.connection_count == 0

        ws = _make_ws()
        await mgr.connect(ws)
        assert mgr.connection_count == 1

        mgr.disconnect(ws)
        assert mgr.connection_count == 0

    @pytest.mark.asyncio
    async def test_run_connection_count(self):
        mgr = ConnectionManager()
        assert mgr.run_connection_count == 0

        ws1 = _make_ws()
        ws2 = _make_ws()
        await mgr.connect_to_run(ws1, run_id=1)
        await mgr.connect_to_run(ws2, run_id=2)
        assert mgr.run_connection_count == 2

        mgr.disconnect_from_run(ws1, run_id=1)
        assert mgr.run_connection_count == 1
