"""Unit tests for the unified-diff applier used by the AI auto-fix flow."""

import pytest

from src.ai.patch_apply import PatchApplyError, apply_unified_diff

ORIGINAL = """\
*** Test Cases ***
Login Test
    Open Browser    ${URL}
    Input Text    id=user    ${USERNAME}
    Click    id=submit
"""


def test_applies_a_simple_replacement():
    diff = """\
--- a/tests/login.robot
+++ b/tests/login.robot
@@ -3,3 +3,3 @@ Login Test
     Open Browser    ${URL}
-    Input Text    id=user    ${USERNAME}
+    Input Text    [data-testid=user]    ${USERNAME}
     Click    id=submit
"""
    out = apply_unified_diff(ORIGINAL, diff)
    assert "[data-testid=user]" in out
    assert "Input Text    id=user    ${USERNAME}" not in out
    # Untouched lines survive and the trailing newline is preserved.
    assert out.startswith("*** Test Cases ***\n")
    assert out.endswith("\n")


def test_tolerates_wrong_line_numbers():
    # The @@ header points at line 99 but the context is what matters.
    diff = """\
@@ -99,1 +99,1 @@
-    Click    id=submit
+    Click    id=login-submit
"""
    out = apply_unified_diff(ORIGINAL, diff)
    assert "id=login-submit" in out
    assert "id=submit" not in out


def test_pure_insertion():
    diff = """\
@@ -5,0 +6,1 @@
+    Close Browser
"""
    out = apply_unified_diff(ORIGINAL, diff)
    assert "Close Browser" in out


def test_raises_when_context_missing():
    diff = """\
@@ -1,1 +1,1 @@
-    This line does not exist in the file
+    Replacement
"""
    with pytest.raises(PatchApplyError):
        apply_unified_diff(ORIGINAL, diff)


def test_raises_on_diff_without_hunks():
    with pytest.raises(PatchApplyError):
        apply_unified_diff(ORIGINAL, "--- a/x\n+++ b/x\n")


def test_disambiguates_duplicate_blocks_by_hint():
    src = "A\nDUP\nB\nDUP\nC\n"
    # Target the SECOND "DUP" (around line 4).
    diff = """\
@@ -4,1 +4,1 @@
-DUP
+CHANGED
"""
    out = apply_unified_diff(src, diff)
    assert out == "A\nDUP\nB\nCHANGED\nC\n"


def test_handles_no_trailing_newline():
    src = "line1\nline2"
    diff = """\
@@ -2,1 +2,1 @@
-line2
+line2-fixed
"""
    out = apply_unified_diff(src, diff)
    assert out == "line1\nline2-fixed"
