"""Story V14.5 — per-file diff preview (`GET /repos/{id}/diff?path=`)."""

from __future__ import annotations

from pathlib import Path

import pytest
from git import Repo

from src.repos.service import GitOperationError, get_file_diff
from tests.conftest import auth_header
from tests.repos.test_save_loop import (  # noqa: F401  (fixtures)
    bare_remote,
    editor_user,
    local_repo,
    runner_user,
    seed_repo_for_clone,
    working_clone,
)


class TestService:
    def test_modified(self, working_clone: Path):
        (working_clone / "README.md").write_text("seed\nnew line\n", encoding="utf-8")
        out = get_file_diff(str(working_clone), "README.md")
        assert out["status"] == "modified"
        assert "+new line" in out["diff"]
        assert out["truncated"] is False

    def test_staged_change_is_included(self, working_clone: Path):
        (working_clone / "README.md").write_text("staged\n", encoding="utf-8")
        Repo(working_clone).index.add(["README.md"])
        out = get_file_diff(str(working_clone), "README.md")
        assert "+staged" in out["diff"] and "-seed" in out["diff"]

    def test_untracked_is_all_added(self, working_clone: Path):
        (working_clone / "sub").mkdir()
        (working_clone / "sub" / "a.robot").write_text("one\ntwo\n", encoding="utf-8")
        out = get_file_diff(str(working_clone), "sub/a.robot")
        assert out["status"] == "untracked"
        assert "+one\n+two\n" in out["diff"]
        assert "--- /dev/null" in out["diff"]

    def test_deleted_is_all_removed(self, working_clone: Path):
        (working_clone / "README.md").unlink()
        out = get_file_diff(str(working_clone), "README.md")
        assert out["status"] == "deleted"
        assert "-seed" in out["diff"]

    def test_unchanged(self, working_clone: Path):
        out = get_file_diff(str(working_clone), "README.md")
        assert out["status"] == "unchanged" and out["diff"] == ""

    def test_large_file_truncated(self, working_clone: Path):
        (working_clone / "big.txt").write_text(("y" * 99 + "\n") * 3000, encoding="utf-8")
        out = get_file_diff(str(working_clone), "big.txt", max_bytes=1000)
        assert out["truncated"] is True
        assert len(out["diff"].encode()) <= 1000

    def test_large_tracked_diff_truncated(self, working_clone: Path):
        (working_clone / "README.md").write_text(("z" * 99 + "\n") * 3000, encoding="utf-8")
        out = get_file_diff(str(working_clone), "README.md", max_bytes=1000)
        assert out["truncated"] is True and out["status"] == "modified"

    def test_binary_untracked(self, working_clone: Path):
        (working_clone / "img.bin").write_bytes(b"\x89PNG\x00\x01\x02")
        out = get_file_diff(str(working_clone), "img.bin")
        assert out["status"] == "binary" and out["diff"] is None

    def test_binary_tracked(self, working_clone: Path):
        (working_clone / "img.bin").write_bytes(b"\x00\x01")
        repo = Repo(working_clone)
        repo.index.add(["img.bin"])
        repo.git.commit("-m", "bin")
        (working_clone / "img.bin").write_bytes(b"\x00\x02\x03")
        out = get_file_diff(str(working_clone), "img.bin")
        assert out["status"] == "binary" and out["diff"] is None

    @pytest.mark.parametrize(
        "bad", ["../etc/passwd", "/etc/passwd", "sub/../../x", "", ".", "sub"],
    )
    def test_traversal_rejected(self, working_clone: Path, bad: str):
        (working_clone / "sub").mkdir()
        with pytest.raises(GitOperationError) as ei:
            get_file_diff(str(working_clone), bad)
        assert ei.value.kind == "bad_path"

    def test_symlink_escape_rejected(self, working_clone: Path, tmp_path: Path):
        secret = tmp_path / "secret.txt"
        secret.write_text("secret\n", encoding="utf-8")
        (working_clone / "link.txt").symlink_to(secret)
        with pytest.raises(GitOperationError) as ei:
            get_file_diff(str(working_clone), "link.txt")
        assert ei.value.kind == "bad_path"

    def test_glob_is_literal(self, working_clone: Path):
        (working_clone / "README.md").write_text("changed\n", encoding="utf-8")
        out = get_file_diff(str(working_clone), "*.md")
        assert out["status"] == "unchanged" and out["diff"] == ""


class TestRouter:
    def test_diff_happy_path(self, client, runner_user, seed_repo_for_clone, working_clone):
        (working_clone / "README.md").write_text("seed\nadded\n", encoding="utf-8")
        r = client.get(
            f"/api/v1/repos/{seed_repo_for_clone.id}/diff",
            params={"path": "README.md"},
            headers=auth_header(runner_user),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["path"] == "README.md"
        assert body["status"] == "modified"
        assert "+added" in body["diff"]
        assert body["truncated"] is False

    def test_traversal_returns_400(self, client, admin_user, seed_repo_for_clone):
        r = client.get(
            f"/api/v1/repos/{seed_repo_for_clone.id}/diff",
            params={"path": "../etc/passwd"},
            headers=auth_header(admin_user),
        )
        assert r.status_code == 400

    def test_local_repo_returns_409(self, client, admin_user, local_repo):
        r = client.get(
            f"/api/v1/repos/{local_repo.id}/diff",
            params={"path": "a.robot"},
            headers=auth_header(admin_user),
        )
        assert r.status_code == 409

    def test_unknown_repo_404(self, client, admin_user):
        r = client.get(
            "/api/v1/repos/99999/diff", params={"path": "a"}, headers=auth_header(admin_user),
        )
        assert r.status_code == 404

    def test_requires_auth(self, client, seed_repo_for_clone):
        r = client.get(f"/api/v1/repos/{seed_repo_for_clone.id}/diff", params={"path": "a"})
        assert r.status_code == 401
