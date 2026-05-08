"""Story TEST-4 — `/api/v1/ai/{generate,reverse,analyze,status,accept}`
endpoint coverage.

Continues TEST-3 (provider CRUD). The five endpoints here are the
"do AI work" surface — they take user input, validate path /
report / spec preconditions, dispatch a background task via
`task_executor`, and return the seed job row. The dispatch itself
goes through `dispatch_task`, which we mock so tests don't actually
spin up the LLM client.

Coverage gaps before this story:
- All 5 endpoints had zero router-level tests.
- The drift-check 409 in /generate was never asserted.
- /accept's four 400 reasons (not completed, no preview, no target,
  unknown repo) were uncovered.
- /status didn't test the 404-on-unknown-id branch.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.ai.models import AiJob, AiProvider
from src.ai.schemas import AiProviderCreate
from src.ai.service import create_provider
from tests.conftest import auth_header


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def provider(db_session: Session, admin_user) -> AiProvider:
    """A default provider so the endpoints have something to resolve."""
    return create_provider(
        db_session,
        AiProviderCreate(
            name="test-provider",
            provider_type="openai",
            model_name="gpt-4o-mini",
            api_key="sk-test",
            is_default=True,
        ),
        admin_user.id,
    )


@pytest.fixture
def repo_with_files(db_session, admin_user, tmp_path):
    """Insert a Repository row pointing at a tmp dir with seeded files."""
    from src.repos.models import Repository

    local = tmp_path / "repo"
    local.mkdir()
    spec = local / "tests" / "demo.roboscope"
    spec.parent.mkdir(parents=True)
    spec.write_text(
        "metadata:\n  target_file: tests/demo.robot\ntests: []\n",
        encoding="utf-8",
    )
    robot = local / "tests" / "demo.robot"
    robot.write_text("*** Test Cases ***\nDemo\n    Log    hi\n", encoding="utf-8")

    repo = Repository(
        name="ai-test-repo",
        repo_type="git",
        git_url="https://example.com/x.git",
        local_path=str(local),
        default_branch="main",
        created_by=admin_user.id,
    )
    db_session.add(repo)
    db_session.flush()
    db_session.refresh(repo)
    return repo


@pytest.fixture
def report_with_failures(db_session, admin_user, tmp_path):
    """A Report row that already has failed_tests > 0."""
    from src.repos.models import Repository
    from src.execution.models import ExecutionRun
    from src.reports.models import Report

    local = tmp_path / "report-repo"
    local.mkdir()
    repo = Repository(
        name="ai-report-repo",
        repo_type="git",
        git_url="https://example.com/r.git",
        local_path=str(local),
        default_branch="main",
        created_by=admin_user.id,
    )
    db_session.add(repo)
    db_session.flush()
    run = ExecutionRun(
        repository_id=repo.id,
        target_path="t.robot",
        branch="main",
        status="failed",
        triggered_by=admin_user.id,
    )
    db_session.add(run)
    db_session.flush()
    report = Report(
        execution_run_id=run.id,
        output_xml_path=str(local / "out" / "output.xml"),
        total_tests=3,
        passed_tests=2,
        failed_tests=1,
        skipped_tests=0,
        total_duration_seconds=1.5,
    )
    db_session.add(report)
    db_session.flush()
    db_session.refresh(report)
    return report


def _mock_dispatch():
    """`dispatch_task` is imported at module load into `src.ai.router`,
    so we patch the local binding (not the source module) — otherwise
    the router still calls the original.
    """
    mock = MagicMock(return_value=MagicMock(id="task-id"))
    return patch("src.ai.router.dispatch_task", mock), mock


# ---------------------------------------------------------------------------
# POST /generate
# ---------------------------------------------------------------------------


class TestGenerate:
    def test_happy_path_dispatches_job(
        self, client, admin_user, repo_with_files, provider,
    ):
        patcher, mock = _mock_dispatch()
        with patcher:
            resp = client.post(
                "/api/v1/ai/generate",
                headers=auth_header(admin_user),
                json={
                    "repository_id": repo_with_files.id,
                    "spec_path": "tests/demo.roboscope",
                    "provider_id": provider.id,
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_type"] == "generate"
        assert body["status"] == "pending"
        # The dispatch was called with run_generate + the new job id.
        mock.assert_called_once()
        called_fn = mock.call_args.args[0]
        assert called_fn.__name__ == "run_generate"

    def test_missing_spec_404(
        self, client, admin_user, repo_with_files, provider,
    ):
        resp = client.post(
            "/api/v1/ai/generate",
            headers=auth_header(admin_user),
            json={
                "repository_id": repo_with_files.id,
                "spec_path": "tests/does-not-exist.roboscope",
                "provider_id": provider.id,
            },
        )
        assert resp.status_code == 404

    def test_unknown_repo_404(self, client, admin_user, provider):
        resp = client.post(
            "/api/v1/ai/generate",
            headers=auth_header(admin_user),
            json={
                "repository_id": 99999,
                "spec_path": "any.roboscope",
                "provider_id": provider.id,
            },
        )
        assert resp.status_code == 404

    def test_runner_user_forbidden(
        self, client, runner_user, repo_with_files, provider,
    ):
        resp = client.post(
            "/api/v1/ai/generate",
            headers=auth_header(runner_user),
            json={
                "repository_id": repo_with_files.id,
                "spec_path": "tests/demo.roboscope",
                "provider_id": provider.id,
            },
        )
        assert resp.status_code == 403

    def test_drift_409_when_target_modified(
        self, client, admin_user, repo_with_files, provider,
    ):
        """If `metadata.generation_hash` exists in the spec but the
        on-disk .robot file's hash differs, the endpoint refuses with
        409 unless `force=true` is passed.
        """
        # Seed a spec with a stale generation_hash that doesn't match
        # the current .robot file.
        spec = Path(repo_with_files.local_path) / "tests" / "demo.roboscope"
        spec.write_text(
            "metadata:\n"
            "  target_file: tests/demo.robot\n"
            "  generation_hash: 'deadbeef-stale-hash'\n"
            "tests: []\n",
            encoding="utf-8",
        )
        resp = client.post(
            "/api/v1/ai/generate",
            headers=auth_header(admin_user),
            json={
                "repository_id": repo_with_files.id,
                "spec_path": "tests/demo.roboscope",
                "provider_id": provider.id,
            },
        )
        assert resp.status_code == 409

    def test_drift_force_true_bypasses(
        self, client, admin_user, repo_with_files, provider,
    ):
        spec = Path(repo_with_files.local_path) / "tests" / "demo.roboscope"
        spec.write_text(
            "metadata:\n"
            "  target_file: tests/demo.robot\n"
            "  generation_hash: 'deadbeef-stale-hash'\n"
            "tests: []\n",
            encoding="utf-8",
        )
        patcher, _mock = _mock_dispatch()
        with patcher:
            resp = client.post(
                "/api/v1/ai/generate",
                headers=auth_header(admin_user),
                json={
                    "repository_id": repo_with_files.id,
                    "spec_path": "tests/demo.roboscope",
                    "provider_id": provider.id,
                    "force": True,
                },
            )
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# POST /reverse
# ---------------------------------------------------------------------------


class TestReverse:
    def test_happy_path_auto_derives_output(
        self, client, admin_user, repo_with_files, provider,
    ):
        patcher, mock = _mock_dispatch()
        with patcher:
            resp = client.post(
                "/api/v1/ai/reverse",
                headers=auth_header(admin_user),
                json={
                    "repository_id": repo_with_files.id,
                    "robot_path": "tests/demo.robot",
                    "provider_id": provider.id,
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_type"] == "reverse"
        assert body["target_path"] == "tests/demo.roboscope"
        called_fn = mock.call_args.args[0]
        assert called_fn.__name__ == "run_reverse"

    def test_explicit_output_path(
        self, client, admin_user, repo_with_files, provider,
    ):
        patcher, _mock = _mock_dispatch()
        with patcher:
            resp = client.post(
                "/api/v1/ai/reverse",
                headers=auth_header(admin_user),
                json={
                    "repository_id": repo_with_files.id,
                    "robot_path": "tests/demo.robot",
                    "provider_id": provider.id,
                    "output_path": "specs/custom.roboscope",
                },
            )
        assert resp.status_code == 200
        assert resp.json()["target_path"] == "specs/custom.roboscope"

    def test_missing_robot_404(
        self, client, admin_user, repo_with_files, provider,
    ):
        resp = client.post(
            "/api/v1/ai/reverse",
            headers=auth_header(admin_user),
            json={
                "repository_id": repo_with_files.id,
                "robot_path": "tests/missing.robot",
                "provider_id": provider.id,
            },
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /analyze
# ---------------------------------------------------------------------------


class TestAnalyze:
    def test_happy_path(self, client, admin_user, report_with_failures, provider):
        patcher, mock = _mock_dispatch()
        with patcher:
            resp = client.post(
                "/api/v1/ai/analyze",
                headers=auth_header(admin_user),
                json={
                    "report_id": report_with_failures.id,
                    "provider_id": provider.id,
                },
            )
        assert resp.status_code == 200
        body = resp.json()
        assert body["job_type"] == "analyze"
        called_fn = mock.call_args.args[0]
        assert called_fn.__name__ == "run_analyze"

    def test_unknown_report_404(self, client, admin_user, provider):
        resp = client.post(
            "/api/v1/ai/analyze",
            headers=auth_header(admin_user),
            json={"report_id": 99999, "provider_id": provider.id},
        )
        assert resp.status_code == 404

    def test_report_with_no_failures_400(
        self, client, admin_user, db_session, provider,
    ):
        # Build a clean report (failed_tests=0).
        from src.repos.models import Repository
        from src.execution.models import ExecutionRun
        from src.reports.models import Report

        repo = Repository(
            name="clean-repo", repo_type="git",
            git_url="https://example.com/c.git",
            local_path="/tmp/clean", default_branch="main",
            created_by=admin_user.id,
        )
        db_session.add(repo)
        db_session.flush()
        run = ExecutionRun(
            repository_id=repo.id, target_path="t",
            branch="main", status="passed", triggered_by=admin_user.id,
        )
        db_session.add(run)
        db_session.flush()
        clean_report = Report(
            execution_run_id=run.id,
            output_xml_path="/tmp/clean/out.xml",
            total_tests=2, passed_tests=2, failed_tests=0,
            skipped_tests=0, total_duration_seconds=0.5,
        )
        db_session.add(clean_report)
        db_session.flush()

        resp = client.post(
            "/api/v1/ai/analyze",
            headers=auth_header(admin_user),
            json={
                "report_id": clean_report.id,
                "provider_id": provider.id,
            },
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# GET /status/{job_id}
# ---------------------------------------------------------------------------


class TestJobStatus:
    def test_returns_pending_job(
        self, client, admin_user, repo_with_files, provider, db_session,
    ):
        from src.ai.service import create_job

        job = create_job(
            db_session, "generate", repo_with_files.id, provider.id,
            "tests/demo.roboscope", "tests/demo.robot", admin_user.id,
        )
        resp = client.get(
            f"/api/v1/ai/status/{job.id}",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "pending"

    def test_404_unknown(self, client, admin_user):
        resp = client.get(
            "/api/v1/ai/status/99999",
            headers=auth_header(admin_user),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /accept
# ---------------------------------------------------------------------------


class TestAccept:
    def _seed_completed_job(
        self, db, admin_user, repo, provider, **overrides,
    ):
        defaults = dict(
            job_type="generate", status="completed", repository_id=repo.id,
            provider_id=provider.id, spec_path="tests/demo.roboscope",
            target_path="tests/generated.robot",
            triggered_by=admin_user.id,
            result_preview="*** Test Cases ***\nGenerated\n    Log    ok\n",
        )
        defaults.update(overrides)
        job = AiJob(**defaults)
        db.add(job)
        db.flush()
        db.refresh(job)
        return job

    def test_accept_writes_file(
        self, client, admin_user, db_session, repo_with_files, provider,
    ):
        job = self._seed_completed_job(
            db_session, admin_user, repo_with_files, provider,
        )
        resp = client.post(
            "/api/v1/ai/accept",
            headers=auth_header(admin_user),
            json={"job_id": job.id},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "written"
        assert body["target_path"] == "tests/generated.robot"
        # File actually landed on disk.
        out = Path(repo_with_files.local_path) / "tests" / "generated.robot"
        assert out.exists()
        assert out.read_text(encoding="utf-8").startswith("*** Test Cases ***")

    def test_accept_unknown_job_404(self, client, admin_user):
        resp = client.post(
            "/api/v1/ai/accept",
            headers=auth_header(admin_user),
            json={"job_id": 99999},
        )
        assert resp.status_code == 404

    def test_accept_pending_job_400(
        self, client, admin_user, db_session, repo_with_files, provider,
    ):
        job = self._seed_completed_job(
            db_session, admin_user, repo_with_files, provider, status="pending",
        )
        resp = client.post(
            "/api/v1/ai/accept",
            headers=auth_header(admin_user),
            json={"job_id": job.id},
        )
        assert resp.status_code == 400
        assert "not completed" in resp.json()["detail"].lower()

    def test_accept_no_preview_400(
        self, client, admin_user, db_session, repo_with_files, provider,
    ):
        job = self._seed_completed_job(
            db_session, admin_user, repo_with_files, provider, result_preview=None,
        )
        resp = client.post(
            "/api/v1/ai/accept",
            headers=auth_header(admin_user),
            json={"job_id": job.id},
        )
        assert resp.status_code == 400
        assert "no result" in resp.json()["detail"].lower()

    def test_accept_no_target_400(
        self, client, admin_user, db_session, repo_with_files, provider,
    ):
        job = self._seed_completed_job(
            db_session, admin_user, repo_with_files, provider, target_path=None,
        )
        resp = client.post(
            "/api/v1/ai/accept",
            headers=auth_header(admin_user),
            json={"job_id": job.id},
        )
        assert resp.status_code == 400
        assert "no target path" in resp.json()["detail"].lower()

    def test_accept_runner_user_forbidden(
        self, client, runner_user, admin_user, db_session, repo_with_files, provider,
    ):
        job = self._seed_completed_job(
            db_session, admin_user, repo_with_files, provider,
        )
        resp = client.post(
            "/api/v1/ai/accept",
            headers=auth_header(runner_user),
            json={"job_id": job.id},
        )
        assert resp.status_code == 403
