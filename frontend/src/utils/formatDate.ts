/**
 * Parse an ISO-ish datetime string from the backend.
 *
 * Why not just `new Date(s)`: SQLAlchemy on SQLite drops `tzinfo` on
 * round-trip, so the API returns timestamps like `2026-04-29T07:58:04`
 * — same wall-clock as UTC but WITHOUT a `Z` or offset suffix. JS
 * `new Date(naiveIso)` interprets that as **local time**, not UTC, so
 * a sync that just happened renders as "vor 2 Std" for a user in CEST.
 *
 * We detect the "no zone marker" case and append `Z` so naive strings
 * are treated as UTC. ISO strings that already carry `Z` or an
 * `+HH:MM` / `-HH:MM` offset pass through unchanged.
 *
 * Exported so other call sites that compute "now − backend-stamp" can
 * reuse the same normalization. Anywhere `new Date(apiField)` flowed
 * into a duration / "remaining" / "X ago" computation has the same
 * off-by-tz-offset bug; use this helper instead.
 */
export function parseBackendDate(s: string): Date {
  const hasZone = /[Zz]$/.test(s) || /[+-]\d{2}:?\d{2}$/.test(s)
  return new Date(hasZone ? s : `${s}Z`)
}

export function formatDate(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  const d = parseBackendDate(dateStr)
  return d.toLocaleDateString('de-DE', { day: '2-digit', month: '2-digit', year: 'numeric' })
}

export function formatDateTime(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  const d = parseBackendDate(dateStr)
  return d.toLocaleDateString('de-DE', {
    day: '2-digit', month: '2-digit', year: 'numeric',
    hour: '2-digit', minute: '2-digit',
  })
}

export function formatTimeAgo(dateStr: string | null | undefined): string {
  if (!dateStr) return '-'
  const d = parseBackendDate(dateStr)
  const now = new Date()
  const diff = now.getTime() - d.getTime()
  const seconds = Math.floor(diff / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)
  const days = Math.floor(hours / 24)

  if (seconds < 60) return 'gerade eben'
  if (minutes < 60) return `vor ${minutes} Min.`
  if (hours < 24) return `vor ${hours} Std.`
  if (days < 7) return `vor ${days} Tagen`
  return formatDate(dateStr)
}
