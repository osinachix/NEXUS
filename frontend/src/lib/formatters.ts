/** Formatting helpers for the Playground/trace UI. Every function here is
 * pure and returns a display-safe string -- callers pass `null`/`undefined`
 * through explicitly rather than the UI silently inventing a value (see
 * CLAUDE.md sections 11/15: never fabricate token counts, cost, latency). */

const NOT_REPORTED = 'Not reported'

export function formatDurationMs(value: number | null | undefined): string {
  if (value === null || value === undefined) return NOT_REPORTED
  if (value < 1000) return `${Math.round(value)} ms`
  return `${(value / 1000).toFixed(2)} s`
}

export function formatTokenCount(value: number | null | undefined): string {
  if (value === null || value === undefined) return NOT_REPORTED
  return value.toLocaleString()
}

export function formatCostUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return NOT_REPORTED
  if (value === 0) return '$0.00'
  return `$${value.toFixed(value < 0.01 ? 6 : 4)}`
}

export function formatTimestamp(value: string | null | undefined): string {
  if (!value) return NOT_REPORTED
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value
  return date.toLocaleTimeString(undefined, { hour12: false, hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

export function truncateId(value: string, visible = 8): string {
  if (value.length <= visible + 3) return value
  return `${value.slice(0, visible)}...`
}
