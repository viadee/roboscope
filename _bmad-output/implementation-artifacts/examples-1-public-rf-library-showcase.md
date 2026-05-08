# Story EXAMPLES-1: Public GitHub repo with green examples for the most popular Robot Framework libraries

Status: phase A done — pre-push

## Phase A summary (delivered)

- Sibling repo created at `/Users/rat/git/mateo2/roboscope-examples/`
  (commit `b15f60a` on local `main`).
- All 7 example folders implemented; **`uv run robot examples/`
  reports 26 tests, 26 passed**.
- LICENSE (Apache-2.0), NOTICE, .gitignore, README, Makefile,
  pyproject.toml (pinned deps), docker-compose.yml (optional offline
  httpbin), .github/workflows/ci.yml all in place.
- Browser suite uses a `data:` URL so it's fully offline-deterministic
  (the original example.com plan flaked on slow networks; switched to
  inline HTML to remove the external dep).
- DatabaseLibrary tests use the modern `Check Row Count`
  assertion-engine keyword instead of the deprecated
  `Row Count Is Equal To X`.

## Phase B (still to do — gated on user authorisation)

1. Create the public GitHub repo (`gh repo create viadee/roboscope-examples --public`).
2. `git push -u origin main`.
3. Configure branch protection on `main` (require CI green).
4. RoboScope-side integration:
   - Add an "Examples & starter projects" section to
     `roboscope/README.md` linking to the public repo.
   - Add a panel in the in-app docs (EN/DE/FR/ES) with the clone URL.
   - Add a hint in the "New repository" dialog ("Looking for working
     examples? Try roboscope-examples [link]").

Phase B requires explicit go-ahead because publishing to GitHub is
public + irreversible (the repo URL gets indexed within minutes).

Epic: ECOSYSTEM — Resources outside the main app
Story Key: `examples-1-public-rf-library-showcase`

## Reported

Users coming to RoboScope often ask "show me a working `Browser` /
`Requests` / `Database` / `Process` example" — and most blog posts and
README snippets they find online don't actually run end-to-end (broken
imports, missing fixtures, mock services that no longer exist).

We want a separate, public, Apache-2.0-licensed GitHub repository
that contains **actually-runnable** examples for the most-used Robot
Framework libraries, each one wired into CI so a green-checkmark on
the README is the proof. RoboScope's in-app docs and README will link
to it.

## Goals

1. **Single source of truth** for "here is the simplest meaningful
   working example of `<library>`."
2. **Always green** — every push runs every example via GitHub
   Actions; merging requires the workflow passing.
3. **Forkable as a starter kit** — a new RoboScope user can `git clone`
   it, drop it into RoboScope as a project, and run the suites with
   one click.
4. **Keeps RoboScope itself lean** — examples don't bloat the main
   repo or the docker image.

## Non-goals (V1)

- A tutorial site with prose explanations. README + Robot doc strings
  per suite are the doc layer.
- 100% library coverage. Pick the popular ones; community PRs can add
  more later.
- Mobile / native libraries (`AppiumLibrary`, `Mainframe3270`) — they
  need device farms / TN3270 emulators, much heavier CI.
- Translations beyond English. The Robot suites already have
  international users; we keep the README in English.

## Acceptance Criteria

### AC1 — Repo skeleton

A new directory `roboscope-examples/` (sibling to `roboscope/` and
`roboscope-rfheal/`) with:

```
roboscope-examples/
├── README.md
├── LICENSE                  # Apache-2.0
├── NOTICE
├── .gitignore
├── pyproject.toml           # robotframework + library deps + dev tools
├── Makefile                 # `make test`, `make lint`, `make clean`
├── .github/
│   └── workflows/
│       └── ci.yml           # runs make test on push + PR
├── examples/
│   ├── 01-builtin-collections/
│   ├── 02-builtin-string-datetime/
│   ├── 03-process-and-os/
│   ├── 04-requests-rest-api/
│   ├── 05-database-sqlite/
│   ├── 06-jsonlibrary/
│   └── 07-browser-playwright/
└── docker-compose.yml       # optional services (httpbin) for offline runs
```

### AC2 — Library coverage (V1)

The seven folders above. Each folder MUST contain:

1. A `README.md` (3–10 lines) that explains *what* the suite proves
   and *which* keywords are demonstrated.
2. At least one `*.robot` suite that runs to green with the deps
   declared in the top-level `pyproject.toml`.
3. No external paid services. Fixtures are either local files
   (SQLite db, JSON files), public free APIs (`httpbin.org`,
   `jsonplaceholder.typicode.com`), or a `docker-compose` service.

Per-folder library coverage:

| Folder                       | Library / built-in     | Demonstrates                                    |
|------------------------------|------------------------|-------------------------------------------------|
| 01-builtin-collections       | Collections            | List/Dict ops, `Get From Dictionary`, `Count Values In List` |
| 02-builtin-string-datetime   | String, DateTime       | Templating, regex, ISO date math                |
| 03-process-and-os            | Process, OperatingSystem | Run a CLI tool, capture stdout, file roundtrip |
| 04-requests-rest-api         | RequestsLibrary        | GET/POST against httpbin, status code asserts   |
| 05-database-sqlite           | DatabaseLibrary + sqlite3 | Schema setup → insert → query → row-count assert |
| 06-jsonlibrary               | JSONLibrary            | Parse, query (JSONPath), update, write back     |
| 07-browser-playwright        | Browser library        | Open page → fill input → click → assertion      |

### AC3 — Top-level Makefile

`make test` runs every suite green:

```make
test:
	uv run robot --outputdir results examples/

lint:
	uv run robotidy --check examples/
	uv run robocop --reports all examples/

clean:
	rm -rf results/ .venv/
```

`make install` bootstraps a uv venv with the right deps. `make rfbrowser-init` runs `rfbrowser init` for the Browser-library example
(documented in README that this is a one-time step).

### AC4 — GitHub Actions CI

`.github/workflows/ci.yml`:

- Triggers: `push` to `main`, `pull_request` to `main`.
- One job, `runs-on: ubuntu-latest`.
- Steps:
  1. `actions/checkout@v4`.
  2. Set up Python 3.12 via `astral-sh/setup-uv@v3` (matches main repo's tooling).
  3. `uv sync` to install deps.
  4. Start `docker-compose up -d httpbin` if any suite needs it.
  5. `make rfbrowser-init` for the Browser suite.
  6. `make test`.
  7. Upload `results/` as an artifact (so failed runs are debuggable).
- Branch protection on `main` requires a green CI before merge
  (configured in repo settings, not in code).

### AC5 — README

The top-level README contains, in this order:

1. One-paragraph "what is this" pitch + green-CI badge.
2. Quick-start: `git clone … && cd roboscope-examples && make install && make test`.
3. Folder-by-folder index with one-line descriptions and a link to
   each folder's README.
4. "Use with RoboScope" section: how to clone this repo into a
   RoboScope project and run the suites from the UI.
5. Contributing: PR a new `examples/NN-<library>/` folder with at
   least one green test, and the CI will gatekeep.
6. License: Apache-2.0.

### AC6 — RoboScope integration

After the repo is published:

1. Add a link to it in `roboscope/README.md` under a new "Examples
   & starter projects" section.
2. Add a panel in the in-app docs (4 locales) pointing users to the
   repo and showing the `git clone` URL as a copy-button-ready code
   block.
3. Pre-seed a hint in the "New repository" dialog: an info-text
   reading "Looking for working examples? Try roboscope-examples
   (link)."

### AC7 — License + provenance

- LICENSE: full Apache-2.0 text (same file as `roboscope-rfheal`).
- NOTICE: short attribution noting the project is an Apache-2.0
  ecosystem helper for RoboScope (commercial-friendly).
- Each example's README either says "original work, Apache-2.0"
  *or* cites the source if adapted from another Apache-2.0 / MIT
  example. No GPL-derived examples (same constraint as
  RECORDER-LICENSE).

## Implementation phases

1. **Phase A (this story)**: scaffold the repo locally, fill the
   seven folders with green-passing tests, wire CI, write README.
   Stop before pushing to GitHub.
2. **Phase B (separate story EXAMPLES-2)**: create the public
   GitHub repo, push, configure branch protection, add the integration
   surfaces in RoboScope (README + in-app docs + new-repo dialog hint).

Splitting Phase A and Phase B keeps the GitHub-side actions
explicitly authorised.

## Risk notes

- **Flaky external services**. `httpbin.org` and
  `jsonplaceholder.typicode.com` occasionally hiccup. Mitigation: pin
  to specific endpoints with retry-keyword wrappers, and run a local
  `docker-compose up -d httpbin` in CI to remove the dependency on
  the public host.
- **Browser-library Playwright install in CI** is bandwidth-heavy
  (~200 MB). Mitigation: cache `~/.cache/ms-playwright` between
  workflow runs by hashing `pyproject.toml`.
- **Tests must survive `pip` version churn**. Pinned versions in
  `pyproject.toml` (no caret ranges) — every dep is locked. Renovate
  bot can later bump them.
- **License contamination**. Some "robotframework-*-examples" repos
  on GitHub are MIT or Apache, but blog snippets are unlicensed.
  Reviewer must verify every example's provenance before merge.
