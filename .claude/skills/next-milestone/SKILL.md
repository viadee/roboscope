---
name: next-milestone
description: "Skill: Extract the next milestone phase from CLAUDE.md, plan and implement it fully (backend, frontend, tests, E2E), verify all tests pass, and check for coverage gaps."
---

# Next Milestone Phase

Implement the next unchecked milestone phase from CLAUDE.md end-to-end. **Done = all tests green, no coverage gaps.**

---

## Phase 0 — Extract & Understand

1. Read `CLAUDE.md` and find the **Milestone** section.
2. Identify the **first phase where all sub-items are unchecked** (`- [ ]`). That is the "current phase".
3. List every sub-item of that phase. These are the **deliverables**.
4. Print a summary: phase name, deliverables, and affected modules (backend, frontend, E2E).

---

## Phase 1 — Plan

Before writing any code, create a detailed implementation plan. Use the `TodoWrite` tool to track all tasks.

### 1.1 Architecture & API Design
- For each deliverable: identify new/changed models, schemas, services, routers, stores, views, components.
- Identify new API endpoints (method, path, auth level, request/response schemas).
- Identify new/changed database models and plan Alembic migrations.

### 1.2 Test Plan
- **Backend tests**: list every new service function, router endpoint, and edge case that needs a test.
- **E2E tests**: list every user-facing workflow that needs an E2E spec. Identify which **existing** E2E specs might break and need updating.
- Map each deliverable to its test cases (backend + E2E).

### 1.3 Dependency Order
- Order tasks so that foundational work (models, migrations, services) comes before routers, then frontend stores/views, then tests.
- Group into implementation waves that can be committed atomically.

Print the full plan and **ask the user to confirm** before proceeding.

---

## Phase 2 — Implement (iterative waves)

For each wave from the plan:

### 2.1 Write the Code
- Implement backend changes (models → schemas → service → router → wire into `api/v1/`).
- Implement frontend changes (types → API client → store → view/component → i18n → router).
- Run Alembic migrations if models changed.
- Follow all patterns from CLAUDE.md (db.commit before dispatch_task, model imports for FK resolution, uv for package management, etc.).

### 2.2 Write Backend Tests
- Write pytest tests for every new service function and router endpoint.
- Use existing fixtures (`db_session`, `client`, `admin_user`, `runner_user`, `viewer_user`, `auth_header`).
- Run backend tests after each wave:
  ```bash
  cd backend && python -m pytest tests/ -x -q
  ```
- Fix any failures immediately before moving on.

### 2.3 Write E2E Tests
- Write Playwright E2E specs for new user workflows.
- Use existing page objects and auth fixtures. Create new page objects if needed.
- Use API mocking via `page.route()` following existing patterns.

### 2.4 Run Relevant E2E Tests Only
- During development, only run E2E specs that are **directly affected** by the current wave:
  ```bash
  cd e2e && npx playwright test tests/<relevant-spec>.spec.ts
  ```
- Fix any failures immediately.

### 2.5 Commit
- Create an atomic commit for each completed wave with a conventional commit message.

---

## Phase 3 — Coverage Gap Analysis

After all waves are implemented:

1. **Backend coverage check**: Run `make test-backend-cov` and inspect uncovered lines in new/changed files.
2. **E2E coverage check**: For every new UI element, button, form, and workflow — verify there is an E2E test that exercises it. List any gaps.
3. **Edge cases**: Check error handling paths, permission boundaries (VIEWER vs RUNNER vs EDITOR vs ADMIN), empty states, and validation errors.
4. **i18n**: Verify all new user-facing strings have translations in all 4 languages (EN, DE, FR, ES).

Write additional tests to close any gaps found. Run the relevant tests again to confirm they pass.

---

## Phase 4 — Local Verification

Run the full local test suite to make sure nothing is broken:

```bash
make test-backend    # all backend tests
make test-frontend   # all frontend tests
```

Run **all** E2E tests that are related to the changed modules:
```bash
cd e2e && npx playwright test tests/<all-relevant-specs>.spec.ts
```

Fix any failures. Repeat until green.

---

## Phase 5 — Full E2E on GitHub Actions (Background)

1. Push the branch and create a PR (or push to existing PR branch).
2. The GitHub Actions E2E workflow will trigger automatically.
3. **Launch a background agent** that:
   - Monitors the GitHub Actions run status via `gh run watch` or `gh run view`.
   - When the run completes:
     - If **green**: report success to the user.
     - If **red**: download the failure logs, diagnose the issue, apply fixes, commit, push, and re-monitor. Repeat until green or until 3 fix attempts have been made (then report to the user for manual intervention).

```bash
# Check latest run status
gh run list --branch <branch> --limit 1
gh run view <run-id>
# Download logs on failure
gh run view <run-id> --log-failed
```

---

## Phase 6 — Update CLAUDE.md

Once all tests pass (including GitHub Actions):

1. In `CLAUDE.md`, check off (`- [x]`) every sub-item of the completed phase.
2. Add a summary entry to the "Fertiggestellt" list with all major features implemented.
3. Commit: `docs: mark milestone phase N as complete`

---

## Rules

- **Never skip tests.** Every new endpoint, service function, and UI workflow needs tests.
- **Fix forward.** If a test fails, fix it immediately — don't move to the next wave.
- **Minimal blast radius.** Only run relevant E2E tests during development. Full suite only at the end.
- **Atomic commits.** Each wave gets its own commit with a conventional commit message.
- **Ask before big decisions.** If an architectural choice is ambiguous, ask the user.
- **Follow existing patterns.** Match the code style, file structure, and conventions documented in CLAUDE.md.
