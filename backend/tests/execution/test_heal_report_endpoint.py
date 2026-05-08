"""Story SH-2 — /runs/{id}/heal-report endpoint tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.auth.models import User
from src.execution.models import ExecutionRun, RunStatus
from src.repos.models import Repository
from tests.conftest import auth_header


ENDPOINT = "/api/v1/runs/{}/heal-report"


@pytest.fixture
def repo(db_session: Session, admin_user: User) -> Repository:
    r = Repository(
        name="heal-endpoint-repo",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path="/tmp/heal-repo",
        created_by=admin_user.id,
    )
    db_session.add(r)
    db_session.flush()
    db_session.refresh(r)
    return r


def _mk_run(
    db_session: Session, repo: Repository, owner: User, *, output_dir: Path | None,
    status: str = RunStatus.FAILED,
):
    run = ExecutionRun(
        repository_id=repo.id,
        target_path="tests",
        branch="main",
        status=status,
        output_dir=str(output_dir) if output_dir else None,
        triggered_by=owner.id,
    )
    db_session.add(run)
    db_session.flush()
    db_session.refresh(run)
    return run


def _write_audit(output_dir: Path, records: list[dict]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "heal_audit.jsonl").write_text(
        "\n".join(json.dumps(r) for r in records), encoding="utf-8",
    )


def _write_output_xml(output_dir: Path, tests: dict[str, str]) -> None:
    parts = ['<?xml version="1.0" encoding="UTF-8"?>', "<robot>", "<suite>"]
    for name, status in tests.items():
        parts.append(f'<test name="{name}"><status status="{status}"/></test>')
    parts.append("</suite></robot>")
    (output_dir / "output.xml").write_text("\n".join(parts), encoding="utf-8")


class TestHealReportEndpoint:
    def test_404_on_missing_run(self, client, admin_user) -> None:
        resp = client.get(ENDPOINT.format(99999), headers=auth_header(admin_user))
        assert resp.status_code == 404

    def test_run_without_output_dir_returns_zero(
        self, client, db_session, repo, admin_user
    ) -> None:
        run = _mk_run(db_session, repo, admin_user, output_dir=None)
        resp = client.get(ENDPOINT.format(run.id), headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_heals"] == 0
        assert body["entries"] == []

    def test_run_without_audit_file_returns_zero(
        self, client, db_session, repo, admin_user, tmp_path
    ) -> None:
        run = _mk_run(db_session, repo, admin_user, output_dir=tmp_path)
        resp = client.get(ENDPOINT.format(run.id), headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_heals"] == 0

    def test_classifies_confirmed_and_suspect_correctly(
        self, client, db_session, repo, admin_user, tmp_path
    ) -> None:
        _write_audit(tmp_path, [
            {
                "timestamp": "2026-04-24T10:00:00Z",
                "test_name": "Happy Test",
                "keyword": "Click",
                "original_selector": "id=submit",
                "healed_selector": "[data-testid=submit]",
                "confidence": 0.95,
                "source": "sidecar",
            },
            {
                "timestamp": "2026-04-24T10:00:10Z",
                "test_name": "Broken Test",
                "keyword": "Click",
                "original_selector": "id=next",
                "healed_selector": "text=Next",
                "confidence": 0.7,
                "source": "transposition",
            },
        ])
        _write_output_xml(tmp_path, {
            "Happy Test": "PASS",
            "Broken Test": "FAIL",
        })

        run = _mk_run(db_session, repo, admin_user, output_dir=tmp_path)
        resp = client.get(ENDPOINT.format(run.id), headers=auth_header(admin_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["total_heals"] == 2
        assert body["confirmed"] == 1
        assert body["suspect"] == 1
        outcomes = sorted(e["outcome"] for e in body["entries"])
        assert outcomes == ["confirmed", "suspect"]

    def test_unauthenticated_blocked(self, client) -> None:
        resp = client.get(ENDPOINT.format(1))
        assert resp.status_code == 401
