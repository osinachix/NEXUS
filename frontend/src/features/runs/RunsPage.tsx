import { useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useAgentRegistry } from '@/hooks/useAgentRegistry'
import { useRuns } from '@/hooks/useRuns'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { ChevronDownIcon } from '@/components/icons'
import { truncateId } from '@/lib/formatters'
import { RunsTable } from './RunsTable'
import { RunsTableSkeleton } from './RunsTableSkeleton'

const LIST_LIMIT = 100

/**
 * The NEXUS run history (Phase 6.3), rendered from GET /v1/runs. This is
 * explicitly NOT a durable audit log -- it only reflects runs recorded by
 * this API process since it last started, up to the bounded RunStore's
 * capacity (see README "Known limitations"). Status/agent filtering is
 * server-side (the same query params GET /v1/runs accepts); free-text
 * search and sort order are client-side, appropriate for the store's
 * bounded, small-by-design result set.
 *
 * An optional `?thread_id=` (Phase 6.4) restricts the list to one
 * session's runs -- how Session Detail's "View Runs" link works. It's
 * read here, not in a wrapper page, since it's just another server-side
 * filter alongside status/agent, not a different execution surface.
 */
export function RunsPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const threadIdFilter = searchParams.get('thread_id')

  const [statusFilter, setStatusFilter] = useState('')
  const [agentFilter, setAgentFilter] = useState('')
  const [search, setSearch] = useState('')
  const [sortOrder, setSortOrder] = useState<'newest' | 'oldest'>('newest')

  const { runs, total, status, error, refetch } = useRuns({
    limit: LIST_LIMIT,
    status: statusFilter || undefined,
    agent: agentFilter || undefined,
    thread_id: threadIdFilter ?? undefined,
  })
  const { agents } = useAgentRegistry()

  const clearThreadFilter = () => setSearchParams((params) => {
    const next = new URLSearchParams(params)
    next.delete('thread_id')
    return next
  })

  const hasActiveFilters = Boolean(statusFilter || agentFilter || search.trim() || threadIdFilter)

  const visibleRuns = useMemo(() => {
    const query = search.trim().toLowerCase()
    let list = query
      ? runs.filter((run) => run.request_id.toLowerCase().includes(query) || run.thread_id.toLowerCase().includes(query))
      : runs

    if (sortOrder === 'oldest') list = [...list].reverse()
    return list
  }, [runs, search, sortOrder])

  const clearFilters = () => {
    setStatusFilter('')
    setAgentFilter('')
    setSearch('')
    if (threadIdFilter) clearThreadFilter()
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-lg font-semibold text-text-primary">Runs</h1>
        <p className="text-sm text-text-muted">
          Recent executions recorded by this NEXUS runtime. This reflects the bounded, in-process
          run store, not a durable history -- a backend restart clears it.
        </p>
      </div>

      {threadIdFilter && (
        <div className="flex items-center gap-2 rounded-md border border-accent-dim bg-accent-subtle px-3 py-2 text-sm text-accent">
          <span>
            Showing runs for session <span className="font-mono">{truncateId(threadIdFilter, 16)}</span>
          </span>
          <button type="button" onClick={clearThreadFilter} className="ml-auto text-xs underline hover:no-underline">
            Clear
          </button>
        </div>
      )}

      <div className="flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label htmlFor="run-status-filter" className="text-[11px] font-medium tracking-wide text-text-muted uppercase">
            Status
          </label>
          <div className="relative">
            <select
              id="run-status-filter"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value)}
              className="w-36 appearance-none rounded-md border border-border-default bg-surface-2 py-1.5 pr-7 pl-2.5 text-sm text-text-primary hover:border-border-strong focus:border-accent"
            >
              <option value="">All statuses</option>
              <option value="completed">Completed</option>
              <option value="failed">Failed</option>
            </select>
            <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 text-text-muted" />
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="run-agent-filter" className="text-[11px] font-medium tracking-wide text-text-muted uppercase">
            Agent
          </label>
          <div className="relative">
            <select
              id="run-agent-filter"
              value={agentFilter}
              onChange={(event) => setAgentFilter(event.target.value)}
              className="w-40 appearance-none rounded-md border border-border-default bg-surface-2 py-1.5 pr-7 pl-2.5 text-sm text-text-primary hover:border-border-strong focus:border-accent"
            >
              <option value="">All agents</option>
              {agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
            <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 text-text-muted" />
          </div>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="run-search" className="text-[11px] font-medium tracking-wide text-text-muted uppercase">
            Search
          </label>
          <input
            id="run-search"
            type="text"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Request or thread ID"
            className="w-52 rounded-md border border-border-default bg-surface-2 px-2.5 py-1.5 text-sm text-text-primary placeholder:text-text-muted hover:border-border-strong focus:border-accent focus:outline-none"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="run-sort" className="text-[11px] font-medium tracking-wide text-text-muted uppercase">
            Order
          </label>
          <div className="relative">
            <select
              id="run-sort"
              value={sortOrder}
              onChange={(event) => setSortOrder(event.target.value as 'newest' | 'oldest')}
              className="w-32 appearance-none rounded-md border border-border-default bg-surface-2 py-1.5 pr-7 pl-2.5 text-sm text-text-primary hover:border-border-strong focus:border-accent"
            >
              <option value="newest">Newest</option>
              <option value="oldest">Oldest</option>
            </select>
            <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-2 -translate-y-1/2 text-text-muted" />
          </div>
        </div>

        {hasActiveFilters && (
          <button
            type="button"
            onClick={clearFilters}
            className="rounded-md border border-border-default bg-surface-2 px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
          >
            Clear filters
          </button>
        )}

        {status === 'ready' && (
          <span className="ml-auto self-end pb-1.5 text-xs text-text-muted">
            {total} run{total === 1 ? '' : 's'}
          </span>
        )}
      </div>

      {status === 'error' && error && (
        <div className="max-w-md">
          <ErrorPanel error={error} onRetry={refetch} />
        </div>
      )}

      {status === 'loading' && <RunsTableSkeleton />}

      {status === 'ready' && runs.length === 0 && !hasActiveFilters && (
        <div className="flex flex-1 flex-col items-center justify-center gap-3 rounded-md border border-dashed border-border-subtle py-16 text-center">
          <p className="text-sm font-medium text-text-primary">No runs yet</p>
          <p className="max-w-sm text-sm text-text-muted">
            Execute an agent in the Playground to create your first run.
          </p>
          <Link
            to="/playground"
            className="mt-1 rounded-md bg-accent px-4 py-2 text-sm font-medium text-surface-0 transition-opacity hover:opacity-90"
          >
            Open Playground
          </Link>
        </div>
      )}

      {status === 'ready' && runs.length > 0 && visibleRuns.length === 0 && (
        <div className="flex flex-1 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border-subtle py-16 text-center">
          <p className="text-sm text-text-muted">No runs match the current filters.</p>
          <button type="button" onClick={clearFilters} className="text-sm text-accent hover:underline">
            Clear filters
          </button>
        </div>
      )}

      {status === 'ready' && visibleRuns.length > 0 && <RunsTable runs={visibleRuns} />}
    </div>
  )
}
