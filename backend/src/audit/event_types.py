"""Central registry of structured audit event types (NFR29).

Each value is a dotted `<domain>.<entity>.<action>` string that goes into
`AuditLog.action`. `resource_type` is derived from the first segment.

Phase 4 extends this enum incrementally — only events that have a concrete
emission site belong here. Add a member **before** its first call site.
"""

from __future__ import annotations

from enum import StrEnum


class AuditEventType(StrEnum):
    SSO_LOGIN_SUCCESS = "sso.login.success"
    SSO_LOGIN_FAILURE = "sso.login.failure"
    SSO_LOGIN_RATE_LIMITED = "sso.login.rate_limited"
    TEAM_MEMBER_SYNCED_FROM_IDP = "team.member.synced_from_idp"
    TEAM_CREATED = "team.created"
    TEAM_UPDATED = "team.updated"
    TEAM_DELETED = "team.deleted"
    TEAM_MEMBER_ADDED = "team_member.added"
    TEAM_MEMBER_UPDATED = "team_member.updated"
    TEAM_MEMBER_REMOVED = "team_member.removed"
    REPOSITORY_TEAM_ASSIGNED = "repository.team_assigned"
    REPOSITORY_TEAM_UNASSIGNED = "repository.team_unassigned"
    GROUP_MAPPING_CREATED = "group_mapping.created"
    GROUP_MAPPING_UPDATED = "group_mapping.updated"
    GROUP_MAPPING_DELETED = "group_mapping.deleted"
    USER_DEACTIVATED = "user.deactivated"
    USER_REACTIVATED = "user.reactivated"
    SSO_EMERGENCY_BYPASS_ACTIVATED = "sso.emergency_bypass.activated"
    SSO_EMERGENCY_BYPASS_DEACTIVATED = "sso.emergency_bypass.deactivated"
    API_TOKEN_REASSIGNED = "api_token.reassigned"
    USER_ACCOUNT_LINKED = "user.account_linked"
    USER_ACCOUNT_LINK_CANCELLED = "user.account_link_cancelled"
    RECORDING_SESSION_STARTED = "recording.session.started"
    RECORDING_SESSION_COMPLETED = "recording.session.completed"
    RECORDING_SESSION_ABORTED = "recording.session.aborted"
    RECORDING_FLOW_SAVED = "recording.flow.saved"
    FLAKY_TEST_QUARANTINED = "flaky.test.quarantined"
    FLAKY_TEST_UNQUARANTINED = "flaky.test.unquarantined"
    HEAL_PATCH_APPLIED = "heal.patch.applied"


def resource_type_for(event_type: AuditEventType) -> str:
    """Return the canonical resource_type (`sso`, `team`, `idp`, ...) for an event."""
    return event_type.value.split(".", 1)[0]
