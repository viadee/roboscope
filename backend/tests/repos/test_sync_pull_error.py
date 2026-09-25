"""Issue #36: a refused `git pull` must surface as a sync error, not success."""

from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from git import Repo

from src.repos.tasks import sync_repo
from tests.repos.test_save_loop import (  # noqa: F401  (fixtures)
    bare_remote,
    editor_user,
    seed_repo_for_clone,
    working_clone,
)

_IDENT = dict(GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@example.com",
              GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@example.com")


def test_dirty_tree_conflict_reports_error(db_session, seed_repo_for_clone, working_clone: Path,
                                           bare_remote: Path, tmp_path: Path):
    # Someone else pushes a change to README.md …
    other = Repo.clone_from(str(bare_remote), str(tmp_path / "other"))
    other.git.update_environment(**_IDENT)
    (tmp_path / "other" / "README.md").write_text("upstream\n", encoding="utf-8")
    other.git.commit("-am", "upstream")
    other.git.push("origin", "main")
    # … while the in-app editor left an uncommitted edit on the same file.
    (working_clone / "README.md").write_text("local edit\n", encoding="utf-8")

    @contextmanager
    def reuse():
        yield db_session

    with patch("src.repos.tasks.get_sync_session", reuse):
        out = sync_repo(seed_repo_for_clone.id)

    db_session.refresh(seed_repo_for_clone)
    assert out["status"] == "error"
    assert seed_repo_for_clone.sync_status == "error"
    assert "overwritten" in (seed_repo_for_clone.sync_error or "")
    # The local edit is untouched.
    assert (working_clone / "README.md").read_text(encoding="utf-8") == "local edit\n"
