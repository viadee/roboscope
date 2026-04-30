/**
 * Shared error-handling helpers.
 *
 * The codebase has ~50 `catch (e: any)` blocks of the form:
 *
 *     } catch (e: any) {
 *       const detail = e?.response?.data?.detail
 *       error.value = typeof detail === 'string' ? detail : fallback
 *     }
 *
 * Each one re-implements the same axios-error → human-readable-string
 * unwrap. `extractErrorDetail()` consolidates that into one tested
 * helper so callers can switch to `catch (e: unknown)` without
 * sprinkling `as any` casts. New code should use this; old `: any`
 * sites should migrate as they're touched (the codebase tracks 65
 * such annotations as a known long-tail in CLAUDE.md).
 */
/**
 * Extract a human-readable error message from a thrown value, falling
 * back to `fallback` when nothing usable is available.
 *
 * The migration target replaces this exact idiom (which appears 50+
 * times in the codebase):
 *
 *     const detail = e?.response?.data?.detail || fallback
 *
 * The helper therefore matches that semantic precisely — it walks
 * the `response.data` path on an unknown thrown value and returns
 * a string, falling back when nothing usable was extractable. It
 * deliberately does NOT extract `Error.message` or
 * `AxiosError.message` ("Network Error", "Request failed with
 * status code 500"), because the original idiom didn't either —
 * call sites uniformly preferred a localised fallback over those
 * raw messages.
 *
 * The structural check (`response?.data?.detail`) — rather than
 * `axios.isAxiosError(e)` — also makes the helper drop-in for unit
 * tests that mock with plain objects (`{ response: { data: { detail
 * } } }`), matching the codebase's existing test patterns.
 *
 * Always returns a string. Never throws.
 */
export function extractErrorDetail(e: unknown, fallback: string): string {
  // Walk `e.response.data` defensively — `e` may be anything from a
  // real AxiosError to a plain object mocked in tests, to a native
  // Error, to null. Only return a string when we find one in the
  // expected place.
  if (e && typeof e === 'object' && 'response' in e) {
    const response = (e as { response?: unknown }).response
    if (response && typeof response === 'object' && 'data' in response) {
      const data = (response as { data?: unknown }).data
      if (data && typeof data === 'object' && 'detail' in data) {
        const detail = (data as { detail?: unknown }).detail
        // FastAPI conventional shape: `{ "detail": "<string>" }`
        if (typeof detail === 'string' && detail.length > 0) {
          return detail
        }
        // Some endpoints return a structured detail object with
        // `.message` (e.g. validation errors with extra context).
        if (
          detail
          && typeof detail === 'object'
          && 'message' in detail
          && typeof (detail as { message?: unknown }).message === 'string'
        ) {
          return (detail as { message: string }).message
        }
      }
      // Endpoints that skip the detail wrapper and return a plain string.
      if (typeof data === 'string' && data.length > 0) {
        return data
      }
    }
  }
  return fallback
}
