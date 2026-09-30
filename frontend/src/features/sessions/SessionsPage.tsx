import { useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { useSessions } from '@/hooks/useSessions'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { ChevronDownIcon } from '@/components/icons'
import { SessionsTable } from './SessionsTable'
import { SessionsTableSkeleton } from './SessionsTableSkeleton'

const LIST_LIMIT = 100

/**
 * The NEXUS session/state explorer (Phase 6.4), rendered from
 * GET /v1/sessions. A SESSION is persistent thread/workflow state, not an
 * execution record -- see the Runs page for execution history. This is
 * explicitly NOT a durable session index: it only reflects sessions
 * discoverable within the checkpointer's bounded scan window (see README
 * "Known limitations"). Search/sort are client-side, appropriate for this
 * small, bounded dataset.
 */
export function SessionsPage() {
  const [search, setSearch] = useState('')
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest')

  const { sessions, status, error, refetch } = useSessions({ limit: LIST_LIMIT })

  const hasActiveFilters = Boolean(search.trim())

  const visibleSessions = useMemo(() => {
    const query = search.trim().toLowerCase()
    let list = query
      ? sessions.filter(
          (s) =>
            s.thread_id.toLowerCase().includes(query) ||
            (s.last_route ?? '').toLowerCase().includes(query) ||
            (s.last_message_type ?? '').toLowerCase().includes(query),
        )
      : sessions

    if (sortOrder === 'oldest') list = [...list].reverse()
    return list
  }, [sessions, search, sortOrder])

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-lg font-semibold text-text-primary">Sessions</h1>
        <p className="text-sm text-text-muted">
          Persistent agent conversations and workflow state. This reflects the checkpointer's
          durable state directly, not a separate session database.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="session-search" className="text-[11px] font-medium tracking-wide text-text-muted uppercase">
            Search
          </label>
          <input
            id="session-search"
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Thread ID, route, or classification"
            className="w-64 rounded-md border border-border-default bg-surface-2 px-2.5 py-1.5 text-sm text-text-primary placeholder:text-text-muted hover:border-border-strong focus:border-accent focus:outline-none"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="session-sort" className="text-[11px] font-medium tracking-wide text-text-muted uppercase">
            Order
          </label>
          <div className="relative">
            <select
              id="session-sort"
              value={sortOrder}
              onChange={(event) => setSortOrder(event.target.value as 'newest' | 'oldest')}
              className="w-36 appearance-none rounded-md border border-border-default bg-surface-2 py-1.5 pr-7 pl-2.5 text-sm text-text-primary hover:border-border-strong focus:border-accent"
            >
              <option value="newest">Most recent</option>
              <option value="oldest">Oldest</option>
            </select>
            <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 text-text-muted" />
          </div>
        </div>

        {hasActiveFilters && (
          <button
            type="button"
            onClick={() => setSearch('')}
            className="rounded-md border border-border-default bg-surface-2 px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
          >
            Clear search
          </button>
        )}

        {status === 'ready' && (
          <span className="ml-auto self-end pb-1.5 text-xs text-text-muted">
            {sessions.length} session{sessions.length === 1 ? '' : 's'}
          </span>
        )}
      </div>

      {status === 'error' && error && (
        <div className="max-w-md">
          <ErrorPanel error={error} onRetry={refetch} />
        </div>
      )}

      {status === 'loading' && <SessionsTableSkeleton />}

      {status === 'ready' && sessions.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-md border border-dashed border-border-subtle py-16 text-center">
          <p className="text-sm font-medium text-text-primary">No sessions yet</p>
          <p className="max-w-sm text-sm text-text-muted">
            Start an execution in the Playground to create a session.
          </p>
          <Link
            to="/playground"
            className="mt-1 rounded-md bg-accent px-4 py-2 text-sm font-medium text-surface-0 transition-opacity hover:opacity-90"
          >
            Open Playground
          </Link>
        </div>
      )}

      {status === 'ready' && sessions.length > 0 && visibleSessions.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border-subtle py-16 text-center">
          <p className="text-sm text-text-muted">No sessions match this search.</p>
          <button type="button" onClick={() => setSearch('')} className="text-sm text-accent hover:underline">
            Clear search
          </button>
        </div>
      )}

      {status === 'ready' && visibleSessions.length > 0 && <SessionsTable sessions={visibleSessions} />}
    </div>
  )
}
