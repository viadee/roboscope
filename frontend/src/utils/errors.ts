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
 * Extract the HTTP status code from an axios-style error, or null
 * when the thrown value isn't an HTTP response. Used by call sites
 * that branch on specific status codes (401 = wrong password, 409 =
 * conflict, 422 = validation, ...) — pairs with `extractErrorDetail`
 * for the message extraction. Same structural-walk philosophy:
 * works on real AxiosError instances AND plain test mocks.
 */
export function extractErrorStatus(e: unknown): number | null {
  if (e && typeof e === 'object' && 'response' in e) {
    const r = (e as { response?: unknown }).response
    if (r && typeof r === 'object' && 'status' in r) {
      const s = (r as { status?: unknown }).status
      if (typeof s === 'number') return s
    }
  }
  return null
}

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
/**
 * Status-aware error-message builder for user-facing call sites.
 *
 * `extractErrorDetail` alone has a blind spot: an UNHANDLED backend
 * exception comes back from Starlette's error middleware as a 500
 * whose body is the bare text `"Internal Server Error"`. That string
 * matches the plain-string-body branch and gets surfaced verbatim —
 * so the user sees "Internal Server Error" with no idea what went
 * wrong or what to do (the real cause, e.g. a full disk, is only in
 * the backend log). This helper branches on the HTTP status instead:
 *
 *   - 5xx           → `serverError(status)` (the raw body is useless,
 *                     so we never surface it; the localised message
 *                     points the user at the server logs).
 *   - 4xx           → `extractErrorDetail` — a client error's `detail`
 *                     IS meaningful (permission denied, repo missing,
 *                     validation), so keep showing it.
 *   - no response   → `networkError` (backend unreachable / CORS /
 *                     connection refused — axios produces an error
 *                     with no `.response`).
 *
 * All three message options are optional; each falls back to
 * `fallback` when not supplied. Always returns a string; never throws.
 */
export interface RequestErrorMessages {
  /** Generic message used for 4xx without a detail, or any unknown throw. */
  fallback: string
  /** 5xx — receives the numeric status so callers can show the code. */
  serverError?: (status: number) => string
  /** No HTTP response received (backend down, network failure). */
  networkError?: string
}

export function describeRequestError(
  e: unknown,
  messages: RequestErrorMessages,
): string {
  const status = extractErrorStatus(e)
  if (status !== null) {
    if (status >= 500) {
      return messages.serverError ? messages.serverError(status) : messages.fallback
    }
    // 4xx (and the rare 3xx that surface as errors): the server's
    // `detail` is the useful, actionable text — keep showing it.
    return extractErrorDetail(e, messages.fallback)
  }
  // status === null: either a genuine no-response failure, or a
  // weird shape that still carries a `response`. Only treat it as a
  // network error when there's truly no `response` object — otherwise
  // fall back to the detail walk so we don't mislabel a malformed 4xx.
  const hasResponse =
    e !== null
    && typeof e === 'object'
    && 'response' in e
    && typeof (e as { response?: unknown }).response === 'object'
    && (e as { response?: unknown }).response !== null
  if (!hasResponse && messages.networkError) {
    return messages.networkError
  }
  return extractErrorDetail(e, messages.fallback)
}

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
