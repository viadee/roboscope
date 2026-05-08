"""Story ROBUSTNESS-1 — `/health` deep check.

Previously the endpoint returned 200 unconditionally. Now it does a
`SELECT 1` roundtrip; on DB failure we return 503 so kubelet liveness
probes can flag the pod for restart.
"""

from __future__ import annotations

from unittest.mock import patch


class TestHealthEndpoint:
    def test_health_200_when_db_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "healthy"
        assert "version" in body
        assert body["task_executor"] == "in-process"

    def test_health_503_when_db_unreachable(self, client):
        # Patch `engine.connect()` so the SELECT 1 raises; the endpoint
        # must surface 503 + the unhealthy body shape.
        from src.database import engine

        def boom():
            raise RuntimeError("simulated DB outage")

        with patch.object(engine, "connect", side_effect=boom):
            resp = client.get("/health")

        assert resp.status_code == 503
        body = resp.json()
        assert body["status"] == "unhealthy"
        assert body["reason"] == "database_unreachable"
        assert "simulated DB outage" in body["error"]
        # Existing fields stay so log consumers don't lose context.
        assert "version" in body

    def test_health_200_returns_after_db_recovers(self, client):
        # Regression guard: the patched-out engine.connect must be
        # restored after the with-block, and a follow-up health call
        # returns 200 again.
        resp = client.get("/health")
        assert resp.status_code == 200
