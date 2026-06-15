"""Regression tests for the AI-subsystem QA-audit fixes (demo-readiness Pass 9).

  - C1: write_generated_file must refuse path traversal (a user-authored spec
        target_file like ../../../x must not escape the repo).
  - C2: _strip_code_fences must tolerate a prose preamble/epilogue and not
        corrupt the generated .robot.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.ai.service import write_generated_file
from src.ai.tasks import _strip_code_fences

# ----- C1: path-traversal containment -----


def test_write_generated_file_writes_within_repo(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    digest = write_generated_file(repo, "sub/dir/test.robot", "content")
    assert (repo / "sub" / "dir" / "test.robot").read_text() == "content"
    assert len(digest) == 64


@pytest.mark.parametrize(
    "evil",
    [
        "../../../escaped.robot",
        "../sibling.robot",
        "/tmp/abs_escape.robot",
        "sub/../../escaped.robot",
    ],
)
def test_write_generated_file_rejects_traversal(tmp_path: Path, evil: str) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError, match="outside the repository"):
        write_generated_file(repo, evil, "PWNED")
    # nothing was written outside the repo
    assert not (tmp_path / "escaped.robot").exists()
    assert not (tmp_path / "sibling.robot").exists()
    assert not Path("/tmp/abs_escape.robot").exists()


# ----- C2: code-fence stripping tolerates prose -----


@pytest.mark.parametrize(
    "raw,expected",
    [
        # plain fenced block
        ("```robot\n*** Test Cases ***\nFoo\n```", "*** Test Cases ***\nFoo"),
        # prose PREAMBLE before the fence (the bug that corrupted output)
        ("Here is your file:\n```robot\n*** Test Cases ***\nFoo\n```",
         "*** Test Cases ***\nFoo"),
        # prose EPILOGUE after the closing fence
        ("```\nFoo\nBar\n```\nHope this helps!", "Foo\nBar"),
        # both
        ("Sure!\n```python\nX\n```\nDone.", "X"),
        # no fences at all → unchanged (trimmed)
        ("*** Test Cases ***\nNoFence", "*** Test Cases ***\nNoFence"),
        # unbalanced (opening only) → drop preamble + fence line
        ("Here:\n```robot\nA\nB", "A\nB"),
    ],
)
def test_strip_code_fences(raw: str, expected: str) -> None:
    assert _strip_code_fences(raw) == expected


def test_strip_code_fences_no_dangling_fence_in_output() -> None:
    """The corruption signature: a leftover ``` in the accepted .robot."""
    out = _strip_code_fences("Here is your file:\n```robot\n*** Settings ***\n```")
    assert "```" not in out


# ----- H3: rotated SECRET_KEY → clear decrypt error -----


def test_decrypt_with_rotated_secret_key_raises_clear_error(monkeypatch) -> None:
    from src.ai import encryption
    from src.ai.encryption import ApiKeyDecryptError, decrypt_api_key, encrypt_api_key

    monkeypatch.setattr(encryption.settings, "SECRET_KEY", "secret-key-AAAAAAAAAAAA")
    ciphertext = encrypt_api_key("sk-provider-secret")

    monkeypatch.setattr(encryption.settings, "SECRET_KEY", "secret-key-BBBBBBBBBBBB")
    with pytest.raises(ApiKeyDecryptError, match="SECRET_KEY"):
        decrypt_api_key(ciphertext)
