# Changelog

All notable changes to this project are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.1] — 2026-05-11

### Changed
- `robotframework-browser` moved from a hard runtime dependency to an optional `[browser]` extra. The heal library uses `BuiltIn().run_keyword("Browser.<keyword>")` to delegate at test-execution time — it does NOT import the Browser library at module-import time — so installing the heal package without Browser succeeds cleanly. Users who actually run heal-decorated tests should `pip install robotframework-roboscopeheal[browser]`.

  Motivation: RoboScope ships in offline release bundles that pre-download wheels via `pip download`. The previous hard `robotframework-browser>=18.0` dependency forced pip to also resolve Playwright + node + a Chromium-runtime stack, which is wildly out of scope for the heal library and bloated every offline ZIP. Moving Browser to an extra cuts ~80 MB from the offline bundle and unblocks the air-gapped install path entirely.



## [0.2.0] — 2026-05-11

### Changed
- Distribution name renamed `roboscope-rfheal` → `robotframework-roboscopeheal` to match the Robot Framework community PyPI convention (`robotframework-*` prefix). The Python import path is unchanged (`from RoboScopeHeal import …`); only the `pip install` name moves.

### Added — sync with upstream RoboScope `backend/src/recording/heal/`
- RECORDER-FRAMES guard in `_lookup_command_id` and `_lookup_stored_fingerprint`: when the failed selector carries an `iframe[...] >>> ` qualifier, the heal walker correctly strips the wrap before sidecar lookup and bails out on cross-origin iframe document walks (the walker JS uses `document.querySelectorAll` on the top frame and would silently emit top-frame selectors for cross-frame elements without this guard).
- `_split_iframe_wrap` exposed as a public helper so consumers can correlate iframe-recorded sidecar entries against runtime failures.

### Fixed
- Type-narrowing nit in `library.py::verify_callback` — `verify(selector) == 0` no longer wrapped in a redundant `bool(...)`.

## [0.1.0] — 2026-04-28

Initial extraction from the RoboScope monorepo into a standalone PyPI-publishable package.

### Added
- `RoboScopeHeal` Robot Framework library with the `Heal *` keyword family wrapping `Browser`-library actions (Click, Fill Text, Type Text, Press Keys, Get Text, Get Attribute, Upload File By Selector, Select Options By, Drag And Drop, Hover, Wait For Elements State).
- Sidecar reader (`<test>.rbs.json`) for recorder-emitted selector candidates.
- Cross-strategy selector transposition (id ↔ test-id ↔ aria ↔ text ↔ css ↔ xpath ↔ Playwright locator).
- DOM-walk fingerprint scoring for sidecar-less heals.
- Per-test budget, confidence thresholds, and `no-heal` tag opt-out.
- `parse_heal_audit(path)` helper for downstream tooling.

### Provenance
Source originated as the `backend/src/recording/heal/` module of [RoboScope](https://github.com/viadee/roboscope). Extracted into this repository under Apache-2.0 with full git history reset (the inheritance is documented in NOTICE).
