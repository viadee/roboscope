# RoboScopeHeal

Self-healing keywords for the [Robot Framework `Browser` library](https://robotframework-browser.org/), driven by recorded selector candidates.

When a recorded `.robot` test fails because a selector no longer matches the live DOM, `RoboScopeHeal` walks a curated fall-back chain — sidecar-stored alternative selectors → cross-strategy transposition → DOM-walk fingerprint scoring — and reports every heal as an audit entry the user can review and accept. **The `.robot` source is never silently rewritten**; heals are surfaced as suggestions, not auto-commits.

## Installation

```bash
pip install roboscope-rfheal
```

`robotframework-browser` is a runtime dependency. If you haven't initialised its bundled Chromium yet:

```bash
rfbrowser init
```

## Quick start

```robotframework
*** Settings ***
Library    Browser
Library    RoboScopeHeal

*** Test Cases ***
Login
    New Browser    chromium    headless=True
    New Context
    New Page    https://example.com/login

    # Heal-prefixed keywords are explicit opt-in. Plain `Click`,
    # `Fill Text`, etc. continue to work exactly as before.
    Heal Fill Text    [data-testid="email"]       user@example.com
    Heal Fill Text    [data-testid="password"]    s3cret
    Heal Click        [data-testid="submit"]
```

The library reads a sidecar `<test>.rbs.json` next to your `.robot` file when present (this is what RoboScope's recorder emits). Without a sidecar, only the cross-strategy + DOM-walk fall-backs apply.

## Heal strategy

When a `Heal *` keyword's primary selector times out, the library tries — in order — until one resolves to a unique element on the live page:

1. **Sidecar candidates.** Alternative selectors recorded by the recorder (test-id → ARIA → text → CSS → XPath → Playwright locator).
2. **Cross-strategy transposition.** `id=foo` → `[data-testid=foo]`, `text=Hello` → `xpath=//*[normalize-space(text())="Hello"]`, etc.
3. **DOM-walk fingerprint scoring.** Healenium-style structural similarity: walks the document and scores each candidate node by tag, attribute overlap, and ancestor path against the original selector's element.

Per-test budget, confidence thresholds, and a `no-heal` test tag bound the blast radius. A failed heal that the test ultimately failed on never offers a "Copy patch" affordance — silently wrong fixes are the failure mode the design avoids.

## Available keywords

| Keyword              | Wraps                          |
| -------------------- | ------------------------------ |
| `Heal Click`         | Browser → `Click`              |
| `Heal Fill Text`     | Browser → `Fill Text`          |
| `Heal Type Text`     | Browser → `Type Text`          |
| `Heal Press Keys`    | Browser → `Press Keys`         |
| `Heal Get Text`      | Browser → `Get Text`           |
| `Heal Get Attribute` | Browser → `Get Attribute`      |
| `Heal Upload File`   | Browser → `Upload File By Selector` |
| `Heal Select Options By` | Browser → `Select Options By` |
| `Heal Drag And Drop` | Browser → `Drag And Drop`      |
| `Heal Hover`         | Browser → `Hover`              |
| `Heal Wait For Elements State` | Browser → `Wait For Elements State` |

## Heal report

Every successful (or attempted-but-failed) heal is appended as one JSON line to `heal_audit.jsonl` in the Robot output directory. The accompanying `parse_heal_audit(path)` Python helper turns that file into structured `HealAuditEntry` objects for dashboards / CI annotations:

```python
from RoboScopeHeal import parse_heal_audit

report = parse_heal_audit(Path("output/heal_audit.jsonl"))
for entry in report.entries:
    print(entry.test, entry.original_selector, "→", entry.healed_selector,
          "confidence=", entry.confidence)
```

## Opt-out per test

Add the `no-heal` tag to any test you don't want healed:

```robotframework
*** Test Cases ***
Strict regression
    [Tags]    no-heal
    Heal Click    [data-testid="submit"]    # ← behaves exactly like Browser.Click
```

## Provenance

Originally developed inside the [RoboScope](https://github.com/viadee/roboscope) project (story SH-2). Extracted into this standalone package so other Robot Framework users can adopt the heal pipeline without pulling in the rest of RoboScope.

## Licence

[Apache-2.0](LICENSE).
