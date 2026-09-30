import { Link, useParams } from 'react-router-dom'
import { useSession } from '@/hooks/useSession'
import { CopyButton } from '@/components/CopyButton'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { truncateId } from '@/lib/formatters'
import { SessionMessageList } from './SessionMessageList'
import { SessionSummary } from './SessionSummary'

/**
 * One session's persistent state (Phase 6.4) -- a STATE inspector, not a
 * second execution surface. The Playground remains where turns are
 * actually sent; this page only reads and displays what the checkpointer
 * already durably holds for this thread. See CLAUDE.md's "State vs
 * Memory" distinction: this is state (what the active workflow needs),
 * not a long-term memory system.
 */
export function SessionDetailPage() {
  const { threadId } = useParams<{ threadId: string }>()
  const { session, status, error, refetch } = useSession(threadId)

  if (status === 'loading') {
    return (
      <div className="flex h-full flex-col gap-4 p-6" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded bg-surface-3" />
        <div className="h-24 w-full max-w-xl animate-pulse rounded bg-surface-3" />
        <div className="h-64 w-full animate-pulse rounded bg-surface-3" />
      </div>
    )
  }

  if (status === 'not_found') {
    return (
      <div className="flex h-full flex-col items-start gap-3 p-6">
        <p className="text-sm font-medium text-text-primary">Session not found</p>
        <p className="max-w-md text-sm text-text-secondary">
          This session may not exist, may be outside the checkpointer's discoverable state, or may
          not be accessible.
        </p>
        <Link to="/sessions" className="text-sm text-accent hover:underline">
          Back to Sessions
        </Link>
      </div>
    )
  }

  if (status === 'error' && error) {
    return (
      <div className="max-w-md p-6">
        <ErrorPanel error={error} onRetry={refetch} />
      </div>
    )
  }

  if (!session) return null

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
      <div className="flex flex-col gap-2">
        <Link to="/sessions" className="w-fit text-xs text-text-muted hover:text-text-secondary">
          &larr; Sessions
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-text-primary">Session</h1>
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-sm text-text-secondary" title={session.thread_id}>
                {truncateId(session.thread_id, 16)}
              </span>
              <CopyButton value={session.thread_id} label="thread ID" />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Link
              to={`/runs?thread_id=${encodeURIComponent(session.thread_id)}`}
              className="rounded-md border border-border-default bg-surface-2 px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
            >
              View Runs
            </Link>
            <button
              type="button"
              onClick={refetch}
              className="rounded-md border border-border-default bg-surface-2 px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
            >
              Refresh
            </button>
          </div>
        </div>
      </div>

      <SessionSummary session={session} />

      <div className="flex flex-col gap-2">
        <span className="text-xs font-medium tracking-wide text-text-muted uppercase">State / Conversation</span>
        <SessionMessageList messages={session.messages ?? []} />
      </div>
    </div>
  )
}
