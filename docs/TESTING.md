# Testing strategy

Three tiers, ordered by cost. Every test belongs to exactly one tier, and the
backend tier is **derived** from what a test touches (`backend/tests/conftest.py::pytest_collection_modifyitems`)
so nobody has to remember a decorator.

| Tier | Backend (pytest) | Frontend (Vitest) | Where it runs |
|------|------------------|-------------------|---------------|
| **Unit** — no DB, no app, no real subprocess, no network | auto-mark `unit` (≈1200 tests) | pure-TS specs in `src/tests/{utils,types,i18n}` + the `robotTextIO` / `flowConverter` specs | `make test-unit`, mutation-tested |
| **Integration** — real DB/app, real subprocess, real git | auto-mark `db` (TestClient + in-memory SQLite, ≈1200 tests); explicit `slow` (real subprocess / venv / git in `tmp_path`, ≈90 tests); explicit `integration` (real Playwright Chromium, ≈40 tests, opt-in) | component specs mounting Vue (`@vue/test-utils`, 28 files) + pinia store specs | `make test-backend-db`, `make test-backend-slow`, `make test-backend-integration`, `make test-frontend` |
| **E2E** — real backend + Vite dev server + Chromium | — | — | `e2e/` (Playwright, 66 specs, 1 worker), `make test-e2e`, `.github/workflows/e2e.yml` |

Rules of thumb

- A backend test that takes `db_session` / `client` / `*_user` is `db`; otherwise it is `unit`.
  Marking a module `pytestmark = pytest.mark.slow` opts it out of the fast loop
  (`make test-backend-fast` = `not slow and not integration`).
- `integration` (browser) is excluded by `addopts` everywhere, including CI; run it
  with `make test-backend-integration` on a machine with `playwright install chromium`.
- The TestClient lifespan boots the real app against the app engine. `tests/conftest.py`
  points that engine at a per-xdist-worker SQLite file in the temp dir and sets a
  `SECRET_KEY`, so `pytest -n auto` works without a `.env` and without workers racing
  on `./roboscope.db`.
- Frontend: six specs test copied-inline logic rather than the real module
  (`RobotEditorEscapeRoundTrip`, `RobotEditorIframeRoundTrip`, `RobotEditorSidecarPrune`,
  `views/RecordingLauncherView.targetUrl`, `views/RecordingLiveView.*`). They catch nothing
  in production code and are not worth mutating; migrate them to import the module when touched.

## Mutation testing (unit tier only)

Coverage says a line ran; a mutation score says a test would notice if the line were wrong.
Both tools mutate only pure-logic modules that have dedicated unit specs — DB, HTTP and
Vue code are excluded because mutants there are slow to evaluate and mostly equivalent.

### Backend — mutmut (2.x)

Config: `backend/pyproject.toml` `[tool.mutmut]` (`paths_to_mutate` lists the modules) and
`backend/mutmut_config.py` (a `pre_mutation` hook that narrows the pytest command to the
module's own test files — `tests/<pkg>/test_<module>*.py` plus an explicit extras map).
mutmut is pinned `<3` because mutmut 3 assumes a src-layout and asserts on a package that is
literally named `src`, which this backend is.

```bash
make mutation-backend                                     # all configured modules (minutes)
cd backend && .venv/bin/mutmut run --paths-to-mutate src/execution/resolver.py --rerun-all
cd backend && .venv/bin/mutmut results                    # summary
cd backend && .venv/bin/mutmut show <id>                  # the surviving diff
cd backend && .venv/bin/mutmut html && open html/index.html
```

mutmut 2 mutates the file **in place** (with a backup it restores afterwards) and caches
verdicts in `backend/.mutmut-cache` (git-ignored). If a run is killed hard, `git status`
shows the mutated file; `git checkout` it. `--rerun-all` re-checks every mutant that survived
the focused run against the whole unit tier before reporting it, so a missing entry in the
extras map costs time, not correctness.
Add a new pure module to `paths_to_mutate` when you give it a dedicated unit test file; add
non-conventional test files to `EXTRA_TESTS`.

### Frontend — Stryker

Config: `frontend/stryker.config.json` (`mutate` lists the modules, vitest runner, per-test coverage).

```bash
make mutation-frontend                                           # all configured modules
cd frontend && ./node_modules/.bin/stryker run --mutate src/utils/chartGaps.ts   # one module
open frontend/reports/mutation/index.html                        # HTML report
```

### Reading the score

- **Killed**: a unit test failed on the mutant. Good.
- **Survived**: no test noticed. Either add an assertion or accept it as equivalent
  (e.g. a logging string). Look at the diff before adding a test for the sake of a number.
- **No coverage**: the unit tier never executes that line. Either it needs a test or it
  belongs to a module that should not be in the mutate list.
- Thresholds are informational (`break: null`); nothing in CI gates on the score.

### Measured baseline (2026-10-27, local, 6 cores)

Backend (mutmut, `--rerun-all`, ≈14 s per mutant — budget ~1 h per 250 mutants):

| Module | Killed | Survived | Score |
|--------|-------:|---------:|------:|
| `src/utc_response.py` | 4 | 0 | 100 % |
| `src/auth/return_to.py` | 27 | 4 | 87 % |
| `src/insecure_tls.py` | 23 | 6 | 79 % |
| `src/environments/venv_utils.py` | 113 | 36 | 76 % |
| `src/execution/resolver.py` | 92 | 63 | 59 % |
| `src/recording/selector_synthesis.py` (49 of 281 checked) | 25 | 24 | 51 % |
| `src/reports/parser.py` | not yet run (313 mutants) | | |

Frontend (Stryker, 95 min for the full list):

| Module | Score | Note |
|--------|------:|------|
| `formatDuration.ts` | 100 % | |
| `errors.ts` | 89 % | |
| `healToggle.ts` | 89 % | |
| `formatDate.ts` | 88 % | |
| `robotEnvVars.ts` | 85 % | |
| `effectiveSelector.ts` | 84 % | |
| `chartGaps.ts` | 79 % | |
| `paletteView.ts` | 78 % | |
| `resourcePath.ts` | 77 % | |
| `robotTextIO.ts` | 55 % | 157 uncovered mutants — mostly error-message strings |
| `flowConverter.ts` | 44 % | 179 uncovered mutants — node-layout branches only exercised by Vue-mount specs |

`robotKeywordSignatures.ts` (30 %) and `robotLanguage.ts` (22 %) were dropped from the
`mutate` list after this run: they are static tables (keyword signatures, CodeMirror
theme/grammar), their ~2300 string-literal mutants cost 98 % of the run time and a surviving
`'#9AA5BF' → ''` tells you nothing. Overall score without them: ≈60 %.

## CI mapping

| Workflow | Tiers |
|----------|-------|
| `build.yml` (push to main) | backend `unit` + `db` + `slow`, frontend all |
| `phase4-gates.yml` (PRs) | Gate 2 boot invariant, Gate 3 auth/teams/audit (`db`), Gate 5 full backend + frontend, Gate 4 axe E2E, Gates 6/7 install smoke |
| `e2e.yml` (push + PRs) | E2E |

Mutation testing is a local / on-demand tool, not a gate.
