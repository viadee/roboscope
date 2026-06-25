"""EXEC.4: repo tag discovery aggregates per-test [Tags] + suite-level tags."""

from src.explorer.service import list_all_tags

SUITE = """\
*** Settings ***
Force Tags    regression    nightly
Test Tags     smoke

*** Test Cases ***
Login Works
    [Tags]    smoke    auth
    Log    hi

Logout Works
    [Tags]    auth
    Log    bye
"""


def test_list_all_tags_aggregates_and_dedupes(tmp_path):
    (tmp_path / "suite.robot").write_text(SUITE)
    tags = list_all_tags(str(tmp_path))
    # per-test [Tags] + Force/Test tags, sorted + de-duplicated
    assert tags == ["auth", "nightly", "regression", "smoke"]


def test_list_all_tags_empty_repo(tmp_path):
    assert list_all_tags(str(tmp_path)) == []


def test_list_all_tags_ignores_non_robot(tmp_path):
    (tmp_path / "notes.txt").write_text("Force Tags    nope")
    assert list_all_tags(str(tmp_path)) == []
