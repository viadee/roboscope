"""Login-observed IdP groups cache (Story 3-5).

We avoid adding a dedicated table for what amounts to a short list of
strings per IdP — instead, the cache rides on the existing `AppSetting`
key/value store under the `sso.seen_groups.<idp_id>` key, with the
value being a JSON array of distinct group_claim_values in
insertion order. The cap at `_MAX_ENTRIES` prevents unbounded growth
if a misconfigured IdP sends hundreds of group claims per login.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from src.settings.models import AppSetting

_KEY_PREFIX = "sso.seen_groups."
_MAX_ENTRIES = 200


def _key(idp_id: int) -> str:
    return f"{_KEY_PREFIX}{idp_id}"


def list_seen_groups(db: Session, idp_id: int) -> list[str]:
    row = (
        db.query(AppSetting).filter(AppSetting.key == _key(idp_id)).one_or_none()
    )
    if row is None or not row.value:
        return []
    try:
        data = json.loads(row.value)
    except json.JSONDecodeError:
        return []
    return [g for g in data if isinstance(g, str)]


def record_seen_groups(db: Session, idp_id: int, groups: list[str]) -> None:
    """Merge `groups` into the cache for `idp_id`. Keeps insertion order,
    dedups, and caps the total at `_MAX_ENTRIES`.
    """
    if not groups:
        return
    existing = list_seen_groups(db, idp_id)
    seen = {g: None for g in existing}  # dict preserves insertion order
    for g in groups:
        if isinstance(g, str) and g not in seen:
            seen[g] = None
    merged = list(seen.keys())[-_MAX_ENTRIES:]

    row = (
        db.query(AppSetting).filter(AppSetting.key == _key(idp_id)).one_or_none()
    )
    payload = json.dumps(merged)
    if row is None:
        row = AppSetting(
            key=_key(idp_id),
            value=payload,
            value_type="json",
            category="auth",
            description=f"Login-observed group claims for IdP {idp_id} (Story 3-5 cache).",
        )
        db.add(row)
    else:
        row.value = payload
    db.flush()
