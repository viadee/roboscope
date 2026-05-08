---
stepsCompleted: ['step-01-init', 'step-02-context', 'step-03-starter', 'step-04-decisions', 'step-05-patterns', 'step-06-structure', 'step-07-validation', 'step-08-complete']
lastStep: 8
status: 'complete'
completedAt: '2026-04-15'
inputDocuments:
  - _bmad-output/planning-artifacts/prd.md
  - _bmad-output/project-context.md
  - _bmad-output/project-docs/index.md
  - _bmad-output/project-docs/project-overview.md
  - _bmad-output/project-docs/source-tree-analysis.md
  - _bmad-output/project-docs/backend-auth-deep-dive.md
  - _bmad-output/project-docs/data-models-backend.md
  - _bmad-output/project-docs/api-contracts-auth.md
  - CLAUDE.md
workflowType: 'architecture'
project_name: 'roboscope'
user_name: 'Thomas'
date: '2026-04-14'
---

# Architecture Decision Document

_This document builds collaboratively through step-by-step discovery. Sections are appended as we work through each architectural decision together._

## Project Context Analysis

### Requirements Overview

**Funktionale Anforderungen:** 50 FRs in 8 Capability-Bereichen — IdP-Konfiguration (6), SSO-Auth (7), Teams & Membership (9), Access Control & Role Resolution (8), First-Login & Onboarding (6), Resilience & Outage (5), Deprovisioning (4), Audit (4), Lokalisierung (1). Alle FRs sind verbindlicher Capability Contract; jede Architekturkomponente muss auf mindestens eine FR rückführbar sein.

**Nicht-funktionale Anforderungen (architekturformend):**

- **Sicherheit:** Fernet-verschlüsselte Client-Secrets, PKCE/state/nonce mit ≥128 Bit Entropie und 10-Min-TTL, `return_to`-Origin-Validierung, id_token sofort verwerfen, **TLS 1.2+** Pflicht, IP-Ratenlimitierung, 24-h-Max für Emergency-Bypass.
- **Reliability:** IdP-Ausfall darf laufende Sessions nicht invalidieren (stateless JWT bleibt gültig); **null Netzwerk-Calls beim App-Boot**; IdP-Discovery 24 h DB-gecacht, lazy refreshed via APScheduler.
- **Performance:** SSO-Round-Trip < 5 s; Group-Sync ≤ 500 ms bei 50 IdP-Gruppen; Dry-Run < 10 s mit Phasen-spezifischem Timeout.
- **Deployability:** `uv`-gepinnte Deps; Windows-Offline-ZIP muss grün builden; **keine `xmlsec`-C-Extension** — expliziter Scope-Gate gegen SAML-Pullback.
- **Accessibility:** WCAG 2.1 AA auf allen neuen UI-Flächen; Login voll tastaturbedienbar; `aria-label` in EN/DE/FR/ES.
- **Integration:** OpenID Connect Core 1.0 + Authorization Code Flow mit PKCE; bestehende `rbs_…`-API-Tokens unverändert funktionsfähig.

**Scale & Complexity:**

- Primärer technischer Bereich: selbst-gehostete Multi-Part-Webanwendung (FastAPI sync Backend + Vue 3 SPA + optionale Chrome MV3 Extension).
- Komplexitätsgrad: **medium-high** — Brownfield-Integration mit bestehenden `User` / `ApiToken` / `ProjectMember` / `AuditLog`-Primitiven; Drei-Layer-Role-Resolution (global / Team / Project); transaktionale Semantik unter `ThreadPoolExecutor(max_workers=1)`; Offline-Boot-Invariante; Multi-Locale-UI.
- Geschätzte neue Architekturkomponenten: 5 neue Modelle (`IdentityProvider`, `Team`, `TeamMember`, `IdPGroupMapping`, `OidcLoginAttempt`), 1 modifiziertes (`Repository.team_id`), ~24 neue Endpoints, 1 neuer SSO-Auth-Pfad, 1 Emergency-Bypass-Subsystem, 1 First-Login-Flow.

### Technical Constraints & Dependencies

**Stack-Bindungen (unveränderlich):**

- Python 3.12+ sync FastAPI + SQLAlchemy 2.0 sync + Pydantic v2.
- `uv` für alle venv/pip-Operationen via `environments/venv_utils.py` — kein direktes `pip` oder `python -m venv`.
- In-process `ThreadPoolExecutor(max_workers=1)` via `task_executor.dispatch_task()` — kein Redis/Celery. Login-Time-Group-Sync läuft **inline, nicht dispatched**.
- SQLite (dev) / PostgreSQL (prod); identische Test-Suite; Alembic-Migrationen rollback-kompatibel innerhalb des Milestones.
- Offline-only Statik: kein CDN, keine Google Fonts.
- vue-i18n mit `@|{}`-Escaping — Prod-Build bricht sonst mit SyntaxError.

**Neue Dependencies (zu spezifizieren in späteren Schritten):**

- OIDC-Library: `authlib` (Kandidat — kein `xmlsec`-Bedarf, sync-freundliche API, PKCE-Support).
- Optional: `httpx` (falls nicht bereits im Stack) für Discovery/JWKS-Fetches mit TLS-1.2+-Enforcement.

**Bestehende Primitiven, auf denen Phase 4 aufbaut:**

- `User(email, username, hashed_password, role, is_active, last_login_at)` — `email` wird zum SSO-Verknüpfungsschlüssel.
- `Role` StrEnum: VIEWER(0) / RUNNER(1) / EDITOR(2) / ADMIN(3) — keine Änderung.
- `ApiToken(user_id, role)` — bleibt unverändert; `role` weiterhin gegen `User.role` (global) gecappt, nicht gegen effective_role.
- `ProjectMember(user_id, repository_id, role)` — wird Teil der `MAX()`-Resolution.
- `AuditLog` + `AuditMiddleware` — captures Phase-4-Events automatisch.
- Auth-Dependency `get_current_user` — akzeptiert JWT *und* API-Token transparent; muss nach Phase 4 `User.is_active` bei jedem Request prüfen (FR42).
- Fernet via `src/encryption.py` und `SECRET_KEY` — `is_secret=True`-Pattern für `IdentityProvider.client_secret_encrypted`.
- APScheduler (24 h) — piggy-back für IdP-Discovery-Cache-Refresh und Emergency-Bypass-Auto-Expire.

### Cross-Cutting Concerns Identified

1. **Auth im Request-Pfad.** `get_current_user`-Dependency ist die einzige Modifikationsstelle für SSO-Session-Validierung + `is_active`-Recheck. JWT-Form muss identisch bleiben (FR11, NFR28).
2. **Role Resolution als Single Source of Truth.** Neue Funktion `effective_role(user, repo) = MAX(global, team, project)` wird von allen repo-scoped Endpoints (`/repos`, `/runs`, `/reports`, `/explorer`, `/stats`) konsumiert. Bestehende `require_role`-Checks müssen auf den Resolver umgestellt werden.
3. **Strukturierte Audit-Details.** Neue Event-Typen (SSO-Login, IdP-Config-CRUD, Bypass, Team-CRUD, Membership-Sync, Token-Reassign) brauchen einen Event-Typ-Katalog mit strukturiertem `detail`-JSON für SIEM-Konsum (NFR29).
4. **Transaktionale Semantik des Login-Time-Sync.** Group-Sync committet *vor* JWT-Ausgabe in derselben Transaktion; Idempotenz über `(user_id, login_session_id)`.
5. **Boot-vs-Runtime-Netzwerk-Invariante.** App-Boot = 0 outbound. IdP-Discovery = lazy runtime, 24-h-gecacht, APScheduler-Refresh. "Expired-but-usable"-UI-State (NFR15).
6. **i18n-Korridor.** Alle neuen User-Facing-Strings in 4 Locales, inkl. Error-Copy, Admin-UI, Handoff-Artifact; Prod-Build-Regression-Test als Gate.
7. **Accessibility-Korridor.** WCAG 2.1 AA auf allen neuen UI-Flächen.
8. **Dependency-Hygiene.** Keine neue Dep darf `xmlsec` oder andere Windows/slim-Docker-inkompatible C-Extensions ziehen. Scope-Gate gegen SAML-Pullback in v1.
9. **Migration-Rollback-Kompatibilität.** Phase-4-Migrationen sind forward+backward-compatible innerhalb des Milestones; neue Phase-4-Zeilen dürfen beim Rollback verloren gehen, `User` / `ApiToken` / `Repository` / `AuditLog` bleiben unangetastet.

## Starter Template Evaluation

### N/A — Brownfield Phase

Phase 4 ist eine Erweiterung der bestehenden RoboScope-Codebase. Es gibt keine Starter-Template-Auswahl; der Stack ist etabliert und in `CLAUDE.md` und `project-context.md` (Kategorie 1) mit Begründung dokumentiert.

**Stack-Bindungen (unveränderlich für Phase 4):**

- **Backend:** Python 3.12+ · FastAPI (sync) · SQLAlchemy 2.0 (sync) · Pydantic v2 · `uv`
- **Frontend:** Vue 3.5 · Pinia · Vue Router 4 · Vite 7 · TypeScript strict · vue-i18n v10
- **DB:** SQLite (dev) / PostgreSQL (prod) · Alembic-Migrationen
- **Auth-Primitiven:** JWT (PyJWT) · `rbs_…` API-Tokens · bcrypt · Fernet
- **Background-Work:** in-process `ThreadPoolExecutor(max_workers=1)` — kein Redis/Celery
- **Scheduler:** APScheduler
- **Testing:** pytest (~555) · Vitest · Playwright (217)
- **Deployment:** Docker Compose (prod) · Offline-ZIP (Linux/macOS/Windows)

**Einzige neue Dependency in Scope für Phase 4:** OIDC-Library (Auswahl in Step 4 — Architectural Decisions). Primärer Kandidat: `authlib` — kein `xmlsec`-Bedarf, sync-freundliche API, nativer PKCE-Support, via `uv add` pinnbar und Windows-Offline-ZIP-kompatibel.

**Initialization Command:** keiner. Phase-4-Arbeit beginnt mit einer Alembic-Migration für die neuen Modelle (`IdentityProvider`, `Team`, `TeamMember`, `IdPGroupMapping`, `OidcLoginAttempt`, plus `Repository.team_id` und `Settings`-Erweiterung) — das ist die erste Story des Epic.

## Core Architectural Decisions

### Decision Priority Analysis

**Bereits entschieden durch bestehenden Stack (Brownfield, nicht re-diskutiert):** DB (SQLite dev / Postgres prod), API-Stil (REST), Frontend-State (Pinia), Routing (Vue Router 4), Styling (CSS Custom Properties in `main.css`), Hosting (Docker Compose + Offline-ZIP), Testing-Framework, i18n (vue-i18n v10), Secrets-Pattern (Fernet via `SECRET_KEY`), Audit (via `AuditMiddleware`), Background-Work (`ThreadPoolExecutor(max_workers=1)`).

**Kritisch (blockieren Implementation):**

- OIDC-Library-Auswahl
- Role-Resolution-Semantik
- OIDC-State-Lifecycle und Cleanup
- JWT-Form-Kompatibilität mit bestehenden API-Tokens
- Migration-Strategie mit Rollback-Kompatibilität

**Wichtig (formen Architektur):**

- Admin-UI-Routing und Struktur der Pinia-Stores
- OIDC-Discovery-Caching-Strategie
- Strukturiertes Audit-Event-Detail-Schema
- Fehlerbehandlungs-Konventionen in `/auth/sso/*`-Endpoints
- Umstellungs-Strategie von `require_role` auf `require_effective_role`

**Aufgeschoben (Post-MVP, in PRD-Non-Goals festgehalten):** SAML 2.0, SCIM 2.0, Refresh-Tokens/Silent-Renew, Multi-Team-per-Repo.

### Data Architecture

| Entscheidung | Wahl | Begründung |
|---|---|---|
| **Neue Modelle** | `IdentityProvider`, `Team`, `TeamMember`, `IdPGroupMapping`, `OidcLoginAttempt` | Minimaler Satz für FR1–FR22; `OidcLoginAttempt` hält state/nonce/pkce_verifier single-use, 10-Min-TTL. |
| **Modifiziertes Modell** | `Repository.team_id: int \| None` FK (nullable) | Eine Team-Zuordnung pro Repo (PRD Non-Goal: Multi-Team-per-Repo). `NULL` = unscoped/global. |
| **`Settings`-Erweiterung** | `sso_emergency_bypass` (bool), `sso_emergency_bypass_expires_at` (datetime), `deprovision_retention_days` (int, default 90) | Neue Env-Defaults `SSO_EMERGENCY_BYPASS_MAX_HOURS=24`, `DEPROVISION_RETENTION_DAYS=90`. |
| **Migration-Strategie** | Alembic, additive-only, rollback-kompatibel innerhalb Milestone | NFR17: neue Phase-4-Zeilen dürfen beim Rollback verloren gehen; Kern-Entitäten (`User` / `ApiToken` / `Repository` / `AuditLog`) bleiben unangetastet. |
| **SCIM-Forward-Compat** | `external_id: str \| None` auf `Team` und `TeamMember` (nullable, reserviert, nicht exposed in v1) | Phase 5 SCIM ohne Schema-Migration möglich. |
| **`TeamMember.source`** | Enum `manual` / `idp_group_sync` | FR20: IdP-driven Changes dürfen manuelle Grants nicht überschreiben. Discriminator für Sync-Diff. |
| **Caching-Strategie** | DB-basierter Discovery-Cache (`IdentityProvider.discovery_cache_json` + `discovery_cached_at`) — kein Redis | Konsistent mit „no Redis/Celery"; APScheduler (24 h) piggy-backt. |

### Authentication & Security

| Entscheidung | Wahl | Begründung |
|---|---|---|
| **OIDC-Library** | **`authlib`** (gepinnt via `uv add`, aktuelle stabile Version) | NFR20: sync-freundliche API, natives PKCE, kein `xmlsec`-Bedarf, Windows-Offline-ZIP-kompatibel, aktiv gepflegt. Alternativen (`python-jose`+manueller Flow, `requests-oauthlib`) verworfen wegen fehlendem Discovery/PKCE-Komfort bzw. alter Maintenance. |
| **OIDC-Flow** | Authorization Code Flow **mit verpflichtendem PKCE** | NFR26; schützt gegen Auth-Code-Interception. |
| **State/Nonce/PKCE-Storage** | `OidcLoginAttempt`-Tabelle mit 10-Min-TTL, Cleanup via APScheduler | Konsistent mit „keine Redis"; einmal-verwendbar (Row-Delete nach Callback); NFR6. |
| **JWT-Form** | **unverändert** gegenüber Phase 3; id_token wird nach Claim-Extraktion verworfen | FR11, NFR9: keine Foreign-Token-Material im System; bestehender `get_current_user`-Code unverändert für Token-Konsum. |
| **`get_current_user`-Erweiterung** | Zusätzlicher `User.is_active`-Recheck pro Request | FR42: sofortige Session-Invalidation bei Deaktivierung. Minimal-invasive Erweiterung; User-Objekt wird ohnehin geladen. |
| **Role Resolution** | `effective_role(user, repo) = MAX(user.role, team_role_for(user, repo), project_member_role(user, repo))` in neuer `src/auth/permissions.py`-Funktion | FR23, FR24; Winstons Empfehlung. Additiv (Grant-only), keine Deny-Semantik. Single Source of Truth. |
| **Umstellung `require_role` → `require_effective_role`** | **Schritt-für-Schritt** — beide Funktionen koexistieren während der Umstellung; Endpoint-by-Endpoint-Migration über eigene Stories. | Senkt Regressions-Risiko. Story-Sequenz wird länger, aber jede Einzel-Migration ist klein und testbar. Entschieden: 2026-04-14 (Thomas). |
| **API-Token-Cap** | `ApiToken.role` bleibt gegen `User.role` (global) gecappt, **nicht** gegen `effective_role` | NFR28, FR30: keine CI/CD-Breaking-Changes. Tokens sind Maschinen-Identitäten, keine Human-Sessions. |
| **Client-Secret-Storage** | Fernet-verschlüsselt in `IdentityProvider.client_secret_encrypted: LargeBinary` via existierendem `is_secret=True`-Pattern in `src/encryption.py` | NFR5; keine neue Infrastruktur. |
| **`return_to`-Validation** | Whitelist gegen App-Origin in `/auth/sso/{idp_id}/login` | NFR7: Open-Redirect-Schutz. Fallback auf `/` bei invalider Target. |
| **Rate-Limiting** | **DB-basierter Counter** (neue Tabelle oder In-Memory-Struktur mit DB-Persistenz); kein `slowapi` | Single-Instance-Deployment; keine neue Dependency nötig. Entschieden: 2026-04-14 (Thomas). Implementierung: Zähler pro (IP, Window) mit APScheduler-Cleanup. |
| **Emergency-Bypass-Scope** | **Eine** installationsweite Toggle, maximale Dauer 24 h, auto-expire via APScheduler | FR39–41, NFR11. Per-User-Override explizit gestrichen (PRD Non-Goal). |
| **Bootstrap-Admin** | `admin@roboscope.local` / lokales Passwort bleibt **immer** aktiv, unabhängig von SSO-Konfiguration und Bypass-State | FR8, NFR12. Break-Glass-Invariante. |
| **TLS-Enforcement** | Nginx-Config ≥ TLS 1.2; Backend-HTTP-Client (Kandidat: `httpx`) setzt Min-Version 1.2 für outbound Calls zu IdPs | NFR13. |

### API & Communication Patterns

| Entscheidung | Wahl | Begründung |
|---|---|---|
| **API-Stil** | REST (bestehendes Muster); OpenAPI-Docs via FastAPI-Auto-Generation | Konsistent mit bestehenden `/api/v1/*`-Endpoints. |
| **Neue Router-Module** | `src/auth/sso_router.py`, `src/auth/idp_router.py`, neues Domain-Modul `src/teams/` (mit `models.py`, `service.py`, `router.py`), Erweiterung `src/auth/router.py` für `/api-tokens/{id}/reassign` und `/settings/sso-emergency-bypass` | Domain-getrennt; `teams/` parallel zu `auth/`, `repos/`, `reports/` etc. |
| **OIDC-Callback** | **Ein** geteilter `GET /auth/sso/callback?code&state` — IdP wird über `state`-Lookup in `OidcLoginAttempt` identifiziert | Ein Redirect-URI pro Installation statt pro IdP; vereinfacht IdP-Admin-Handoff (Ingrid bekommt eine URL, nicht drei). |
| **Public Endpoints** | `/auth/sso/providers` (Liste für Login-UI), `/auth/sso/{idp_id}/login`, `/auth/sso/callback` | Vor `get_current_user`-Dependency; FastAPI-Dependency-Override pro Endpoint. |
| **Error-Handling** | Bestehendes `HTTPException` + strukturiertes `detail: {code, message, localization_key}` für User-facing-Fehler | Ermöglicht Frontend-Lokalisierung aus Backend-Fehlern; FR38 verlangt lokalisierte Fehlermeldungen. |
| **Audit-Event-Schema** | Neuer `AuditEventType`-Enum (`sso.login.success`, `sso.login.failure`, `idp.created`, `team.created`, `team_member.synced_from_idp`, `sso.emergency_bypass.activated`, usw.) mit strukturiertem `detail: dict[str, Any]` | NFR29: SIEM-tauglich. Enum zentralisiert in `src/audit/event_types.py`. |
| **WebSocket** | Keine neuen Channels nötig | Phase 4 ist request-response only; keine Live-Updates. |

### Frontend Architecture

| Entscheidung | Wahl | Begründung |
|---|---|---|
| **Neue Pinia-Stores** | `stores/sso.ts`, `stores/team.ts`, `stores/idpAdmin.ts`, `stores/emergencyBypass.ts` | Domain-getrennt konsistent mit bestehender Store-Struktur. |
| **Neue Views** | `LoginView.vue` (erweitert), `FirstLoginView.vue`, `TeamListView`, `TeamDetailView`, `IdpProviderListView`, `IdpProviderEditView` (inkl. Dry-Run-Panel), `SsoErrorView` | 1 View pro Haupt-Screen; Routing via Vue Router 4. |
| **Routing-Guards** | Neuer Guard `requireEffectiveRole(role)` konsumiert Backend-berechneten `effective_role` aus User-Context; ersetzt statische `requireRole` für repo-scoped Routes | FR24: SSOT liegt im Backend; Frontend cached pro Navigation. |
| **First-Login-Detection** | Backend setzt `first_login_complete: bool` auf User; Frontend-Guard redirectet auf `/welcome` wenn `false`; View setzt Flag auf `true` bei Dismiss | FR31–FR34; einfacher State statt komplexem Onboarding-Wizard. |
| **Read-Only-Affordances** | Neue Prop `readOnly: boolean` auf `FlowEditor.vue`; computed aus `effective_role < EDITOR` | FR25, FR35: disabled-with-tooltip Edit, Read-Only-Banner. |
| **i18n-Lock-Zeitpunkt** | Alle Translation Keys in Sprint 1 gelockt; Tech-Writer-Pass in Sprint 2 parallel | Gegen vue-i18n `@\|{}`-Escaping-Regression; NFR19 Prod-Build-Test als CI-Gate. |
| **Handoff-Artifact-Format** | **Markdown + PDF**. PDF-Rendering: `reportlab` (pure Python, keine C-Deps). Entschieden: 2026-04-14 (Thomas). | FR5; `weasyprint` verworfen wegen C-Deps und Offline-ZIP-Risiko; `reportlab` ist Windows/slim-Docker-kompatibel und mit `uv` pinnbar. |

### Infrastructure & Deployment

| Entscheidung | Wahl | Begründung |
|---|---|---|
| **Hosting** | Unverändert: Docker Compose (prod), Offline-ZIP | Keine neuen Services. |
| **Neue Env-Variablen** | `SSO_EMERGENCY_BYPASS_MAX_HOURS` (default 24), `DEPROVISION_RETENTION_DAYS` (default 90) | Konfigurierbar per Installation; Defaults in PRD festgelegt. |
| **APScheduler-Erweiterungen** | Bestehender 24 h-Scheduler wird piggy-backt für: IdP-Discovery-Cache-Refresh, Emergency-Bypass-Auto-Expire, `OidcLoginAttempt`-TTL-Cleanup, `TeamMember`-Retention-Cleanup (90 d), Rate-Limit-Counter-Cleanup | Kein neuer Scheduler-Service; NFR15. |
| **CI-Gates (neu)** | (a) Prod-Frontend-Build-Test (vue-i18n Escape-Regression), (b) Offline-Boot-Network-Isolation-Smoke-Test, (c) Windows-Offline-ZIP-Build-Success, (d) Mock-OIDC-Fixture-basierte Integration-Tests | NFR4, NFR14, NFR18, NFR20. |
| **Nginx-Config-Änderung** | Min-TLS-Version 1.2; Cipher-Suite-Härtung (konservative Modern-Profile-Auswahl) | NFR13. Shipping in `docker/nginx.conf`. |
| **Monitoring** | Nutzt bestehendes Logging; neue Audit-Events strukturiert JSON-loggbar für SIEM-Ingest ohne zusätzliche Instrumentation | NFR29; Phase 5 bringt Prometheus. |

### Decision Impact Analysis

**Implementation Sequence (empfohlene Story-Reihenfolge):**

1. **Alembic-Migration** für 5 neue Modelle + `Repository.team_id` + `Settings`-Erweiterung + Rate-Limit-Counter-Tabelle — rollback-kompatibel.
2. **`effective_role()`-Funktion** in `src/auth/permissions.py`; `require_effective_role`-Dependency neu neben existierendem `require_role`. Kein Endpoint-Switch in dieser Story.
3. **Schrittweise Umstellung**: pro Sub-Story ein Endpoint-Prefix (`/runs` → `/reports` → `/explorer` → `/repos` → `/stats`) von `require_role` auf `require_effective_role`. Jede Sub-Story hat eigene Regressions-Tests und eigene PR.
4. **Mock-OIDC-Fixture** in `backend/tests/fixtures/mock_oidc.py` — wird in #5, #6, #7, #13 wiederverwendet.
5. **IdP-Admin-Router** (`IdentityProvider`-CRUD + Dry-Run) — rein backend-seitig, testbar ohne echte IdP.
6. **OIDC-Login-Flow** mit Mock-OIDC-Fixture — SSO-Login funktionsfähig, noch ohne Team-Sync.
7. **Team-Model + Admin-Router** (`Team`, `TeamMember` CRUD, `IdPGroupMapping`) — ohne Sync.
8. **Login-Time Group-Sync** — inline-transaktional, Idempotenz-Key.
9. **Frontend Login-Seite** + SSO-Buttons + Error-Copy.
10. **Frontend Admin-UI** (IdP-CRUD + Dry-Run-Panel + Team-Management).
11. **First-Login-View** + Read-Only-Affordances im FlowEditor.
12. **Emergency-Bypass** + Outage-Error-Copy.
13. **Offboarding** (API-Token-Reassign, `is_active`-Propagation, Retention-Cleanup).
14. **Handoff-Artifact-Generator** (`reportlab` + Markdown).
15. **i18n-Pass** (EN/DE/FR/ES für alle neuen Strings, Prod-Build-Test).
16. **E2E-Tests** (7 Playwright-Specs).

**Cross-Component Dependencies:**

- `effective_role()` (#2) muss vor Team-Sync (#8) fertig sein, sonst kein Permission-Check-Target für Team-Rollen.
- Endpoint-Umstellungen (#3) können parallel zu #5–#8 laufen, sind aber blocking für #10 (Frontend benötigt konsistente Role-Checks).
- Mock-OIDC-Fixture (#4) wird früh gebaut, einmal stabilisiert.
- Migration (#1) ist strict blocking für alle Backend-Stories; Frontend-Stories (#9–#11) können mit Stub-APIs parallel beginnen.
- i18n-Pass (#15) hängt an gelockten Translation-Keys ab Sprint 1 — keine späten Copy-Änderungen.
- Handoff-Artifact (#14) hängt an IdP-Admin (#5) und Callback-URL-Naming-Lock (PRD Open Risk R4).

## Implementation Patterns & Consistency Rules

### Pattern Categories Defined

**Autoritative Quellen (nicht re-entschieden in Phase 4):**

- `_bmad-output/project-context.md` — 202 Regeln in 7 Kategorien (Tech-Stack-Invarianten, Critical Implementation Rules, Coding Style, Testing Rules, Workflow Rules, Critical Don't-Miss-Rules, Usage Guidelines).
- `CLAUDE.md` — Architekturübersicht, Conventions, Gotchas (`uv`-only, offline-only, vue-i18n-Escaping, `db.commit()` before `dispatch_task()`, WebSocket-Broadcast-Invariante, Audit-Middleware).

**In Phase 4 neu entschiedene Patterns (Delta):** Die nachfolgenden Abschnitte ergänzen die autoritativen Quellen gezielt für neuen Phase-4-Code. Bei Konflikt gewinnt `project-context.md`.

### Naming Patterns (Delta)

**Database Naming:**

- Tabellen (snake_case, Plural, konsistent mit bestehenden): `identity_providers`, `teams`, `team_members`, `idp_group_mappings`, `oidc_login_attempts`, `rate_limit_counters`.
- Spalten: snake_case. FKs: `<entity>_id` (Singular). Beispiel: `team_id`, `idp_id`, `user_id`.
- Indizes: `ix_<table>_<column>` via SQLAlchemy `Index()`; zusammengesetzte Unique-Constraints: `uq_<table>_<col1>_<col2>`.

**API Naming:**

- Pfade plural, lowercase, konsistent mit bestehenden `/api/v1/*`-Mustern. Beispiele: `/teams`, `/teams/{id}/members`, `/auth/sso/providers`, `/auth/idp-providers`, `/group-mappings`.
- Path-Parameter: `{id}`.
- Query-Parameter: snake_case (`?include_disabled=true`).
- JSON-Felder: **snake_case** (konsistent mit bestehenden Backend-Responses).

**Code Naming (Backend):**

- OIDC-Flow-Funktionen: `initiate_sso_login`, `handle_sso_callback`, `_extract_claims`, `_sync_team_memberships`. Underscore-prefixed für privat.
- Audit-Event-Konstanten: zentral in `src/audit/event_types.py` als `AuditEventType` StrEnum. Namensschema: `<domain>.<entity>.<action>` — `sso.login.success`, `idp.config.created`, `team.member.synced`.

**Code Naming (Frontend):**

- Pinia-Stores: kebab-case Dateinamen, camelCase Exports — `stores/sso.ts`, `stores/team.ts`, `stores/idpAdmin.ts`, `stores/emergencyBypass.ts`.
- Views: PascalCase mit Suffix `View` — `FirstLoginView.vue`, `IdpProviderEditView.vue`.

### Structure Patterns (Delta)

**Backend-Modul-Struktur für Phase 4:**

- **`src/auth/`** (existierend, erweitert): `sso_router.py`, `idp_router.py`, `permissions.py` (neu: `effective_role()`, `require_effective_role()`), `oidc_service.py` (Discovery, Token-Exchange, Claim-Extraction via `authlib`), `rate_limit.py` (DB-Counter).
- **`src/teams/`** (neu): `models.py`, `service.py`, `router.py`, `sync.py` (Login-Time Group-Sync).
- **`src/audit/event_types.py`** (neu): zentrale `AuditEventType` StrEnum.
- **Tests:** `backend/tests/auth/test_sso_*.py`, `backend/tests/teams/test_*.py`, `backend/tests/fixtures/mock_oidc.py` (geteilt).

**Frontend-View-Struktur:**

- `views/auth/` (neu): `FirstLoginView.vue`, `SsoErrorView.vue`.
- `views/admin/` (existierend, erweitert): `IdpProviderListView.vue`, `IdpProviderEditView.vue`.
- `views/teams/` (neu): `TeamListView.vue`, `TeamDetailView.vue`.
- `components/admin/DryRunPanel.vue` (neu, wiederverwendet).

**Migration-Ordnung:**

- Alle Phase-4-Migrationen haben vollständigen `down()`-Pfad (NFR17).

### Format Patterns (Delta)

**OIDC-Error-Response-Format** (alle `/auth/sso/*`-Endpoints):

```json
{
  "detail": {
    "code": "idp.unreachable" | "idp.credentials_invalid" | "idp.claim_missing" | "state.invalid" | "state.expired" | "return_to.invalid" | "idp.not_configured",
    "message": "Human-readable fallback in EN",
    "localization_key": "errors.sso.idp_unreachable",
    "context": { /* provider-specific detail JSON */ }
  }
}
```

- Frontend konsumiert `localization_key`; `message` ist Fallback.
- Interne Fehler folgen bestehendem HTTPException-Muster ohne `localization_key`.

**Audit-Event-Detail-Format** (NFR29):

```json
{
  "actor_user_id": 42,
  "actor_role": "ADMIN",
  "source_ip": "10.0.0.12",
  "target_entity_type": "Team" | "IdentityProvider" | "TeamMember" | "ApiToken" | "User",
  "target_entity_id": 7,
  "changes": { /* old→new delta, null für Creates/Deletes */ },
  "extras": { /* event-typ-spezifisch */ }
}
```

**Datum/Zeit:** ISO-8601 UTC mit `Z`-Suffix; `datetime.now(timezone.utc)` im Backend.

### Communication Patterns (Delta)

**Pinia-Store-Pattern:**

- Actions async; try/catch, setzen Store-internen `error: string | null`.
- Loading-State pro Action: `loadingProviders: boolean`, `loadingDryRun: boolean`. Kein globaler Spinner.
- State-Shape `reactive()`, direkte Mutation (Vue 3 Pinia-Convention).

**`effective_role`-State-Update:**

- Backend liefert `effective_roles: Record<repoId, Role>` als Teil der User-Session-Payload nach Login und bei Repo-Navigation-Refresh.
- Frontend cached pro Navigation; kein Live-Push. Stale-Fenster akzeptiert (NFR45).

**Audit-Event-Emission:**

- Middleware deckt POST/PUT/PATCH/DELETE automatisch ab.
- Nicht-HTTP-getriggerte Events (Login-Time-Group-Sync, Emergency-Bypass-Auto-Expire): explizit via `audit_service.log_event(event_type=AuditEventType.TEAM_MEMBER_SYNCED, detail=...)`.

### Process Patterns (Delta)

**Error-Recovery (OIDC):**

- `OidcLoginAttempt` bleibt bis TTL-Expiry auch bei Callback-Fehler — Debugging via `AuditLog`-Kreuzreferenz.
- Token-Exchange-Fehler: detaillierter `sso.login.failure`-Audit-Event; User sieht generische Fehlermeldung (keine IdP-Interna).
- Netzwerk-Timeout: distinkter Error-Code `idp.unreachable` vs. `idp.timeout` (FR38).

**Transaktionale Semantik (Login-Time-Sync, NFR3):**

- **Eine Transaktion** umfasst: User-Upsert, IdPGroupMapping-Lookup, TeamMember-Diff, Insert/Delete mit `source='idp_group_sync'`, Audit-Event, JWT-Issuance-Vorbereitung.
- Commit **vor** JWT-Response. Rollback → User sieht `sso.login.failure`, keine stale Teams.
- Idempotenz: `(user_id, login_request_id)` als Soft-Key; Retry innerhalb Fenster: No-Op.

**Read-Only-Affordances (Frontend):**

- Editierbare Komponenten (FlowEditor, Code-Editor, Admin-Forms) prüfen `effective_role` via Composable `useCanEdit(repoId)`:
  - EDITOR+: volle Funktionalität.
  - RUNNER: Run aktiv, Edit disabled-mit-Tooltip.
  - VIEWER: Read-Only-Banner oben, Edit disabled-mit-Tooltip, Run hidden.

**First-Login-Flow:**

- Backend: `User.first_login_complete: bool` default `False`.
- Frontend Router-Guard: wenn `user.first_login_complete === false` und Route ≠ `/welcome` → redirect `/welcome`.
- Dismiss: PATCH `/auth/me/first-login-complete`.

### Enforcement Guidelines

**All AI Agents MUST:**

1. Vor jeder Story das relevante `project-context.md`-Kapitel lesen (Cat. 1 für Stack-Pins, Cat. 2 für Implementation Rules, Cat. 4 für Testing).
2. Vor jedem Endpoint-Write in Phase-4-Code: `src/auth/permissions.py::effective_role()` für repo-scoped Checks verwenden, **nicht** `require_role` direkt.
3. Vor jedem neuen Audit-Event: Typ in `src/audit/event_types.py` als `AuditEventType` StrEnum registrieren, dann verwenden.
4. Vor jedem User-facing-String: in alle 4 Locale-Bundles (EN/DE/FR/ES) eintragen + `@|{}`-Escaping + Prod-Build lokal laufen lassen.
5. Vor jedem neuen Modell: Alembic-Migration mit funktionierendem `down()`.
6. Vor jedem PR-Merge: ~555 Backend-Tests + 217 Playwright-Tests lokal grün.
7. Bei Unsicherheit: `CLAUDE.md` "Critical patterns & gotchas"-Sektion prüfen, insbesondere `db.commit()` before `dispatch_task()`, `asyncio.run_coroutine_threadsafe` für WebSocket-Broadcasts aus BG-Threads, vue-i18n-Escaping.

**Pattern Enforcement:**

- **`project-context.md` als CI-gated Reference.** Verstöße im Code-Review mit Pattern-Zitat markieren.
- **Ruff + mypy strict** in CI; Pattern-Verstöße bei Naming/Typing brechen Build.
- **Prod-Frontend-Build-Test** in CI (NFR19) — fängt vue-i18n-Escape-Regressions.
- **Offline-Boot-Network-Isolation-Test** in CI (NFR14) — fängt versehentliche Outbound-Calls beim Boot.

**Pattern-Update-Prozess:**

- Änderungen am Phase-4-Delta → PR gegen diese Architektur-Datei + Review durch Owner.
- Änderungen an `project-context.md` → via `bmad-generate-project-context`-Skill oder direkte PR mit doppeltem Reviewer.

### Pattern Examples

**Good:**

```python
# src/auth/sso_router.py
from src.audit.event_types import AuditEventType
from src.auth.permissions import require_effective_role

@router.get("/sso/callback")
def sso_callback(code: str, state: str, db: Session = Depends(get_db)) -> RedirectResponse:
    attempt = _lookup_and_consume_attempt(db, state)  # deletes row on success
    try:
        claims = oidc_service.exchange_code(attempt, code)
    except OidcTimeoutError:
        audit_service.log_event(db, AuditEventType.SSO_LOGIN_FAILURE,
                                detail={"reason": "idp.unreachable", "idp_id": attempt.idp_id})
        raise HTTPException(502, {
            "code": "idp.unreachable",
            "message": "Identity provider unreachable",
            "localization_key": "errors.sso.idp_unreachable",
            "context": {"idp_id": attempt.idp_id}
        })
    user = _upsert_user(db, claims)
    _sync_team_memberships(db, user, claims["groups"])  # same txn
    db.commit()  # commit BEFORE JWT issuance
    jwt = issue_jwt(user)
    return RedirectResponse(url=attempt.return_to, headers={"Set-Cookie": f"jwt={jwt}"})
```

**Anti-Patterns:**

```python
# ❌ Don't: dispatch_task for group sync — creates stale RBAC on first post-login request
def sso_callback(...):
    user = _upsert_user(db, claims)
    db.commit()
    jwt = issue_jwt(user)
    dispatch_task(sync_teams_for_user, user.id, claims["groups"])  # ❌ race condition
    return RedirectResponse(...)

# ❌ Don't: build ad-hoc audit detail without event-type enum
audit_log.add("some-sso-event", f"user {user.email} logged in")  # ❌ unstructured

# ❌ Don't: use require_role for repo-scoped endpoint in Phase 4+ code
@router.get("/repos/{repo_id}/runs")
def list_runs(repo_id: int, user = Depends(require_role(Role.VIEWER))):  # ❌ ignores Team grants
    ...
```

## Project Structure & Boundaries

### Neue und modifizierte Dateien

```
roboscope/
├── backend/
│   ├── alembic/
│   │   └── versions/
│   │       └── NNNN_phase4_sso_and_teams.py         [NEU] Alembic-Migration
│   ├── src/
│   │   ├── auth/
│   │   │   ├── models.py                             [MOD] +IdentityProvider, +IdPGroupMapping, +OidcLoginAttempt
│   │   │   ├── schemas.py                            [MOD] +IdP-Pydantic-Schemas, +SSO-Flow-Schemas
│   │   │   ├── router.py                             [MOD] +POST /api-tokens/{id}/reassign, +bypass endpoints
│   │   │   ├── sso_router.py                         [NEU] GET /auth/sso/{providers,login,callback}
│   │   │   ├── idp_router.py                         [NEU] Admin IdP-CRUD + Dry-Run
│   │   │   ├── permissions.py                        [NEU] effective_role(), require_effective_role()
│   │   │   ├── oidc_service.py                       [NEU] authlib-Wrapper, Discovery, Token-Exchange
│   │   │   ├── dependencies.py                       [MOD] get_current_user: +is_active-Recheck
│   │   │   └── service.py                            [MOD] User-Upsert aus Claims
│   │   ├── teams/                                    [NEU Modul]
│   │   │   ├── __init__.py
│   │   │   ├── models.py                             Team, TeamMember
│   │   │   ├── schemas.py                            Team/TeamMember/GroupMapping Pydantic
│   │   │   ├── router.py                             /teams, /teams/{id}/members, /teams/import-from-idp-groups, /group-mappings
│   │   │   ├── service.py                            Team-CRUD, Membership-Management
│   │   │   └── sync.py                               Login-Time Group-Sync (inline transactional)
│   │   ├── audit/
│   │   │   ├── models.py                             [unchanged]
│   │   │   ├── middleware.py                         [unchanged — auto-captures POST/PUT/PATCH/DELETE]
│   │   │   ├── event_types.py                        [NEU] AuditEventType StrEnum
│   │   │   └── service.py                            [MOD] log_event() für non-HTTP Events
│   │   ├── users/
│   │   │   └── models.py                             [MOD] +first_login_complete: bool
│   │   ├── repos/
│   │   │   └── models.py                             [MOD] +Repository.team_id FK
│   │   ├── settings/
│   │   │   └── models.py                             [MOD] +sso_emergency_bypass, +sso_emergency_bypass_expires_at, +deprovision_retention_days
│   │   ├── rate_limit.py                             [MOD] +SSO-spezifischer per-IP-Counter
│   │   ├── encryption.py                             [unchanged — Fernet]
│   │   ├── task_executor.py                          [unchanged]
│   │   ├── main.py                                   [MOD] Router-Mounting + APScheduler-Job-Registrierung
│   │   └── config.py                                 [MOD] +SSO_EMERGENCY_BYPASS_MAX_HOURS, +DEPROVISION_RETENTION_DAYS
│   └── tests/
│       ├── fixtures/
│       │   └── mock_oidc.py                          [NEU] Geteilte Mock-OIDC-Provider-Fixture
│       ├── auth/
│       │   ├── test_sso_login.py                     [NEU]
│       │   ├── test_sso_callback.py                  [NEU]
│       │   ├── test_idp_admin.py                     [NEU]
│       │   ├── test_dry_run.py                       [NEU]
│       │   ├── test_effective_role.py                [NEU] table-driven MAX()-Tests
│       │   ├── test_emergency_bypass.py              [NEU]
│       │   ├── test_rate_limit_sso.py                [NEU]
│       │   └── test_api_token_reassign.py            [NEU]
│       └── teams/                                    [NEU Testpaket]
│           ├── test_team_crud.py
│           ├── test_team_sync.py                     Transaktionalität, Idempotenz
│           ├── test_group_mapping.py
│           └── test_import_from_idp_groups.py
├── frontend/
│   ├── src/
│   │   ├── views/
│   │   │   ├── LoginView.vue                         [MOD] SSO-Buttons, lokales Form-Toggle
│   │   │   ├── FirstLoginView.vue                    [NEU] Welcome-Screen
│   │   │   ├── SsoErrorView.vue                      [NEU] Lokalisierter Outage-Screen
│   │   │   ├── IdpProviderListView.vue               [NEU] Admin-Liste
│   │   │   ├── IdpProviderEditView.vue               [NEU] IdP-Edit mit Dry-Run-Panel
│   │   │   ├── TeamListView.vue                      [NEU]
│   │   │   └── TeamDetailView.vue                    [NEU] Member-Management, Group-Mapping
│   │   ├── stores/
│   │   │   ├── auth.ts                               [MOD] +effective_roles, +first_login_complete
│   │   │   ├── sso.ts                                [NEU] Provider-Liste
│   │   │   ├── team.ts                               [NEU] User-Teams, Default-Team
│   │   │   ├── idpAdmin.ts                           [NEU] IdP-CRUD, Dry-Run
│   │   │   └── emergencyBypass.ts                    [NEU]
│   │   ├── composables/
│   │   │   └── useCanEdit.ts                         [NEU] Konsumiert effective_role
│   │   ├── components/
│   │   │   ├── admin/
│   │   │   │   └── DryRunPanel.vue                   [NEU]
│   │   │   ├── FlowEditor.vue                        [MOD] +readOnly prop, Read-Only-Banner
│   │   │   └── TeamSwitcher.vue                      [NEU] Header-Komponente
│   │   ├── router/
│   │   │   └── index.ts                              [MOD] +Phase-4-Routes, +Guards
│   │   └── locales/
│   │       ├── en.json                               [MOD] +alle neuen Keys
│   │       ├── de.json                               [MOD]
│   │       ├── fr.json                               [MOD]
│   │       └── es.json                               [MOD]
├── e2e/
│   └── tests/
│       ├── sso-login.spec.ts                         [NEU]
│       ├── first-login-landing.spec.ts               [NEU]
│       ├── admin-idp-dry-run.spec.ts                 [NEU]
│       ├── team-management.spec.ts                   [NEU]
│       ├── emergency-bypass.spec.ts                  [NEU]
│       ├── bookmark-survives-expiry.spec.ts          [NEU]
│       └── sso-outage-error.spec.ts                  [NEU]
└── docker/
    └── nginx.conf                                    [MOD] TLS 1.2+ Min-Version, Cipher-Härtung
```

### Architectural Boundaries

**API Boundaries:**

- **Öffentlich (vor `get_current_user`):** `/auth/sso/providers`, `/auth/sso/{idp_id}/login`, `/auth/sso/callback`, `/auth/login` (existing). Alles andere verlangt Authentication.
- **Auth-Dependency-Kette:** `get_current_user` → `require_effective_role(role, repo_id=?)` für repo-scoped Endpoints → Endpoint-Body. `require_role` (statisch, global) bleibt für ADMIN-only-Endpoints wie IdP-CRUD.
- **OIDC-Callback ist der einzige IdP-Outbound-Trigger.** Andere Code-Pfade dürfen nur: (a) Discovery-Cache-Refresh (APScheduler), (b) Admin-Dry-Run mit IdP sprechen.
- **Audit-Middleware sitzt vor den Routern** — keine neue Middleware-Registrierung nötig.

**Component Boundaries (Backend):**

- **`src/auth/`** besitzt SSO-Flow, IdP-Admin, `get_current_user`, Permission-Primitives, API-Token-Verwaltung.
- **`src/teams/`** besitzt Team/TeamMember-Lifecycle, Group-Sync, Group-Mapping-CRUD. Permission-Checks passieren in Routern, nicht in Services.
- **`src/audit/`** besitzt Audit-Event-Typen + Middleware + Service.
- **`src/repos/`** konsumiert `effective_role(user, repo)` via `require_effective_role`-Dependency. Kein direkter Import von `teams.service`.
- **`src/users/`** wird erweitert um `first_login_complete`; keine Phase-4-Kernlogik dort.

**Component Boundaries (Frontend):**

- **`stores/auth.ts`** ist Single-Source-of-Truth für User-Session inkl. `effective_roles` und `first_login_complete`. Andere Stores referenzieren `authStore` für Permission-Gates.
- **`composables/useCanEdit`** liest `authStore.effective_roles[repoId]` — Views rufen nie Store-State direkt ab.
- **Router-Guards** sind der einzige Ort, an dem Redirects basierend auf Session-State passieren.

**Data Boundaries:**

- **`Repository.team_id` FK** koppelt `repos` an `teams` weich (nullable, `ON DELETE SET NULL`). Einseitige Beziehung.
- **`TeamMember.source`** discriminiert manuelle vs IdP-gesyncte Memberships. Sync-Diff betrachtet nur `source='idp_group_sync'`-Rows.
- **`OidcLoginAttempt`** hat 10-Min-TTL, wird bei Callback-Konsum gelöscht. Zugriff nur aus `auth.sso_router`.
- **`AuditLog`** bleibt write-only aus Service-Perspektive; Reads nur via Admin-UI-Endpoint.

### Requirements to Structure Mapping (FR → File)

| FRs | Primäre Dateien |
|---|---|
| FR1–6 (IdP Config) | `src/auth/idp_router.py`, `src/auth/oidc_service.py`, `src/auth/models.py` (IdentityProvider), `frontend/src/views/IdpProvider*.vue`, `frontend/src/stores/idpAdmin.ts`, `frontend/src/components/admin/DryRunPanel.vue` |
| FR7–13 (SSO Auth) | `src/auth/sso_router.py`, `src/auth/oidc_service.py`, `src/auth/dependencies.py`, `frontend/src/views/LoginView.vue`, `frontend/src/stores/sso.ts` |
| FR14–22 (Teams) | `src/teams/*`, `frontend/src/views/Team*.vue`, `frontend/src/stores/team.ts`, `frontend/src/components/TeamSwitcher.vue` |
| FR23–30 (Role Resolution) | `src/auth/permissions.py`, schrittweise Umstellung aller `src/{repos,execution,reports,explorer,stats}/router.py` auf `require_effective_role` |
| FR31–36 (First-Login UX) | `frontend/src/views/FirstLoginView.vue`, `frontend/src/router/index.ts` (Guard), `src/users/models.py` (`first_login_complete`), `frontend/src/components/FlowEditor.vue` (readOnly prop) |
| FR37–41 (Resilience & Bypass) | `src/auth/router.py` (bypass endpoints), `src/settings/models.py`, `src/main.py` (APScheduler-Job), `frontend/src/stores/emergencyBypass.ts`, `frontend/src/views/SsoErrorView.vue` |
| FR42–45 (Deprovisioning) | `src/auth/router.py` (API-Token-Reassign), `src/users/service.py` (is_active-Propagation), `src/teams/service.py` (Retention-Cleanup via APScheduler) |
| FR46–49 (Audit) | `src/audit/event_types.py` (Enum), `src/audit/service.py` (log_event), Aufrufer in allen neuen Services |
| FR50 (i18n) | `frontend/src/locales/*.json`, lokalisierte Strings in allen neuen Views + Error-Responses aus Backend |

### Integration Points

**Internal Communication (Backend):**

- **Router → Service → Model** (bestehendes Muster). Services kennen Models; Router kennen Services.
- **Cross-module Service-Calls:** Minimiert. `auth.sso_router` ruft `teams.sync.sync_team_memberships()`; `users.service.deactivate_user()` ruft `auth.api_token_service.revoke_all_for_user()`.
- **Audit:** Services rufen `audit.service.log_event()` explizit für non-HTTP-Events; HTTP-Endpoints werden via Middleware automatisch abgedeckt.
- **APScheduler-Jobs** in `main.py` registriert, rufen Services für Discovery-Cache-Refresh, Bypass-Auto-Expire, Retention-Cleanup, Counter-Cleanup.

**External Integrations:**

- **IdPs (Azure AD, Google, GitHub):** Nur aus `auth.oidc_service`. Timeout, TLS-1.2+-Enforcement, Retry-Policy lokal im Service.
- **Kein anderer Outbound-Traffic** als Teil von Phase 4.

**Data Flow:**

1. **SSO-Login:** Browser → `/auth/sso/{idp_id}/login` → 302 IdP → Consent → 302 `/auth/sso/callback` → Token-Exchange (authlib) → Claim-Extraction → User-Upsert + Team-Sync (1 Txn) → Commit → JWT-Issuance → 302 `return_to`.
2. **API-Request:** Request → `get_current_user` (JWT/API-Token + is_active-Recheck) → `require_effective_role(role, repo_id)` berechnet `MAX()` → Endpoint-Body → Audit-Middleware loggt Response.
3. **Emergency-Bypass:** Admin → POST `/settings/sso-emergency-bypass` {hours} → Validation (≤24) → Settings-Update + APScheduler-One-Shot-Expiry → Audit-Log. Login-Seite zeigt elevated local-password form.
4. **Offboarding:** Admin setzt `is_active=false` → User-Sessions on next request rejected + `ApiToken.revoked_at=now()` + Audit-Log.

### File Organization Patterns

- **Config:** `backend/src/config.py` (zentraler Pydantic Settings), `.env`, `docker-compose.*.yml`.
- **Source:** Domain-based in `backend/src/<domain>/`. Jede Domain kapselt `models.py`, `schemas.py`, `router.py`, `service.py`; optional `dependencies.py`, `sync.py`.
- **Tests:** spiegeln Source-Struktur: `backend/tests/<domain>/test_<feature>.py`. Fixtures in `backend/tests/fixtures/`.
- **Assets:** keine neuen. Handoff-Artifact-PDF wird zur Request-Zeit via `reportlab` generiert.

### Development Workflow Integration

- **Dev-Server:** `make dev` (`:8000` Backend, `:5173` Frontend) — unverändert.
- **DB-Migration:** `make db-migrate msg="phase4 sso and teams"` → `make db-upgrade`.
- **Tests:** `make test` (Backend + Frontend); `make test-e2e` Playwright.
- **Build:** bestehender Pipeline + neue CI-Gates (Offline-Boot-Isolation, Prod-Frontend-Build, Windows-Offline-ZIP, Mock-OIDC-Integration).

## Architecture Validation Results

### Coherence Validation ✅

- **Technology-Kompatibilität:** `authlib` + sync FastAPI + SQLAlchemy 2.0 sync + `reportlab` (pure Python) + `respx` (Tests) + `@axe-core/playwright` (E2E) vertragen sich mit dem gepinnten Stack; alle via `uv` bzw. `npm` installierbar ohne C-Extension-Risiko.
- **Pattern-Konsistenz:** Naming, Struktur und Audit-Event-Schema folgen den bestehenden Konventionen aus `project-context.md` Cat. 2. Delta klar abgegrenzt.
- **Structure-Alignment:** Neue Modul-Grenzen (`teams/`, `sso_router.py`, `idp_router.py`) respektieren Domain-Gliederung; keine zirkulären Imports, keine Layer-Verletzungen.
- **Keine widersprüchlichen Entscheidungen** gefunden.

### Requirements Coverage Validation ✅

**FR-Abdeckung (50/50):**

| FR-Gruppe | Heimat | Status |
|---|---|---|
| FR1–6 (IdP Config) | `IdentityProvider` + `idp_router` + `oidc_service.dry_run` | ✅ |
| FR7–13 (SSO Auth) | `sso_router` + `oidc_service` + `return_to`-Validation | ✅ |
| FR14–22 (Teams) | `src/teams/*` | ✅ |
| FR23–30 (Role Resolution) | `permissions.effective_role()` + schrittweise Umstellung | ✅ |
| FR31–36 (First-Login UX) | `FirstLoginView` + `first_login_complete` + `useCanEdit` | ✅ |
| FR37–41 (Resilience & Bypass) | Emergency-Bypass + `SsoErrorView` + APScheduler | ✅ |
| FR42–45 (Deprovisioning) | `is_active`-Recheck + API-Token-Reassign + Retention | ✅ |
| FR46–49 (Audit) | `AuditEventType` Enum + Middleware + `log_event()` | ✅ |
| FR50 (i18n) | Locales + CI-Prod-Build-Gate | ✅ |

**NFR-Abdeckung (30/30):** Alle Performance-, Security-, Reliability-, Deployability-, Accessibility-, Integration-, und Auditability-NFRs haben architektonische Verankerung. A11y-Tooling-Gap (NFR23) gelöst durch `@axe-core/playwright`-Entscheidung.

### Implementation Readiness Validation ✅

- **Decision Completeness:** alle kritischen Entscheidungen dokumentiert mit Begründung; PDF-Lib, Rate-Limiting-Ansatz, `require_role`-Migration-Strategie explizit vom User geentschieden; 5 validierungs-gefundene Gaps gelockt (siehe unten).
- **Structure Completeness:** vollständiger Baum neuer + modifizierter Dateien; FR→File-Mapping lückenlos.
- **Pattern Completeness:** Naming, Struktur, Kommunikation, Prozess abgedeckt; Good/Anti-Pattern-Beispiele konkret.

### Resolved Gaps (Entscheidungen aus Validation Round)

| # | Gap | Entscheidung |
|---|---|---|
| 1 | Endpoint-Shape für `effective_roles` | `GET /auth/me` liefert `effective_roles_by_repo: dict[int, Role]` eager (Teams-of-User-Repos, typisch <50). Bei späterem Perf-Problem: additive Migration zu Lazy/Hybrid. |
| 2 | A11y-Tooling (NFR23) | `@axe-core/playwright` in bestehende Playwright-Suite; 1 Test pro neue View mit `injectAxe()` + `checkA11y()`. Manueller Screenreader-Smoke-Test als Release-Gate-Item. |
| 3 | `require_role` vs `require_effective_role` Kriterium | **Defaultregel:** Endpoint mit `{repo_id}` im Pfad → `require_effective_role`. Alles andere → `require_role`. Grenzfälle (Run-/Report-Scope via Join) als **Ausnahmen-Liste in `project-context.md` Cat. 2** dokumentieren. |
| 4 | Mock-OIDC-Fixture-Implementation | `respx`-basiert (mockt `httpx`-Transport unter `authlib`); kein zweiter FastAPI-Server, keine externe Dep jenseits `respx`. Fixture in `backend/tests/fixtures/mock_oidc.py`, geteilt über alle SSO-Tests. |
| 5 | Zero-Teams-Fallback im Login-Response | Backend garantiert `teams: Team[]` (leer bei keiner Membership) und `default_team_id: int \| null` im `/auth/me`. `FirstLoginView` rendert Zero-Teams-Empty-State (FR34). Neues Setting `admin_contact_email` (default `admin@roboscope.local`) als konfigurierbarer Admin-Kontakt. |

**Nice-to-Have-Ergänzungen eingearbeitet:**

- Rate-Limit-Counter-Cleanup: stündlich alte Counter (>24 h) löschen; `RATE_LIMIT_CLEANUP_HOURS=1` als Konstante in `config.py`.
- CSP-Header für Login-Seite: Nginx-Default konservativ setzen (`default-src 'self'; frame-ancestors 'none'`); als Teil der `nginx.conf`-Änderung für TLS.
- Handoff-Artifact-Caching: nicht in v1; bei Bedarf später additiv.

### Settings-Modell-Erweiterung (finales Bild)

Aus Gap-Resolution ergänzt:

```python
# src/settings/models.py
class Settings(Base):
    # ... existing fields ...
    sso_emergency_bypass: bool = False
    sso_emergency_bypass_expires_at: datetime | None = None
    deprovision_retention_days: int = 90
    admin_contact_email: str = "admin@roboscope.local"  # [NEU aus Gap 5]
```

### Architecture Completeness Checklist

**✅ Requirements Analysis**
- [x] Project context thoroughly analyzed
- [x] Scale and complexity assessed (medium-high, Brownfield)
- [x] Technical constraints identified
- [x] 9 cross-cutting concerns mapped

**✅ Architectural Decisions**
- [x] Critical decisions documented (OIDC-Lib, Role-Resolution, JWT-Form, Migration, PDF-Lib, Rate-Limit, require_role-Migration)
- [x] Technology stack fully specified
- [x] Integration patterns defined
- [x] Performance considerations addressed

**✅ Implementation Patterns**
- [x] Naming conventions established (als Delta zu project-context.md)
- [x] Structure patterns defined
- [x] Communication patterns specified
- [x] Process patterns documented
- [x] Good/Anti-Pattern-Beispiele konkret

**✅ Project Structure**
- [x] Complete directory structure defined
- [x] Component boundaries established
- [x] Integration points mapped (4 Data Flows)
- [x] Requirements to structure mapping complete (FR-Gruppe → Files)

**✅ Validation & Gap-Resolution**
- [x] Kohärenz geprüft
- [x] 50 FR + 30 NFR Coverage verifiziert
- [x] 5 Gaps identifiziert und mit Entscheidungen gelockt
- [x] Settings-Modell-Erweiterung aus Gap-5 eingearbeitet

### Architecture Readiness Assessment

**Overall Status:** **READY FOR IMPLEMENTATION**

**Confidence Level:** **High** — alle validierungs-gefundenen Gaps sind explizit entschieden, keine offenen Architektur-Fragen blockieren Epic-Breakdown oder Story-Erstellung.

**Key Strengths:**

- Alle 50 FRs + 30 NFRs haben architektonische Heimat mit File-Zuordnung.
- Brownfield-Respekt: keine Stack-Änderungen, keine Pattern-Duplikate, autoritative Cross-References auf `project-context.md`.
- Non-Goals (SAML, SCIM, Silent Renew, Multi-Team-per-Repo) spürbar im Design verankert.
- Mock-OIDC-Fixture (`respx`) senkt Test-Kosten über 16 Stories.
- `MAX()`-Role-Resolution + additive Grants vermeiden Deny-Komplexität.
- Schrittweise `require_role`→`require_effective_role`-Umstellung mit codifizierter Defaultregel senkt Regressions-Risiko.
- A11y, Rate-Limiting, CSP als nicht-verhandelbare CI-Gates verankert — Procurement-Review-kompatibel.

**Areas for Future Enhancement:**

- SCIM 2.0 (Phase 5) — Schema-Vorbereitung via `external_id`-Felder schon erledigt.
- SAML 2.0 (Phase 4.5) — Architektur unterstützt; nur `xmlsec`-Build-Pfad zu lösen.
- Silent Token Renewal — falls Paul-Validierungsmetrik positiv (PRD Appendix A).
- Real-time Deprovisioning — via SCIM (Phase 5); aktuelle login-time-Sync-Staleness in AuditLog nachvollziehbar.

### Implementation Handoff

**AI Agent Guidelines:**

- Dieses Dokument ist der verbindliche Architektur-Kontrakt für Phase 4.
- Alle Stories referenzieren FR- und NFR-Nummern aus dem PRD sowie die „Requirements to Structure Mapping"-Tabelle dieses Dokuments.
- Bei Unsicherheit: zuerst `project-context.md` prüfen, dann dieses Dokument, dann fragen.
- Alle 5 validierungs-resolvierten Entscheidungen (oben) sind **verbindlich**; keine Re-Diskussion in Sprint-Planung.

**First Implementation Priority:**

Story 1 des Epic-Breakdowns: **Alembic-Migration** für:

- 5 neue Modelle: `IdentityProvider`, `Team`, `TeamMember`, `IdPGroupMapping`, `OidcLoginAttempt`
- `Repository.team_id` FK (nullable, `ON DELETE SET NULL`)
- `User.first_login_complete: bool` (default `False`)
- `Settings`-Erweiterungen: `sso_emergency_bypass`, `sso_emergency_bypass_expires_at`, `deprovision_retention_days`, `admin_contact_email`
- `RateLimitCounter` Tabelle (falls noch nicht vorhanden) oder Erweiterung

Rollback-kompatibel (`down()`-Pfad vollständig). Keine Verhaltensänderung bei Migration-Apply — Endpoints existieren noch nicht. Tests verifizieren Up/Down-Symmetrie.
