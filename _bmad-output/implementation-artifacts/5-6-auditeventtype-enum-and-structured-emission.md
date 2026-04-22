# Story 5-6: AuditEventType enum + structured emission

Status: done (shipped inline with Phase 4 Epic 2)

## Story

As a Security analyst,
I want all Phase-4 audit events to use a centralized `AuditEventType` enum with structured detail JSON,
so that SIEM ingestion is deterministic.

## Acceptance Criteria

1. A single `AuditEventType` StrEnum lists every event dotted-literal used across Phase 4 (sso.*, team.*, team_member.*, group_mapping.*, repository.team_assigned, repository.team_unassigned).
2. A `log_event(db, event_type, **fields)` helper derives `AuditLog.action` and `resource_type` from the enum so call sites cannot drift from the SIEM literals.
3. Every Phase 4 emission site uses `log_event` with a typed enum member — no raw string `action` values.
4. Enum members remain immutable once shipped (downstream SIEMs match on literals); renames are additive-only.

## Implementation

Shipped in commit `c8c171b` as part of the Phase 4 Epic 2 + 3 bundle:

- `backend/src/audit/event_types.py` — `AuditEventType` StrEnum with 15 members covering SSO, team, team_member, group_mapping, repository event families. Docstring calls out "immutable literals, additive-only".
- `backend/src/audit/service.py` — `log_event(db, event_type, *, user_id, username, resource_id, detail, ip_address)` wraps the existing `log_audit` and derives `action = event_type.value` + `resource_type = event_type.value.split(".", 1)[0]` via `resource_type_for()`.
- Call sites in `sso_router.py`, `teams/router.py`, `repos/router.py` all use the enum; no raw strings.
- Tests: `backend/tests/audit/test_event_types.py` locks in literal stability + the helper round-trip.

## Notes

- The StrEnum approach means enum members double as `str` values, so direct comparison (`AuditLog.action == AuditEventType.SSO_LOGIN_SUCCESS`) works without unwrapping — kept for migration convenience.
- `repository.team_assigned` / `repository.team_unassigned` were added in Story 3-2; the enum was extended, not replaced.
- SIEM rules should match `audit_log.action` against the dotted literals, not the enum member names.
