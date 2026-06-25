"""Schemas for the governance read endpoint."""

from pydantic import BaseModel


class FeaturesResponse(BaseModel):
    """Resolved feature flags for the frontend.

    `flags[key]` is the effective on/off value; `locked[key]` is True when the
    value was set via an ENV override (the UI renders it as non-editable —
    "managed by your administrator").
    """

    flags: dict[str, bool]
    locked: dict[str, bool]
