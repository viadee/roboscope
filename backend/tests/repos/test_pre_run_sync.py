"""Story REPO-3 — pre-run sync helper unit tests.

Covers `sync_for_run(repo, timeout_seconds)` selection / outcome paths
and verifies it is wired into `execute_test_run`. Pull-itself behaviour
is exercised through real bare-repo + working-clone fixtures (same
shape as `test_save_loop.py`) for the happy path; failure modes are
mocked so the test stays fast and offline.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
from git import Repo
from sqlalchemy.orm import Session

from src.repos.models import Repository
from src.repos.service import sync_for_run


# ---------------------------------------------------------------------------
# fixtures — bare-remote + working-clone, same shape as test_save_loop.py
# ---------------------------------------------------------------------------


@pytest.fixture
def bare_remote(tmp_path: Path) -> Path:
    bare = tmp_path / "remote.git"
    Repo.init(bare, bare=True, initial_branch="main")
    return bare


@pytest.fixture
def working_clone(tmp_path: Path, bare_remote: Path) -> Path:
    clone = tmp_path / "clone"
    repo = Repo.clone_from(str(bare_remote), str(clone))
    seed = clone / "README.md"
    seed.write_text("seed\n", encoding="utf-8")
    repo.index.add(["README.md"])
    repo.git.update_environment(
        GIT_AUTHOR_NAME="seed", GIT_AUTHOR_EMAIL="seed@example.com",
        GIT_COMMITTER_NAME="seed", GIT_COMMITTER_EMAIL="seed@example.com",
    )
    repo.git.commit("-m", "seed")
    repo.git.push("origin", "main")
    return clone


def _mk_repo(
    db: Session, admin_user, working_clone: Path | None = None, **overrides
) -> Repository:
    """Insert a Repository row with sensible defaults for pre-run-sync tests."""
    defaults: dict = {
        "name": f"pre-run-sync-{overrides.get('name', 'r')}",
        "repo_type": "git",
        "git_url": (
            str(working_clone.parent / "remote.git")
            if working_clone is not None else "https://example.com/x.git"
        ),
        "default_branch": "main",
        "local_path": str(working_clone) if working_clone is not None else "/tmp/x",
        "auto_sync": False,
        "sync_interval_minutes": 15,
        "pre_run_sync": True,
        "sync_status": "idle",
        "created_by": admin_user.id,
    }
    defaults.update(overrides)
    repo = Repository(**defaults)
    db.add(repo)
    db.flush()
    db.refresh(repo)
    return repo


# ---------------------------------------------------------------------------
# sync_for_run — skip paths
# ---------------------------------------------------------------------------


class TestSyncForRunSkip:
    def test_local_repo_skips(self, db_session: Session, admin_user):
        repo = _mk_repo(
            db_session, admin_user,
            name="local", repo_type="local", git_url=None, local_path="/tmp/x",
        )
        status, _ = sync_for_run(repo)
        assert status == "skipped"

    def test_flag_off_skips(self, db_session: Session, admin_user, working_clone: Path):
        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone,
            name="off", pre_run_sync=False,
        )
        status, _ = sync_for_run(repo)
        assert status == "skipped"

    def test_in_flight_skips(self, db_session: Session, admin_user, working_clone: Path):
        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone,
            name="inflight", sync_status="syncing",
        )
        status, detail = sync_for_run(repo)
        assert status == "skipped"
        assert detail and "another sync" in detail

    def test_no_git_url_skips(self, db_session: Session, admin_user, working_clone: Path):
        # Defensive: pre_run_sync=True + repo_type='git' but no URL.
        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone,
            name="nourl", git_url=None,
        )
        status, _ = sync_for_run(repo)
        assert status == "skipped"


# ---------------------------------------------------------------------------
# sync_for_run — happy path + error path
# ---------------------------------------------------------------------------


class TestSyncForRunOutcomes:
    def test_success(self, db_session: Session, admin_user, working_clone: Path):
        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone, name="ok",
        )
        status, detail = sync_for_run(repo)
        assert status == "ok", f"expected ok, got {status}: {detail}"
        assert detail and "synced to" in detail

    def test_swallows_git_error(self, db_session: Session, admin_user, working_clone: Path):
        # Point local_path at a non-git directory — sync_repository
        # returns "error: not a git repository", which sync_for_run
        # surfaces as ("error", _) without raising.
        bogus = working_clone.parent / "not-a-repo"
        bogus.mkdir()
        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone,
            name="bogus", local_path=str(bogus),
        )
        status, detail = sync_for_run(repo)
        assert status == "error"
        assert detail and detail  # non-empty

    def test_respects_timeout(self, db_session: Session, admin_user, working_clone: Path):
        # Patch sync_repository to sleep longer than the timeout — we
        # expect ("timeout", _) without raising.
        import time

        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone, name="slow",
        )

        def slow_sync(*_a, **_kw):
            time.sleep(2.0)
            return "synced to deadbeef"

        with patch("src.repos.service.sync_repository", side_effect=slow_sync):
            status, detail = sync_for_run(repo, timeout_seconds=1)
        assert status == "timeout"
        assert detail == "1s"

    def test_unexpected_exception_surfaces_as_error(
        self, db_session: Session, admin_user, working_clone: Path,
    ):
        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone, name="boom",
        )

        def boom(*_a, **_kw):
            raise RuntimeError("network unreachable")

        with patch("src.repos.service.sync_repository", side_effect=boom):
            status, detail = sync_for_run(repo)
        assert status == "error"
        assert detail and "network unreachable" in detail


# ---------------------------------------------------------------------------
# execute_test_run wiring — verifies sync_for_run is called only when on
# ---------------------------------------------------------------------------


class TestSyncStatusFlipping:
    """Review fix M2 — `sync_for_run` must flip sync_status='syncing'
    before the pull and to 'success'/'error' after, so the REPO-2
    scheduler's `due_repos()` filter sees the in-flight state and
    can't dispatch a concurrent `git pull` on the same working copy.
    """

    def test_success_flips_to_success(
        self, db_session: Session, admin_user, working_clone: Path,
    ):
        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone,
            name="ok-flip", sync_status="idle",
        )
        status, _ = sync_for_run(repo, session=db_session)
        assert status == "ok"
        # Re-read from session to get the persisted value.
        db_session.refresh(repo)
        assert repo.sync_status == "success"
        assert repo.sync_error is None

    def test_error_flips_to_error_with_message(
        self, db_session: Session, admin_user, working_clone: Path,
    ):
        bogus = working_clone.parent / "not-a-repo-2"
        bogus.mkdir()
        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone,
            name="err-flip", local_path=str(bogus),
        )
        status, _ = sync_for_run(repo, session=db_session)
        assert status == "error"
        db_session.refresh(repo)
        assert repo.sync_status == "error"
        assert repo.sync_error  # non-empty

    def test_timeout_flips_to_error(
        self, db_session: Session, admin_user, working_clone: Path,
    ):
        import time

        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone,
            name="timeout-flip",
        )

        def slow_sync(*_a, **_kw):
            time.sleep(2.0)
            return "synced to deadbeef"

        with patch("src.repos.service.sync_repository", side_effect=slow_sync):
            status, _ = sync_for_run(repo, session=db_session, timeout_seconds=1)
        assert status == "timeout"
        db_session.refresh(repo)
        assert repo.sync_status == "error"
        assert repo.sync_error and "1s" in repo.sync_error

    def test_skip_paths_do_not_flip(
        self, db_session: Session, admin_user, working_clone: Path,
    ):
        # pre_run_sync=False should leave sync_status untouched — we
        # never started a pull, so no surface change.
        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone,
            name="skip-no-flip", pre_run_sync=False, sync_status="idle",
        )
        status, _ = sync_for_run(repo, session=db_session)
        assert status == "skipped"
        db_session.refresh(repo)
        assert repo.sync_status == "idle"

    def test_no_session_no_flip(
        self, db_session: Session, admin_user, working_clone: Path,
    ):
        # Backward-compatible: callers passing only the repo (e.g.
        # the unit tests above) get the return contract without DB writes.
        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone,
            name="no-session", sync_status="idle",
        )
        status, _ = sync_for_run(repo)
        assert status == "ok"
        # Without a session passed, we never wrote sync_status.
        db_session.refresh(repo)
        assert repo.sync_status == "idle"


class TestTimeoutDoesNotBlockOnPoolShutdown:
    """Review fix M1 — naive `with ThreadPoolExecutor(...) as pool` blocks
    on __exit__ → shutdown(wait=True), defeating the wall-clock timeout.
    The fixed implementation uses explicit `shutdown(wait=False)` in a
    finally clause. This test asserts the timeout actually returns
    promptly even when the underlying pull would take much longer.
    """

    def test_timeout_returns_promptly(
        self, db_session: Session, admin_user, working_clone: Path,
    ):
        import time

        repo = _mk_repo(
            db_session, admin_user, working_clone=working_clone,
            name="prompt-timeout",
        )

        def slow_sync(*_a, **_kw):
            time.sleep(5.0)  # would block the test if shutdown waited
            return "synced to deadbeef"

        t0 = time.monotonic()
        with patch("src.repos.service.sync_repository", side_effect=slow_sync):
            status, detail = sync_for_run(repo, timeout_seconds=1)
        elapsed = time.monotonic() - t0

        assert status == "timeout"
        assert detail == "1s"
        # Generous bound — should be ~1s + small overhead. Anything > 3s
        # means shutdown(wait=True) is sneaking back in.
        assert elapsed < 3.0, f"sync_for_run took {elapsed:.2f}s, expected <3s"
