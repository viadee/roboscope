# Story RECORDER-2: Extract `heal/` into a standalone PyPI-publishable package

Status: done (extraction); pending (PyPI upload + monorepo cutover)

Epic: RECORDER — Recorder v2 robustness
Story Key: `recorder-2-extract-heal-to-pypi-package`

## Reported

> Danach bauen wir eine Story um den Heal-Anteil in ein eigenes Modul auszulagern. […] Das heal module soll dann vorbereitet werden für eine Veröffentlichung auf PyPI.

## What was extracted

`backend/src/recording/heal/` (1316 LOC source + 1139 LOC tests) lifted into a new sibling repository:

    /Users/rat/git/mateo2/roboscope-rfheal/

Layout:

    roboscope-rfheal/
    ├── pyproject.toml          ← hatchling backend, RF >=5 dep, RF Browser >=18 dep
    ├── README.md               ← installation, quick-start, opt-out, heal-report guide
    ├── LICENSE                 ← Apache-2.0 (project-root copy)
    ├── NOTICE                  ← copyright + provenance from RoboScope
    ├── CHANGELOG.md            ← v0.1.0 entry referencing SH-2/3/4/5 history
    ├── .gitignore
    ├── src/
    │   └── RoboScopeHeal/
    │       ├── __init__.py     ← public API surface + library class re-export
    │       ├── candidate_finder.py
    │       ├── fingerprint.py
    │       ├── heal_report.py
    │       └── library.py      ← @library class RoboScopeHeal: …
    └── tests/                  ← 70 unit cases + 2 deferred e2e suites
        ├── test_candidate_finder.py
        ├── test_fingerprint.py
        ├── test_heal_report.py
        ├── test_library.py
        ├── test_long_tail_keywords.py
        ├── test_fingerprint_e2e.py     (skipped — needs Playwright)
        └── test_real_browser_heal_e2e.py (skipped — needs Playwright)

Imports rewritten throughout: `from src.recording.heal.X` → `from RoboScopeHeal.X`. The new `__init__.py` re-exports the library class (`RoboScopeHeal`) so users can write `Library    RoboScopeHeal` in their `.robot` files without a fully-qualified module path.

## Validation

| Step | Outcome |
|---|---|
| Standalone install (`pip install -e .[test]` in fresh venv) | OK |
| Module import (`import RoboScopeHeal; RoboScopeHeal.RoboScopeHeal.__name__`) | OK — `RoboScopeHeal` |
| Unit tests (`pytest tests/ --ignore=*_e2e.py`) | **70 / 70 pass** |
| `python -m build` (sdist + wheel) | OK — `roboscope_rfheal-0.1.0-py3-none-any.whl` (28 KB) + `.tar.gz` (23 KB) |
| `twine check dist/*` | **PASSED** for both artefacts |
| Cross-install in a third venv (wheel only, no source) | OK — package importable, library class resolvable |

## What was NOT changed (deliberate)

- **The RoboScope monorepo `backend/src/recording/heal/` is untouched.** The backend continues to use its in-tree copy. Switching the backend to `pip install roboscope-rfheal` is a release-migration concern (3 backend call-sites in `execution/router.py` + `stats/service.py` use deferred `from src.recording.heal.heal_report import parse_heal_audit`; those become `from RoboScopeHeal import parse_heal_audit` in the cutover commit). Tracked separately so the extraction can be reviewed without coupling to the cutover.
- **No PyPI upload yet.** The package is build- and twine-clean; uploading to PyPI requires (a) creating the GitHub repo at `viadee/roboscope-rfheal`, (b) provisioning a PyPI API token, (c) tagging `v0.1.0`. None of that is something an AI assistant should do unilaterally — it's a release-management decision with a public-namespace land-grab attached.

## Suggested next steps (for a human operator)

1. `git remote add origin git@github.com:viadee/roboscope-rfheal.git && git push -u origin main`.
2. Create a PyPI account / project + API token. Test-upload to `test.pypi.org` first (`twine upload --repository testpypi dist/*`) and install from there to make sure the wheel resolves cleanly when fetched from a real index.
3. When happy: `twine upload dist/*` to publish 0.1.0 to PyPI proper.
4. Cutover commit in the RoboScope monorepo: drop `backend/src/recording/heal/` + `backend/tests/recording/heal/`, add `roboscope-rfheal>=0.1.0` to `backend/pyproject.toml`, replace the 3 deferred imports.
5. Add CI to the new repo (GitHub Actions: matrix-test 3.10/11/12/13, build sdist+wheel on tag, publish on `v*` tag with PyPI's OIDC trusted-publisher flow — no static tokens).

## Out of scope

- Renaming the package away from `roboscope-rfheal`. The name keeps RoboScope-attribution because the heal pipeline shipped first as part of RoboScope; future independent contributors can take over the namespace as they see fit.
- Splitting the heal-report consumers (`HealAuditEntry`, `parse_heal_audit`) into a separate `roboscope-rfheal-report` package. Single package keeps the install footprint small.
- Removing the `Browser`-library dependency. Heal keywords are concrete wrappers around Browser-library actions; there's no useful "library-agnostic" abstraction layer to introduce here.
