# Story LAUNCH-1: Standalone-Start UX — readable log + obvious "open this URL" cue

Status: planned (target 0.9.1)

Epic: Distribution UX polish
Story Key: `launch-1-windows-terminal-ux`

## Story

As a fresh user who just unzipped the standalone Release Package and ran `start-windows.bat` (or the mac/linux equivalent),
I want a readable, human-friendly terminal log and an unmistakable "open `http://localhost:8145` in your browser" cue at the end of startup,
so that I can find the running app within seconds rather than scrolling through a wall of JSON-formatted log lines hunting for the URL.

## Background / problem statement

Two pain points reported on Windows (and present on every standalone platform; Windows is just where it looks worst):

1. The terminal scroll is **JSON log output** — `python_json_logger.JsonFormatter` is fine for production observability ingestion, hostile for a fresh user's eyeballs. The boot sequence emits 30–40 log lines that look like `{"timestamp":"…","level":"INFO","logger":"roboscope.…","message":"…"}` instead of the readable `INFO  roboscope.repos: …` format anyone reading a console expects.
2. After successful startup, the URL the user needs (`http://localhost:8145`) is not surfaced. They have to read the README, the bundled `dist-README.md`, or a config file to know where to point their browser. On Windows specifically, the cmd / PowerShell window doesn't even render the OSC-8 hyperlink most modern terminals would auto-detect, so even `INFO uvicorn: Uvicorn running on http://0.0.0.0:8145` doesn't pop visually.

Both add up to a "I just installed it, now what?" moment that we can fix cheaply.

## Acceptance Criteria

1. **AC1 — Readable log format on standalone start.** The standalone start scripts (`start-mac-and-linux.sh` / `start-windows.bat`) launch the backend with a `LOG_FORMAT=text` env var (or equivalent) that flips `main.py`'s logging configuration from JSON to a readable `LEVEL  logger: message` form. The default in `make dev` and Docker stays unchanged (JSON is right for those — log shippers eat them; this only affects the human-launched binary path).

2. **AC2 — Loud "open this URL" banner after readiness.** Once uvicorn reports the `Application startup complete.` line, the start script (or a dedicated post-startup hook in `main.py`'s lifespan) prints a clearly-set-off banner:

   ```
   ════════════════════════════════════════════════
   ✓  RoboScope is running
      Open in your browser:  http://localhost:8145
   ════════════════════════════════════════════════
   ```

   The exact URL respects the `PORT` env var (so a user who set `PORT=9000` sees the right URL). The banner survives the JSON-vs-text logging toggle because it's printed via `print` to stdout, not through the logger — that way it's never mistaken for a stray INFO line.

3. **AC3 — Optional auto-open on default platform browser.** Add a `--open` flag (or `OPEN_BROWSER=1` env in the bundled `.env`, default off) that, after the readiness banner, calls `webbrowser.open("http://localhost:<port>")`. Default OFF so headless installs don't get a `BROWSER=...` mismatch headache; documented in `scripts/dist-README.md` as the recommended toggle for desktop installs.

4. **AC4 — No regression on Docker / dev-mode logs.** `make dev`, `docker-up`, and the test suite must all keep emitting JSON exactly as today (`pythonjsonlogger.JsonFormatter` driver in `main.py` left untouched on those code paths). Tests in `backend/tests/test_main.py` get one extra assertion: the logger config falls back to JSON when `LOG_FORMAT` is unset.

5. **AC5 — Windows console encoding.** The banner uses ASCII-safe box-drawing (`====`) instead of Unicode (`═══`) when the platform is Windows or when `PYTHONIOENCODING` doesn't include `utf-8` — Windows cmd in legacy code-page modes mojibakes Unicode boxes into junk. Cross-platform render check is part of the manual test plan.

6. **AC6 — README + dist-README updated.** README.md's Standalone Deployment section already names the port (added in the 0.9.0 README polish commit). Update `scripts/dist-README.md` to mention the new banner, the `LOG_FORMAT` knob, and the `OPEN_BROWSER` flag.

## Out of scope

- Replacing `python_json_logger` with a fancier formatter library — overkill; `logging.Formatter` with a manual format string is enough.
- Tray-icon / desktop-app wrapper. RoboScope stays a "open URL in your existing browser" tool for v1.
- A separate "first-run welcome" terminal flow (configure-on-first-start). Possible later, definitely not 0.9.1.

## Dev notes

- The JSON formatter wiring lives in `backend/src/main.py` — search for `pythonjsonlogger.JsonFormatter`. The toggle should be a single `if os.environ.get("LOG_FORMAT", "json") == "text":` switch around the formatter assignment.
- For the readiness banner, the cleanest hook is FastAPI's lifespan handler (the same one that already prints rf-mcp + scheduler startup messages). Add the banner print AFTER all subsystems report ready.
- The `PORT` env var is read in `backend/src/config.py` — reuse `settings.PORT` for the banner so the URL never drifts from the actual bind address.
- `webbrowser.open` is stdlib — no new dependency.
