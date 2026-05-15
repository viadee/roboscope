# Story HEAL-VENDORED: ship `robotframework-roboscopeheal` with every RoboScope release

Status: review

Epic: HEAL — Self-Healing opt-in ergonomics
Story Key: `heal-vendored-release-integration`

## Reasoning

The previous commit (`f15f9d1`) moved the heal-library out of the
RoboScope monorepo and into the sibling `roboscope-rfheal/`
checkout. That works for the user's local dev loop because:
  1. they have the sibling repo checked out at `../roboscope-rfheal`;
  2. `[tool.uv.sources]` in `backend/pyproject.toml` routes the
     `robotframework-roboscopeheal>=0.2` dep at the sibling path.

It does NOT work for **anyone else** until PyPI publication lands:
fresh clones of `roboscope` have no sibling, the dep can't be
resolved, `make dev` fails. The standalone offline ZIPs
(`roboscope_offline_<platform>.zip`) — the user-facing release
artifact — pre-download all wheels via
`scripts/build-mac-and-linux.sh`'s `pip download` step; that step
silently skips dependencies that aren't on PyPI, producing an
install bundle that's missing the heal library entirely.

The user wants RoboScope to **just work** out of the offline ZIP
(or `git clone && make dev`), with or without PyPI publication of
the heal library having happened yet.

## Change

### Vendor the rfheal source into the RoboScope repo

Copy the contents of `roboscope-rfheal/` (the sibling repo) into
`backend/vendor/robotframework-roboscopeheal/`. Files committed:

```
backend/vendor/robotframework-roboscopeheal/
├── pyproject.toml              # name = robotframework-roboscopeheal, v0.2.0
├── README.md
├── LICENSE                     # Apache-2.0
├── NOTICE                      # provenance under monorepo
├── CHANGELOG.md
└── src/RoboScopeHeal/
    ├── __init__.py
    ├── candidate_finder.py
    ├── fingerprint.py
    ├── heal_report.py
    └── library.py
```

Tests deliberately NOT vendored — they live in the standalone repo
and get exercised by that repo's CI; vendoring them would double
the test surface in the RoboScope monorepo CI for zero new
signal (the heal library is exercised end-to-end by RoboScope's
own e2e Recorder tests + the heal-report-endpoint test, both of
which already cover the integration boundary).

### `[tool.uv.sources]` re-pointed at the vendored path

```toml
[tool.uv.sources]
robotframework-roboscopeheal = { path = "vendor/robotframework-roboscopeheal", editable = true }
```

Path goes from `../roboscope-rfheal` (sibling, dev-only) to
`vendor/robotframework-roboscopeheal` (committed, travels with
every clone). Editable=true so a dev who edits the vendor dir
sees the change live — same ergonomics as the sibling path had,
just no separate clone needed.

### Sync script

`scripts/sync-roboscopeheal.sh` — one-shot copy from sibling
into vendor, gated behind a confirmation prompt. Used when:

  - the rfheal sibling repo has a fix that needs to land in
    RoboScope without waiting for the next PyPI release;
  - a release prep step (mirror everything that's drifted).

Diff against the vendored copy gets shown to the user before the
overwrite happens — last line of defense against silently
clobbering vendor-side hand-edits.

### Offline build integration

`scripts/build-mac-and-linux.sh` learns to build the vendored
wheel as part of its wheel-collection step:

```bash
# Build robotframework-roboscopeheal wheel from vendor/ — until
# v0.2 lands on PyPI this is the only way to get it into the
# offline bundle. Wheel ends up in dist/wheels/ alongside the
# pip-downloaded ones; install.sh's `--find-links wheels/` picks
# it up automatically.
echo "Building robotframework-roboscopeheal wheel from vendor/..."
(cd "$ROOT_DIR/backend/vendor/robotframework-roboscopeheal" \
 && python3 -m build --wheel --outdir "$DIST/wheels")
```

Mirror change in `scripts/build-windows.ps1` for the Windows
offline ZIP.

### Docker

`docker/backend.Dockerfile` already does `pip install -e .` from
the backend directory. With the vendored path + `[tool.uv.sources]`,
that resolution works inside the Docker build — `pip` (or `uv`)
sees the local path, builds + installs. No Dockerfile change
needed.

## Out of scope

- Submodule / subtree mode. Would be cleaner long-term (single
  upstream, shared history) but requires the rfheal repo to have
  a public remote URL, which isn't true yet. Vendoring is the
  immediate unblock; subtree migration can happen later under a
  separate story when PyPI publication lifts the access barrier.

- Auto-sync on rfheal-repo commit. The `sync-roboscopeheal.sh`
  script is manually invoked. A pre-commit-hook-style auto-sync
  is a follow-up.

- Removing the vendored copy after PyPI publication. Once the
  PyPI version is reliable, the `[tool.uv.sources]` block can be
  dropped and the dep resolves from PyPI. The vendor dir CAN stay
  as an offline-install fallback (some deployments will never have
  internet access for `pip install`); that's a release-management
  decision to make at the time, not a code change to plan now.

## Edge cases

| Case | Behaviour |
|---|---|
| User clones RoboScope without sibling rfheal repo present | `uv sync` works — resolves the dep from the vendored path. Sibling is no longer needed. |
| User wants to actively hack the heal library | They edit `backend/vendor/robotframework-roboscopeheal/src/RoboScopeHeal/*.py`. The editable install means changes are live. When done, they cherry-pick the diff back into the upstream `roboscope-rfheal` repo so the standalone library benefits too. |
| The vendored copy drifts from the sibling repo | The sync script's pre-overwrite diff prompt is the user's signal. CI can compare hashes and fail the build when they don't match (future hardening). |
| PyPI publication happens later, both `[tool.uv.sources]` and vendor dir are still in place | The sources block takes precedence — vendored copy used. To "switch" to PyPI, drop the sources block. Vendor dir can stay for offline installs. |
| Offline-build script runs without `python -m build` available | Fail the build with a clear message — `pip install build` is a one-line fix for whoever runs the release script. Document in `scripts/dist-README.md`. |
| User on `roboscope_offline_linux.zip` runs `install.sh` | `pip install --no-index --find-links wheels/ -r requirements.txt` finds the bundled wheel; `import RoboScopeHeal` works at runtime. |

## Verification

### Manual

1. **Fresh-clone path**: `git clone roboscope /tmp/rs-fresh && cd /tmp/rs-fresh && cd backend && uv sync` — must succeed without a sibling rfheal repo. Assert `python -c "import RoboScopeHeal; print(RoboScopeHeal.__version__)"` prints `0.2.0`.
2. **Offline-bundle path**: `bash scripts/build-mac-and-linux.sh macos-arm64` produces `dist/roboscope-offline-macos-arm64/wheels/robotframework_roboscopeheal-0.2.0-py3-none-any.whl`. Extract ZIP in a clean dir, run `install.sh`, then start the backend, then import `RoboScopeHeal` from the bundled venv.
3. **Editable-vendor path**: edit `backend/vendor/robotframework-roboscopeheal/src/RoboScopeHeal/__init__.py` to print "hello" at import; restart backend; verify the print fires. Proves the vendor install is editable.

### Automated

- New backend test `backend/tests/test_vendored_rfheal_present.py`:
  - Walks `backend/vendor/robotframework-roboscopeheal/` and
    asserts the four canonical source files exist
    (`candidate_finder.py`, `fingerprint.py`, `heal_report.py`,
    `library.py`) PLUS `pyproject.toml`. Catches accidental
    deletion / restructure during a refactor.
  - Asserts the vendored `pyproject.toml` declares
    `name = "robotframework-roboscopeheal"` (catches a rename of
    the upstream library without a corresponding vendor sync).
  - Imports `RoboScopeHeal` from the installed venv and asserts
    `__version__` matches the version in the vendored
    `pyproject.toml`. Catches the "stale vendored wheel installed,
    new source on disk" scenario.

## Risk

- **Drift between vendor and sibling/upstream**: same risk we had
  before extraction. The sync script is the mitigation; CI hash
  comparison is the future hardening.
- **License compliance**: vendoring an Apache-2.0 project requires
  preserving the LICENSE + NOTICE files. The vendor copy includes
  both; the RoboScope repo's top-level LICENSE remains separate
  (RoboScope itself is also Apache-2.0, so the licenses are
  compatible and no extra notice is needed in roboscope's LICENSE).
- **Wheel reproducibility**: the `python -m build` step in the
  offline-build script produces a wheel whose hash depends on the
  build environment (Python version, build tool versions). Not a
  blocker — pip resolves wheels by version, not hash, in the
  `--find-links` flow. If we ever need bit-for-bit reproducible
  release bundles, switch to a `python -m build --no-isolation`
  with pinned `build` + `hatchling` versions.

## Dev Agent Record

### Completion Notes (2026-05-15)

Implementation was already complete on `feat/heal-toggle`. The following were present and verified:

- `backend/vendor/robotframework-roboscopeheal/` — vendored source tree with pyproject.toml (v0.2.1), LICENSE, NOTICE, README.md, CHANGELOG.md, and four source files under `src/RoboScopeHeal/`.
- `backend/pyproject.toml` — `[tool.uv.sources]` re-pointed from sibling repo to `vendor/robotframework-roboscopeheal` (editable=true).
- `scripts/sync-roboscopeheal.sh` — one-shot copy from sibling into vendor with pre-overwrite diff prompt.
- `scripts/build-mac-and-linux.sh` — builds the vendored wheel during offline bundle creation.
- `backend/tests/test_vendored_rfheal_present.py` — 11 tests: vendor dir exists, 5 canonical files present, distribution name check, installed version matches pyproject.toml.

Backend test suite: 11 passed, 0 failed.

### File List

- `backend/vendor/robotframework-roboscopeheal/` (new directory, committed source tree)
- `backend/vendor/robotframework-roboscopeheal/pyproject.toml` (new)
- `backend/vendor/robotframework-roboscopeheal/LICENSE` (new)
- `backend/vendor/robotframework-roboscopeheal/NOTICE` (new)
- `backend/vendor/robotframework-roboscopeheal/README.md` (new)
- `backend/vendor/robotframework-roboscopeheal/CHANGELOG.md` (new)
- `backend/vendor/robotframework-roboscopeheal/src/RoboScopeHeal/__init__.py` (new)
- `backend/vendor/robotframework-roboscopeheal/src/RoboScopeHeal/candidate_finder.py` (new)
- `backend/vendor/robotframework-roboscopeheal/src/RoboScopeHeal/fingerprint.py` (new)
- `backend/vendor/robotframework-roboscopeheal/src/RoboScopeHeal/heal_report.py` (new)
- `backend/vendor/robotframework-roboscopeheal/src/RoboScopeHeal/library.py` (new)
- `backend/pyproject.toml` (modified — uv.sources vendored path)
- `scripts/sync-roboscopeheal.sh` (new)
- `scripts/build-mac-and-linux.sh` (modified — wheel build step)
- `backend/tests/test_vendored_rfheal_present.py` (new)
