"""WebSocket connection manager for live updates."""

import json
import logging
from collections import defaultdict

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        # General notification connections
        self._connections: list[WebSocket] = []
        # Run-specific connections (run_id -> list of websockets)
        self._run_connections: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, websocket: WebSocket) -> None:
        """Accept a general notification connection."""
        await websocket.accept()
        self._connections.append(websocket)
        logger.debug(f"WebSocket connected. Total: {len(self._connections)}")

    async def connect_to_run(self, websocket: WebSocket, run_id: int) -> None:
        """Accept a run-specific connection for live output."""
        await websocket.accept()
        self._run_connections[run_id].append(websocket)
        logger.debug(f"WebSocket connected to run {run_id}")

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a general connection."""
        if websocket in self._connections:
            self._connections.remove(websocket)
            logger.debug(f"WebSocket disconnected. Total: {len(self._connections)}")

    def disconnect_from_run(self, websocket: WebSocket, run_id: int) -> None:
        """Remove a run-specific connection."""
        if run_id in self._run_connections:
            conns = self._run_connections[run_id]
            if websocket in conns:
                conns.remove(websocket)
            if not conns:
                del self._run_connections[run_id]

    async def broadcast(self, message: dict) -> None:
        """Send a message to all general connections."""
        data = json.dumps(message)
        disconnected: list[WebSocket] = []
        for ws in self._connections:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(ws)

    async def send_to_run(self, run_id: int, message: dict) -> None:
        """Send a message to all connections watching a specific run."""
        if run_id not in self._run_connections:
            return

        data = json.dumps(message)
        disconnected: list[WebSocket] = []
        for ws in self._run_connections[run_id]:
            try:
                await ws.send_text(data)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect_from_run(ws, run_id)

    async def broadcast_run_status(self, run_id: int, status: str, **extra) -> None:
        """Broadcast a run status change to both run-watchers and general listeners."""
        message = {
            "type": "run_status_changed",
            "run_id": run_id,
            "status": status,
            **extra,
        }
        await self.send_to_run(run_id, message)
        await self.broadcast(message)

    async def send_run_output(self, run_id: int, line: str) -> None:
        """Send a line of live output to run watchers."""
        await self.send_to_run(run_id, {
            "type": "run_output",
            "run_id": run_id,
            "line": line,
        })

    async def broadcast_notification(self, title: str, message: str, level: str = "info") -> None:
        """Broadcast a notification to all connections."""
        await self.broadcast({
            "type": "notification",
            "title": title,
            "message": message,
            "level": level,
        })

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    @property
    def run_connection_count(self) -> int:
        return sum(len(conns) for conns in self._run_connections.values())


# Singleton manager
ws_manager = ConnectionManager()
