"""Tests for `UtcJSONResponse` — naive UTC datetime → `...Z` on the wire.

The class is wired as the FastAPI app's `default_response_class`,
so every endpoint inherits the post-processing. These tests cover
the pure render-level transformation: exotic edge cases shouldn't
regress just because someone refactors the regex.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.encoders import jsonable_encoder

from src.utc_response import UtcJSONResponse


def _render(content: object) -> bytes:
    """Pre-encode like FastAPI does in real request flow.

    The framework calls `jsonable_encoder` (via the route handler) on
    a Pydantic model before reaching the response class's `render`.
    By the time our regex sees the body, datetimes are already ISO
    strings — that's the layer we operate on. We pass the encoded
    content to BOTH the constructor and `render` because the
    JSONResponse __init__ runs `render` once internally.
    """
    encoded = jsonable_encoder(content)
    return UtcJSONResponse(encoded).render(encoded)


def test_naive_datetime_string_gains_z_suffix() -> None:
    body = _render({"created_at": "2026-04-29T07:58:04.305999"})
    assert body == b'{"created_at":"2026-04-29T07:58:04.305999Z"}'


def test_explicit_utc_z_passes_through_unchanged() -> None:
    body = _render({"created_at": "2026-04-29T07:58:04Z"})
    assert body == b'{"created_at":"2026-04-29T07:58:04Z"}'


def test_explicit_offset_passes_through_unchanged() -> None:
    body = _render({"created_at": "2026-04-29T07:58:04+02:00"})
    assert body == b'{"created_at":"2026-04-29T07:58:04+02:00"}'


def test_pydantic_naive_datetime_object_is_normalized() -> None:
    """End-to-end: pass an actual datetime, let FastAPI's
    jsonable_encoder turn it into ISO, then our render appends `Z`."""
    naive = datetime(2026, 4, 29, 7, 58, 4)
    body = _render({"created_at": naive})
    assert b'"2026-04-29T07:58:04Z"' in body


def test_aware_datetime_object_passes_through() -> None:
    aware = datetime(2026, 4, 29, 7, 58, 4, tzinfo=timezone.utc)
    body = _render({"created_at": aware})
    # jsonable_encoder emits `+00:00` for aware datetimes; we leave it alone.
    assert b'"2026-04-29T07:58:04+00:00"' in body


def test_datetime_without_seconds_does_not_match() -> None:
    """Regex requires seconds — partial timestamps must NOT be touched
    so we don't mistake an unrelated string for a datetime."""
    body = _render({"value": "2026-04-29T07:58"})
    assert body == b'{"value":"2026-04-29T07:58"}'


def test_embedded_datetime_in_sentence_is_left_alone() -> None:
    """The regex matches only WHOLE quoted strings — a datetime
    embedded inside prose has text after the digits and won't match."""
    body = _render({"note": "occurred at 2026-04-29T07:58:04 sharp"})
    assert b"occurred at 2026-04-29T07:58:04 sharp" in body
    assert b"2026-04-29T07:58:04Z" not in body


def test_array_of_datetimes_each_gets_z() -> None:
    body = _render({
        "events": [
            "2026-04-29T07:58:04",
            "2026-04-29T08:00:00.123",
        ],
    })
    assert b'"2026-04-29T07:58:04Z"' in body
    assert b'"2026-04-29T08:00:00.123Z"' in body


def test_nested_object_is_walked() -> None:
    body = _render({
        "outer": {"inner": {"deep_ts": "2026-04-29T07:58:04"}},
    })
    assert b'"2026-04-29T07:58:04Z"' in body


def test_none_content_renders_as_empty_object_or_null() -> None:
    """Sanity: subclass must not break the parent's None handling."""
    body = _render(None)
    assert body == b"null"
