import { CrossIcon } from '@/components/icons'
import { NexusApiError } from '@/types/api'

const TITLES: Record<string, string> = {
  UNAUTHENTICATED: 'Authentication required',
  THREAD_ACCESS_DENIED: 'Session not accessible',
  RATE_LIMITED: 'Rate limit reached',
  SESSION_NOT_FOUND: 'Session not found',
  RUN_NOT_FOUND: 'Run not found',
  INVALID_REQUEST: 'Invalid request',
  NETWORK_ERROR: 'NEXUS is unreachable',
  STREAM_ERROR: 'Connection interrupted',
  INTERNAL_ERROR: 'Execution failed',
}

/**
 * Renders NEXUS's own safe error shape ({error: {code, message}} --
 * see SECURITY.md section 12) as a polished panel. Never renders a raw
 * exception, stack trace, or response body -- only the structured fields
 * the backend already guarantees are safe to display.
 */
export function ErrorPanel({ error, onRetry }: { error: NexusApiError; onRetry?: () => void }) {
  const title = TITLES[error.code] ?? 'Execution failed'

  return (
    <div
      role="alert"
      className="flex flex-col gap-2 rounded-md border border-status-danger/40 bg-status-danger-subtle p-4"
    >
      <div className="flex items-center gap-2 text-status-danger">
        <CrossIcon />
        <span className="text-sm font-semibold">{title}</span>
      </div>
      <p className="text-sm text-text-secondary">{error.message}</p>
      {error.code === 'RATE_LIMITED' && error.retryAfterSeconds !== null && (
        <p className="text-xs text-text-muted">Retry after {error.retryAfterSeconds}s.</p>
      )}
      <div className="flex items-center gap-3 pt-1 text-xs text-text-muted">
        <span className="font-mono">{error.code}</span>
        {error.status > 0 && <span>HTTP {error.status}</span>}
      </div>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-1 w-fit rounded-md border border-border-default bg-surface-2 px-3 py-1.5 text-xs font-medium text-text-primary transition-colors hover:border-border-strong"
        >
          Retry
        </button>
      )}
    </div>
  )
}
