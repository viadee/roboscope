export function formatDuration(seconds: number | null | undefined): string {
  if (seconds == null || seconds === 0) return '-'
  if (seconds < 1) return `${Math.round(seconds * 1000)}ms`
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const mins = Math.floor(seconds / 60)
  const secs = Math.round(seconds % 60)
  if (mins < 60) return `${mins}m ${secs}s`
  const hours = Math.floor(mins / 60)
  const remainMins = mins % 60
  return `${hours}h ${remainMins}m`
}

export function formatPercent(value: number | null | undefined): string {
  if (value == null) return '-'
  return `${value.toFixed(1)}%`
}
