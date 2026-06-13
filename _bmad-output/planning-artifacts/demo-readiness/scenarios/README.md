# Demo Scenarios — reproducible per-feature walkthroughs

One file per matrix area (A–K). Each scenario is a self-contained,
reproducible recipe a presenter follows to demonstrate a single feature
**and its edge cases** on a fresh install, using committed seed data.

## Format (per feature)
```
### <Feature> — <matrix id>
Seed: <what data / which example repo to use>
Happy path:
  1. <exact click-path / API call>
  ...→ expected: <observable result>
Edge cases:
  - <edge> → <how to trigger> → expected: <observable result>
Capture: <which take-demo-video/take-screenshots spec, if any>
```

## Reproducible seed data (already in the repo)
- `backend/examples/tests/` — bundled "Examples" project, auto-seeded at
  startup (calculator, api_testing, browser, data_processing, flows). These
  are the canonical demo fixtures; prefer them over ad-hoc data.
- Seed admin: `admin@roboscope.local` / `admin123` (auto-seeded).
- Public reference repo "Robot Framework Examples" auto-cloned at startup.

## Media-capture harness
- `e2e/tests/take-screenshots.spec.ts` — screenshots of key flows (skipped in CI).
- `e2e/tests/take-demo-video.spec.ts` — screen recording of the demo flow.
- Run locally: `cd e2e && DEMO_VIDEO=1 npx playwright test take-demo-video.spec.ts`
  (the config un-ignores the video spec when `DEMO_VIDEO` is set).

## Status
Per-area scenario files are authored as each area's QA pass confirms the
feature + edge cases work (see iteration-log). The full Playwright E2E suite
is the automated backbone that proves the happy paths across areas A–K.
