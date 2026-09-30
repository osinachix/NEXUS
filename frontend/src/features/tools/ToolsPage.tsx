import { Link } from 'react-router-dom'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { useToolActivity, useToolRegistry } from '@/hooks/useTools'
import type { ToolActivityEvent, ToolDefinition } from '@/types/tool'

function ToolStatusBadge({ status }: { status: ToolDefinition['status'] }) {
  const active = status === 'active'
  return (
    <span className={`rounded border px-2 py-0.5 text-[11px] font-medium ${active
      ? 'border-status-success/40 bg-status-success/10 text-status-success'
      : 'border-status-warning/40 bg-status-warning/10 text-status-warning'
    }`}>
      {active ? 'Active' : 'Unavailable'}
    </span>
  )
}

function activityLabel(type: ToolActivityEvent['event_type']) {
  if (type === 'tool_completed') return 'Completed'
  if (type === 'tool_denied') return 'Denied'
  return 'Failed'
}

function activityStyle(type: ToolActivityEvent['event_type']) {
  if (type === 'tool_completed') return 'border-status-success/40 bg-status-success/10 text-status-success'
  if (type === 'tool_denied') return 'border-status-warning/40 bg-status-warning/10 text-status-warning'
  return 'border-status-danger/40 bg-status-danger-subtle text-status-danger'
}

function formatDuration(duration: number | null) {
  if (duration === null) return 'Not reported'
  return duration < 1000 ? `${Math.round(duration)} ms` : `${(duration / 1000).toFixed(2)} s`
}

function formatTimestamp(timestamp: string) {
  const date = new Date(timestamp)
  return Number.isNaN(date.getTime()) ? timestamp : date.toLocaleString()
}

function ToolCard({ tool }: { tool: ToolDefinition }) {
  return (
    <article className="flex min-w-0 flex-col gap-4 rounded-lg border border-border-subtle bg-surface-1 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="font-mono text-base font-semibold text-text-primary">{tool.name}</h2>
          <p className="mt-1 text-sm leading-relaxed text-text-secondary">{tool.description}</p>
        </div>
        <ToolStatusBadge status={tool.status} />
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-4 border-t border-border-subtle pt-4 sm:grid-cols-2">
        <section aria-label="Execution type" className="flex flex-col gap-1.5">
          <h3 className="text-[11px] font-medium uppercase tracking-wide text-text-muted">Execution</h3>
          <span className="w-fit rounded border border-border-default bg-surface-2 px-2 py-1 text-xs text-text-primary">
            Native NEXUS tool
          </span>
        </section>

        <section aria-label="Allowed agents" className="flex flex-col gap-1.5">
          <h3 className="text-[11px] font-medium uppercase tracking-wide text-text-muted">Allowed agents</h3>
          {tool.allowed_agents.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {tool.allowed_agents.map((agent) => (
                <Link
                  key={agent}
                  to={`/agents/${encodeURIComponent(agent)}`}
                  className="rounded border border-border-default bg-surface-2 px-2 py-1 font-mono text-xs text-accent hover:border-border-strong hover:underline"
                >
                  {agent}
                </Link>
              ))}
            </div>
          ) : (
            <span className="text-sm text-text-muted">No public agent is currently allowed.</span>
          )}
        </section>
      </div>

      <section aria-label="Enforced controls" className="flex flex-col gap-2 border-t border-border-subtle pt-4">
        <h3 className="text-[11px] font-medium uppercase tracking-wide text-text-muted">Enforced controls</h3>
        <ul className="grid grid-cols-1 gap-2 text-sm text-text-secondary md:grid-cols-2">
          {tool.controls.map((control) => <li key={control} className="flex gap-2"><span className="text-status-success">&#10003;</span><span>{control}</span></li>)}
        </ul>
      </section>
    </article>
  )
}

function ActivityItem({ event }: { event: ToolActivityEvent }) {
  return (
    <article className="grid min-w-0 grid-cols-1 gap-3 border-b border-border-subtle px-3 py-3 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div className="flex min-w-0 flex-col gap-2">
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          <span className={`rounded border px-2 py-0.5 text-[11px] font-medium ${activityStyle(event.event_type)}`}>
            {activityLabel(event.event_type)}
          </span>
          <span className="font-mono text-xs text-text-primary">{event.tool}</span>
          {event.agent && (
            <Link to={`/agents/${encodeURIComponent(event.agent)}`} className="text-xs text-accent hover:underline">
              {event.agent}
            </Link>
          )}
          <span className="text-xs text-text-muted">{formatTimestamp(event.timestamp)}</span>
        </div>
        <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-text-muted">
          <span>{formatDuration(event.duration_ms)}</span>
          {event.reason && <span>Reason: <span className="font-mono">{event.reason}</span></span>}
          {event.error_type && <span>Error type: <span className="font-mono">{event.error_type}</span></span>}
        </div>
      </div>
      <Link to={`/runs/${encodeURIComponent(event.request_id)}`} className="w-fit font-mono text-xs text-accent hover:underline">
        Run {event.request_id.slice(0, 12)}
      </Link>
    </article>
  )
}

export function ToolsPage() {
  const registry = useToolRegistry()
  const activity = useToolActivity()

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto p-4 sm:p-6">
      <header className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-3">
          <h1 className="text-lg font-semibold text-text-primary">Tools</h1>
          <span className="rounded border border-border-default bg-surface-2 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-text-muted">Read only</span>
        </div>
        <p className="max-w-3xl text-sm leading-relaxed text-text-muted">
          Inspect registered tools, the agents allowed to use them, and the controls enforced at execution time.
        </p>
      </header>

      <section className="flex flex-col gap-3" aria-labelledby="tool-registry-heading">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h2 id="tool-registry-heading" className="text-sm font-semibold text-text-primary">Tool registry</h2>
            <p className="mt-1 text-xs text-text-muted">Availability means registered and callable through a supported agent graph.</p>
          </div>
        </div>
        {registry.status === 'loading' && (
          <div className="h-48 animate-pulse rounded-lg border border-border-subtle bg-surface-1" aria-label="Loading tools" />
        )}
        {registry.status === 'error' && registry.error && (
          <div className="max-w-xl"><ErrorPanel error={registry.error} onRetry={registry.retry} /></div>
        )}
        {registry.status === 'ready' && registry.tools.length === 0 && (
          <div className="rounded-lg border border-dashed border-border-subtle p-8 text-center text-sm text-text-muted">
            No tools are registered with this NEXUS runtime.
          </div>
        )}
        {registry.status === 'ready' && registry.tools.length > 0 && (
          <div className="grid min-w-0 grid-cols-1 gap-3">{registry.tools.map((tool) => <ToolCard key={tool.id} tool={tool} />)}</div>
        )}
      </section>

      <section className="flex min-w-0 flex-col gap-3" aria-labelledby="tool-activity-heading">
        <div>
          <h2 id="tool-activity-heading" className="text-sm font-semibold text-text-primary">Recent activity from retained runs</h2>
          <p className="mt-1 max-w-3xl text-xs leading-relaxed text-text-muted">
            Activity is limited to the current API process and runs you own. The bounded run store resets when the API restarts, so this is not a complete audit history.
          </p>
        </div>
        {activity.status === 'loading' && (
          <div className="h-24 animate-pulse rounded-lg border border-border-subtle bg-surface-1" aria-label="Loading tool activity" />
        )}
        {activity.status === 'error' && activity.error && (
          <div className="max-w-xl"><ErrorPanel error={activity.error} onRetry={activity.retry} /></div>
        )}
        {activity.status === 'ready' && activity.activity?.items.length === 0 && (
          <div className="rounded-lg border border-dashed border-border-subtle p-6 text-sm text-text-muted">
            No retained activity.
          </div>
        )}
        {activity.status === 'ready' && activity.activity && activity.activity.items.length > 0 && (
          <div className="min-w-0 overflow-hidden rounded-lg border border-border-subtle bg-surface-1">
            <div className="border-b border-border-subtle px-3 py-2 text-xs text-text-muted">
              Showing {activity.activity.items.length} of {activity.activity.total} retained events
            </div>
            {activity.activity.items.map((event, index) => (
              <ActivityItem key={`${event.request_id}-${event.event_type}-${event.timestamp}-${index}`} event={event} />
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
