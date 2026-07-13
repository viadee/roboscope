# Konzept: Behebung konzeptioneller Ungereimtheiten (Audit 2026-07-02)

Ergebnis eines 4-Achsen-Audits (Backend-Architektur, Frontend-Architektur, API-Vertrag/Security, Doku/Test-Drift). Umsetzung als eigenständige PR(s), Conventional Commits. **Nicht enthalten**: E2E-Use-Case-Abdeckung — die läuft als separater Workstream.

## Priorität 1 — Security & Korrektheit (HIGH)

### 1.1 `require_feature` schreibt keinen AuditLog vor dem 403
- **Wo**: `backend/src/governance/dependencies.py:50-60`
- **Problem**: Die Audit-Middleware überspringt Status ≥ 400 (`audit/middleware.py`). `require_package_op` und `gate_advanced_execution` schreiben deshalb selbst einen `AuditLog` (`action="blocked"`) + `db.commit()` **vor** dem Raise — `require_feature` nicht. Feature-Flag-Blocks über diesen Pfad sind unauditiert (genutzt z. B. von `execution/router.py:121` für `/modifiers`).
- **Fix**: `require_feature` analog zu `require_package_op` um `_audit_block(...)` + Commit vor dem `HTTPException(403)` erweitern. Test in `backend/tests/governance/` ergänzen (403 → AuditLog-Row mit `feature_disabled:<flag>` existiert).

### 1.2 WebSocket `/ws/runs/{run_id}` prüft keine Repo-Rolle
- **Wo**: `backend/src/main.py:508-551` (`_ws_authenticate` + `/ws/runs/{run_id}`)
- **Problem**: Nur JWT-Dekodierung, kein Active-User-Check, kein effektiver Rollen-Check auf dem Repo des Runs. Der SSE-Recorder-Endpoint (`recording/router.py:963-1070`) prüft dagegen Ownership/ADMIN. Ein beliebiger authentifizierter User kann Run-Output jedes Repos streamen.
- **Fix**: In `/ws/runs/{run_id}` nach Auth den Run laden, `repository_id` ermitteln und die effektive Rolle prüfen (gleiche Semantik wie `GET /runs/{run_id}` bzw. `require_effective_role_for_run`); zusätzlich `user.is_active` prüfen (wie SSE). Bei Fehlschlag `close(code=4403)`. Test: WS-Verbindung als user ohne Repo-Grant → Verbindung abgelehnt.

### 1.3 Frontend: 5× `new Date(backendFeld)` statt `parseBackendDate`
- **Wo**:
  - `frontend/src/views/StatsView.vue:90-91` (`lastRunFinished`, `lastAggregated`)
  - `frontend/src/views/EmergencyBypassView.vue:26` (`expires_at`)
  - `frontend/src/views/IdpProviderListView.vue` (`isDiscoveryCacheStale` → `discovery_cached_at`)
  - `frontend/src/views/TeamListView.vue:186` (`team.created_at`)
  - `frontend/src/views/EnvironmentsView.vue` (`docker_image_built_at`)
- **Problem**: Naive ISO-Strings vom Backend werden als Lokalzeit geparst → systematischer UTC-Offset-Fehler (dokumentierte Invariante, `utils/formatDate.ts::parseBackendDate` existiert genau dafür; `useBypassStatus.ts:68` macht es korrekt vor).
- **Fix**: Alle 5 Stellen auf `parseBackendDate()` umstellen. Optional: ESLint-Regel/Grep-Spec, die `new Date(` auf `.value`-/API-Feldern anmeckert, ist nice-to-have, kein Muss.

### 1.4 Flow-Editor-E2E-Fixtures verletzen die „≥2 Testcases“-Regel
- **Wo**: 9 Specs seeden nur 1 Testcase: `flow-editor-settings`, `flow-editor-control-structures`, `flow-editor-template`, `flow-editor-add-control-structures`, `flow-editor-bdd`, `flow-editor-add-arg`, `flow-editor-env-vars`, `flow-editor-libdoc-keywords`, `flow-editor-resource-ux` (alle unter `e2e/tests/`).
- **Problem**: Die dokumentierte Regel (CLAUDE.md) existiert, weil der Deep-Form-Watcher-Reset (`activeItemIndex = 0`) bei 1 Testcase unsichtbar ist. Diese Fixtures können die Regression nicht fangen.
- **Fix**: Jede Fixture um einen zweiten (trivialen) Testcase erweitern; wo der Test auf einem bestimmten Case arbeitet, explizit den **zweiten** Case aktivieren, damit ein Reset-auf-0 sichtbar würde. Danach kompletten flow-editor-E2E-Satz grün laufen lassen.

## Priorität 2 — Konsistenz des Berechtigungsmodells (MEDIUM)

### 2.1 Uneinheitliche Rollen-Floors bei destruktiven Operationen
- `DELETE /repos/{id}` = `require_effective_role(ADMIN)` (`repos/router.py:161`), aber `DELETE /recordings/{id}` = globales `require_role(EDITOR)` (`recording/router.py:101`). Recording-v2-Sessions prüfen bereits repo-scoped (`recording/router.py:421`), v1-Endpoints nicht.
- **Fix**: Recording-Endpoints (v1) auf repo-scoped effektive Rollen umstellen (Delete mindestens EDITOR auf dem zugehörigen Repo). Kein globales `require_role` mehr für repo-gebundene Ressourcen.

### 2.2 `POST /runs/cancel-all` nutzt globale Rolle
- **Wo**: `execution/router.py:775` (global `require_role(RUNNER)`), während `POST /runs/{id}/cancel` repo-scoped prüft (`:760`).
- **Fix**: `cancel-all` entweder auf ADMIN anheben **oder** auf die Runs filtern, für deren Repos der User effektive RUNNER-Rolle hat. Empfehlung: Filtern (verhält sich für Admins identisch).

### 2.3 Fehlende In-Flight-Guards für teure Hintergrund-Tasks
- **Wo**: Docker-Build `environments/router.py:290`, Repo-Sync `repos/router.py:240` — beide dispatchen bedingungslos; die Keyword-Introspection hat als Vorbild einen 120s-Guard (`environments/router.py:500-505`).
- **Fix**: Gleiches Muster übernehmen: Status `building`/`syncing` + `updated_at < N s` → 409/No-op statt Doppel-Dispatch. Commit-before-dispatch-Regel beachten.

### 2.4 Schedule-Trigger-Pfad absichern (präventiv)
- `Schedule.advanced_config`/`variables` (`execution/models.py:94`) werden geschrieben, aber nie gelesen — es existiert kein Trigger. **Fix**: Kommentar am Modell + ein Test/TODO, der festschreibt: ein künftiger Schedule→Run-Pfad MUSS durch `gate_advanced_execution` laufen (sonst Code-Exec-Bypass). Kein Verhalten ändern.

### 2.5 WS-/SSE-Auth-Asymmetrie dokumentieren bzw. angleichen
- `/ws/notifications` streamt an jeden validen Token-Inhaber ohne Active-Check; SSE prüft Ownership + `is_active` + 409 bei Zweitverbindung. **Fix**: mindestens `is_active`-Check in `_ws_authenticate` ergänzen (Rest von 1.2 abgedeckt). Die `^/ws/`-Audit-Exemption in `audit/middleware.py:22` mit Kommentar versehen: State-ändernde WS-Ops sind verboten, solange sie nicht selbst auditieren.

## Priorität 3 — Typ-/Vertragsdrift (LOW)

### 3.1 `RobotStep`-Drift: `trailingComment` fehlt in `flowConverter.ts`
- `robotTextIO.ts:44-63` hat `trailingComment?: string`, die Zwillingsdeklaration in `flow/flowConverter.ts:37-68` nicht. **Fix**: Feld nachziehen + prüfen, ob `cloneStep()` es kopieren muss (String, kein Array — einfache Übernahme). Dokumentierte Regel: neue Felder immer in BEIDE Deklarationen.

### 3.2 `RunModifier.kind` ohne `'listener'`
- `frontend/src/api/execution.api.ts:174` deklariert `kind: 'prerun' | 'prerebot'`, Backend liefert auch `listener` (`execution/modifiers/registry.py:79`), `ExecutionView.vue:296` filtert bereits darauf. **Fix**: Union um `'listener'` erweitern, lokalen Breittyp (`kind: string`) in `ExecutionView.vue:138` auf den API-Typ zurückführen.

## Bereits behoben (nicht erneut anfassen — nur zur Kenntnis)

### B.1 HEAL-VENDORED-Lücke: normal erstellte Umgebungen bekamen keinen Heal-Seed
- **Gefunden über** `heal-toggle.spec.ts` (E2E-Workstream 2026-07-02, deterministisch rot — kein Timing).
- **Ursache**: `POST /environments` legte nur die DB-Zeile an; `create_venv` (der einzige Pfad, der `_install_vendored_heal_into_venv` aufruft) wurde nur von `/setup-default` dispatcht. Die Venv entstand lazy bei der ersten Paket-Installation (`_install_package_inner`) — ohne Heal-Seed.
- **Fix (in dieser Session committet auf dem E2E-Branch)**: (1) `environments/router.py::add_environment` dispatcht jetzt eager `create_venv` (mit `db.commit()` VOR dem Dispatch), (2) der Lazy-Venv-Erstellungspfad in `tasks.py::_install_package_inner` seedet Heal ebenfalls (frische Venv = Day-One-Regel; die „nicht re-adden nach User-Remove"-Regel betrifft nur EXISTIERENDE Venvs). Gepinnt durch `tests/environments/test_router.py::test_create_environment_dispatches_venv_creation`; `TestCreateEnvironment` hat jetzt eine autouse-Fixture, die `dispatch_task` mockt (sonst erzeugen Unit-Tests echte Venvs unter `~/.roboscope/venvs`).

## Abnahme
- `make test` (Backend) + `vue-tsc` + Frontend-Unit-Tests + betroffene E2E-Specs grün.
- Neue/angepasste Gates: AuditLog-Test für 1.1, WS-Reject-Test für 1.2.
- i18n: Es entstehen keine neuen User-Strings (reine Backend-/Typ-Fixes) — falls doch (z. B. 409-Toast bei 2.3), EN/DE/FR/ES pflegen.
