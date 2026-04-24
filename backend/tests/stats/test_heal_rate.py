"""Story SH-6 — /stats/heal-rate aggregation tests."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.auth.models import User
from src.execution.models import ExecutionRun, RunStatus
from src.repos.models import Repository
from tests.conftest import auth_header


ENDPOINT = "/api/v1/stats/heal-rate"


@pytest.fixture
def repo(db_session: Session, admin_user: User) -> Repository:
    r = Repository(
        name="sh6-repo",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path="/tmp/sh6",
        created_by=admin_user.id,
    )
    db_session.add(r)
    db_session.flush()
    db_session.refresh(r)
    return r


def _write_audit_and_output(
    output_dir: Path,
    *,
    records: list[dict],
    test_outcomes: dict[str, str],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "heal_audit.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records), encoding="utf-8",
    )
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<robot>", "<suite>"]
    for name, status in test_outcomes.items():
        parts.append(f'<test name="{name}"><status status="{status}"/></test>')
    parts.append("</suite></robot>")
    (output_dir / "output.xml").write_text("\n".join(parts), encoding="utf-8")


def _mk_run(
    db_session: Session, repo: Repository, owner: User, *,
    output_dir: Path | None,
    status: str = RunStatus.PASSED,
    created_at: datetime | None = None,
) -> ExecutionRun:
    run = ExecutionRun(
        repository_id=repo.id,
        target_path="tests",
        branch="main",
        status=status,
        output_dir=str(output_dir) if output_dir else None,
        triggered_by=owner.id,
    )
    if created_at is not None:
        run.created_at = created_at
    db_session.add(run)
    db_session.flush()
    db_session.refresh(run)
    return run


class TestHealRateEndpoint:
    def test_no_runs_returns_zero(self, client, db_session, admin_user, repo) -> None:
        resp = client.get(
            f"{ENDPOINT}?days=7&repository_id={repo.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_runs_in_window"] == 0
        assert body["total_heals"] == 0
        assert len(body["trend"]) == 7
        assert all(p["heals"] == 0 for p in body["trend"])

    def test_runs_without_heal_audit_count_but_contribute_nothing(
        self, client, db_session, admin_user, repo, tmp_path
    ) -> None:
        out = tmp_path / "no-heals"
        out.mkdir()
        _mk_run(db_session, repo, admin_user, output_dir=out)
        resp = client.get(
            f"{ENDPOINT}?repository_id={repo.id}",
            headers=auth_header(admin_user),
        )
        body = resp.json()
        assert body["total_runs_in_window"] == 1
        assert body["runs_with_heals"] == 0
        assert body["total_heals"] == 0

    def test_mixed_confirmed_and_suspect_aggregated(
        self, client, db_session, admin_user, repo, tmp_path
    ) -> None:
        out = tmp_path / "with-heals"
        _write_audit_and_output(
            out,
            records=[
                {"timestamp": "2026-04-24T09:00:00Z", "test_name": "GoodTest",
                 "keyword": "Click", "original_selector": "id=a",
                 "healed_selector": "[data-testid=a]", "confidence": 0.95,
                 "source": "sidecar"},
                {"timestamp": "2026-04-24T09:00:01Z", "test_name": "BadTest",
                 "keyword": "Click", "original_selector": "id=b",
                 "healed_selector": "text=b", "confidence": 0.7,
                 "source": "transposition"},
            ],
            test_outcomes={"GoodTest": "PASS", "BadTest": "FAIL"},
        )
        _mk_run(db_session, repo, admin_user, output_dir=out)
        resp = client.get(
            f"{ENDPOINT}?repository_id={repo.id}",
            headers=auth_header(admin_user),
        )
        body = resp.json()
        assert body["total_runs_in_window"] == 1
        assert body["runs_with_heals"] == 1
        assert body["total_heals"] == 2
        assert body["confirmed_heals"] == 1
        assert body["suspect_heals"] == 1

    def test_repository_filter_isolates(
        self, client, db_session, admin_user, repo, tmp_path
    ) -> None:
        # Create a second repo + a run there with heals — our filtered
        # call must not see it.
        other = Repository(
            name="sh6-other", git_url="https://github.com/x/z.git",
            default_branch="main", local_path="/tmp/sh6-other",
            created_by=admin_user.id,
        )
        db_session.add(other)
        db_session.flush()
        db_session.refresh(other)

        other_out = tmp_path / "other-heals"
        _write_audit_and_output(
            other_out,
            records=[{
                "timestamp": "2026-04-24T09:00:00Z", "test_name": "X",
                "keyword": "Click", "original_selector": "id=a",
                "healed_selector": "id=b", "confidence": 0.9,
                "source": "sidecar",
            }],
            test_outcomes={"X": "PASS"},
        )
        _mk_run(db_session, other, admin_user, output_dir=other_out)

        resp = client.get(
            f"{ENDPOINT}?repository_id={repo.id}",
            headers=auth_header(admin_user),
        )
        body = resp.json()
        # Our target repo has no runs → zero everything even though a
        # heal landed in the other repo.
        assert body["total_heals"] == 0
        assert body["runs_with_heals"] == 0

    def test_unauthenticated_blocked(self, client) -> None:
        assert client.get(ENDPOINT).status_code == 401
