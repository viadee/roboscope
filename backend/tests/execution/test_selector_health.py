"""Story SH-1 — selector-health diagnosis.

Sidecar-aware lookup of ranked alternative selector candidates when a
run fails on an "element not found" / "locator timeout".
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from src.auth.models import User
from src.auth.service import hash_password
from src.execution.models import RunStatus
from src.execution.router import _extract_failed_locators
from src.repos.models import Repository
from tests.conftest import auth_header


ENDPOINT = "/api/v1/runs/{}/selector-health"


@pytest.fixture
def repo_with_path(db_session: Session, admin_user: User, tmp_path: Path) -> Repository:
    repo = Repository(
        name="sh-1-repo",
        git_url="https://github.com/x/y.git",
        default_branch="main",
        local_path=str(tmp_path),
        created_by=admin_user.id,
    )
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)
    return repo


def _mk_run(
    db_session: Session, repo: Repository, owner: User, *,
    target_path: str = "tests/login.robot", status: str = RunStatus.FAILED,
    output_dir: str | None = None, error_message: str | None = None,
):
    from src.execution.models import ExecutionRun

    run = ExecutionRun(
        repository_id=repo.id,
        target_path=target_path,
        branch="main",
        status=status,
        output_dir=output_dir,
        error_message=error_message,
        triggered_by=owner.id,
    )
    db_session.add(run)
    db_session.flush()
    db_session.refresh(run)
    return run


def _write_sidecar(robot_path: Path, *, active_locator: str, alts: list[dict]) -> None:
    robot_path.write_text("*** Settings ***\nLibrary    Browser\n", encoding="utf-8")
    sidecar = robot_path.with_suffix(".rbs.json")
    sidecar.write_text(
        json.dumps({
            "schema_version": 1,
            "transport": "web_playwright",
            "session_id": "sh-1",
            "name": None,
            "commands": [{
                "index": 0,
                "keyword": "Click",
                "args": {},
                "active_candidate_index": 0,
                "selector_candidates": [
                    {
                        "strategy": "testid",
                        "value": active_locator,
                        "quality_score": 0.95,
                        "verified_unique": True,
                    },
                    *alts,
                ],
            }],
        }),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Pure-function parser
# ---------------------------------------------------------------------------


class TestLocatorExtractor:
    def test_matches_robot_framework_element_not_found(self) -> None:
        txt = "FAIL: Element 'id=submit' not found after 5 seconds."
        assert _extract_failed_locators(txt) == ["id=submit"]

    def test_matches_browser_library_locator_timeout(self) -> None:
        txt = "BrowserError: locator('[data-testid=go]').click: Timeout 5000ms exceeded."
        assert _extract_failed_locators(txt) == ["[data-testid=go]"]

    def test_matches_playwright_waiting_for_selector(self) -> None:
        txt = 'TimeoutError: waiting for selector "text=Submit" failed'
        assert _extract_failed_locators(txt) == ["text=Submit"]

    def test_deduplicates_repeated_locators(self) -> None:
        txt = (
            "Element 'id=x' not found\n"
            'waiting for selector "id=x" failed\n'
        )
        assert _extract_failed_locators(txt) == ["id=x"]

    def test_returns_empty_on_no_match(self) -> None:
        assert _extract_failed_locators("all good, nothing failed") == []


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


class TestEndpoint:
    def test_404_on_missing_run(self, client, admin_user) -> None:
        resp = client.get(ENDPOINT.format(99999), headers=auth_header(admin_user))
        assert resp.status_code == 404

    def test_no_sidecar_when_rbs_file_missing(
        self, client, runner_user, repo_with_path, db_session, tmp_path
    ) -> None:
        (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
        (tmp_path / "tests/login.robot").write_text("xxx", encoding="utf-8")
        run = _mk_run(db_session, repo_with_path, runner_user)
        resp = client.get(ENDPOINT.format(run.id), headers=auth_header(runner_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_sidecar"] is False
        assert body["failed_locators"] == []

    def test_surfaces_alternatives_from_sidecar(
        self, client, runner_user, repo_with_path, db_session, tmp_path
    ) -> None:
        # Create the .robot + sidecar in the fake repo.
        (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
        robot_path = tmp_path / "tests/login.robot"
        _write_sidecar(
            robot_path,
            active_locator="id=submit",
            alts=[
                {"strategy": "aria", "value": "role=button[name='Submit']",
                 "quality_score": 0.8, "verified_unique": True},
                {"strategy": "text", "value": "text=Submit",
                 "quality_score": 0.6, "verified_unique": True},
            ],
        )

        # Simulate a failed run that logged the id=submit miss.
        output_dir = tmp_path / "run_out"
        output_dir.mkdir()
        (output_dir / "stderr.log").write_text(
            "Element 'id=submit' not found after 5 seconds.\n",
            encoding="utf-8",
        )

        run = _mk_run(
            db_session, repo_with_path, runner_user,
            output_dir=str(output_dir),
        )
        resp = client.get(ENDPOINT.format(run.id), headers=auth_header(runner_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_sidecar"] is True
        assert body["sidecar_path"] == "tests/login.rbs.json"
        assert len(body["failed_locators"]) == 1
        hit = body["failed_locators"][0]
        assert hit["raw_locator"] == "id=submit"
        # The active candidate is excluded; remaining sorted by quality desc.
        assert [c["strategy"] for c in hit["candidates"]] == ["aria", "text"]
        assert hit["candidates"][0]["value"] == "role=button[name='Submit']"

    def test_reports_failed_locator_without_candidates_when_sidecar_lacks_match(
        self, client, runner_user, repo_with_path, db_session, tmp_path
    ) -> None:
        (tmp_path / "tests").mkdir(parents=True, exist_ok=True)
        robot_path = tmp_path / "tests/login.robot"
        _write_sidecar(
            robot_path, active_locator="id=somethingelse", alts=[],
        )

        run = _mk_run(
            db_session, repo_with_path, runner_user,
            error_message="Element 'id=submit' not found after 5 seconds",
        )
        resp = client.get(ENDPOINT.format(run.id), headers=auth_header(runner_user))
        assert resp.status_code == 200
        body = resp.json()
        assert body["has_sidecar"] is True
        # id=submit is not in the sidecar → surfaced but without alternatives.
        assert body["failed_locators"][0]["raw_locator"] == "id=submit"
        assert body["failed_locators"][0]["candidates"] == []
