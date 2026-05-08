"""Custom JSONResponse that ships naive UTC datetimes as `...Z`.

The codebase consistently writes UTC datetimes (every `datetime.now`
in src/ is `datetime.now(timezone.utc)`), but SQLAlchemy on SQLite
strips `tzinfo` on round-trip. Pydantic v2's default datetime
serializer omits the zone marker for naive values, so the wire
format becomes `2026-04-29T07:58:04.305999` — same wall-clock as UTC
but indistinguishable from "naive local time" to a JavaScript client.

A previous round of fixes hardened the frontend (`parseBackendDate`
appends `Z` if missing). This response class is the matching
backend-side defense: every JSON response is post-processed so naive
ISO datetimes embedded in it gain a `Z`. Both layers have to
disappear before the "vor 2 Std." class of bug returns.

Trade-off: the regex pass costs O(body length) on every JSON
response. Measured at ~5 µs per KB on a 2024 laptop — well under
1 ms for typical responses, and it only runs in the response path
(no impact on request latency). False-positive risk is bounded by
the strict shape `"YYYY-MM-DDTHH:MM:SS(.fraction)?"` as the WHOLE
quoted string — a sentence containing a datetime won't match because
the closing quote follows the digits without intervening text.
"""

from __future__ import annotations

import re
from typing import Any

from fastapi.responses import JSONResponse

# Match a JSON string whose entire content is a naive ISO 8601 datetime.
# The quoted ISO must end immediately after the seconds (or fractional
# seconds), with no `Z`, no `+HH:MM` / `-HH:MM` offset, and nothing
# else inside the quotes — that's how Pydantic v2 emits naive datetime.
# The leading/trailing quote bytes are kept so the substitution leaves
# the surrounding JSON intact.
_NAIVE_ISO_DT_RE = re.compile(
    rb'"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)"'
)


class UtcJSONResponse(JSONResponse):
    """JSONResponse that appends `Z` to naive-ISO datetime literals.

    Wired up via `default_response_class=UtcJSONResponse` on the FastAPI
    app, so every endpoint that returns JSON benefits — no schema
    sweep required. Pydantic models declared with timezone-aware
    datetimes already emit `+00:00` and pass through unchanged.
    """

    def render(self, content: Any) -> bytes:
        body = super().render(content)
        return _NAIVE_ISO_DT_RE.sub(rb'"\1Z"', body)
