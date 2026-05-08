"""Story AI-2 — unit tests for the patch extractor."""

from __future__ import annotations

from src.ai.patch_extractor import extract_patch_suggestions


SINGLE_PATCH = """\
# Analysis

The login test failed because the submit button's selector changed.

```patch
--- a/tests/login.robot
+++ b/tests/login.robot
@@ -10,3 +10,3 @@ Login Test
     Input Text    id=user    ${USERNAME}
-    Click    id=submit
+    Click    [data-testid=submit]
     Wait Until Element Is Visible    text=Welcome
```

## Priority: HIGH
"""


MULTIPLE_PATCHES = """\
## Summary

Two independent selector changes caused the two failures.

```patch
--- a/tests/login.robot
+++ b/tests/login.robot
@@ -5,1 +5,1 @@
-    Click    id=submit
+    Click    [data-testid=submit]
```

Second file:

```patch
--- a/tests/checkout.robot
+++ b/tests/checkout.robot
@@ -20,1 +20,1 @@
-    Input Text    id=coupon    10OFF
+    Input Text    [data-testid=coupon-input]    10OFF
```
"""


MALFORMED_NO_HEADER = """\
```patch
just some code without unified-diff headers
  Click    id=submit
```
"""


PROSE_ONLY = """\
## Summary

Nothing fixable here — the test is flaky due to network issues.

```python
# not a patch block — different language label
print("hello")
```
"""


UNICODE_PATCH = """\
```patch
--- a/tests/üöä.robot
+++ b/tests/üöä.robot
@@ -1,1 +1,1 @@
-    Log    old
+    Log    neu — with ümlauts
```
"""


def test_extracts_single_patch() -> None:
    patches = extract_patch_suggestions(SINGLE_PATCH)
    assert len(patches) == 1
    assert patches[0]["file_path"] == "tests/login.robot"
    assert "--- a/tests/login.robot" in patches[0]["unified_diff"]
    assert "+++ b/tests/login.robot" in patches[0]["unified_diff"]
    assert "[data-testid=submit]" in patches[0]["unified_diff"]


def test_extracts_multiple_patches_in_order() -> None:
    patches = extract_patch_suggestions(MULTIPLE_PATCHES)
    assert [p["file_path"] for p in patches] == [
        "tests/login.robot",
        "tests/checkout.robot",
    ]


def test_silently_skips_malformed_patch_without_header() -> None:
    assert extract_patch_suggestions(MALFORMED_NO_HEADER) == []


def test_returns_empty_on_prose_only() -> None:
    assert extract_patch_suggestions(PROSE_ONLY) == []


def test_returns_empty_on_none_or_blank() -> None:
    assert extract_patch_suggestions(None) == []
    assert extract_patch_suggestions("") == []


def test_handles_unicode_in_path_and_body() -> None:
    patches = extract_patch_suggestions(UNICODE_PATCH)
    assert len(patches) == 1
    assert patches[0]["file_path"] == "tests/üöä.robot"
    assert "ümlauts" in patches[0]["unified_diff"]


def test_plain_path_header_without_a_prefix_accepted() -> None:
    md = (
        "```patch\n"
        "--- tests/foo.robot\n"
        "+++ tests/foo.robot\n"
        "@@ -1,1 +1,1 @@\n"
        "-old\n+new\n"
        "```\n"
    )
    patches = extract_patch_suggestions(md)
    assert patches == [{
        "file_path": "tests/foo.robot",
        "unified_diff": (
            "--- tests/foo.robot\n"
            "+++ tests/foo.robot\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n+new"
        ),
    }]
