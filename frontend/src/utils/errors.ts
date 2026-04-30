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
import axios from 'axios'

/**
 * Extract a human-readable error message from a thrown value, falling
 * back to `fallback` when nothing usable is available.
 *
 * Walks several common shapes:
 *   - axios error with `response.data.detail` (string) — FastAPI's
 *     conventional error shape; the most common case
 *   - axios error with `response.data.detail` (object with .message)
 *     — some endpoints wrap a structured error
 *   - axios error with `response.data` (string) — endpoints that
 *     skip the detail wrapper
 *   - native Error with `.message` — non-axios paths (sync errors,
 *     fetch failures, etc.)
 *   - everything else — `fallback`
 *
 * Always returns a string. Never throws.
 */
export function extractErrorDetail(e: unknown, fallback: string): string {
  // Most common path — axios error with a FastAPI-shaped `detail`.
  if (axios.isAxiosError(e)) {
    const data: unknown = e.response?.data
    // FastAPI conventional shape: `{ "detail": "<string>" }`
    if (data && typeof data === 'object' && 'detail' in data) {
      const detail = (data as { detail?: unknown }).detail
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
    // Axios's own message is a usable last-resort (e.g. "Network
    // Error", "Request failed with status code 500") — better than
    // a localised fallback when the user is debugging.
    if (e.message) {
      return e.message
    }
  }
  // Non-axios Error subclass (sync throw, programming error).
  if (e instanceof Error && e.message) {
    return e.message
  }
  return fallback
}
