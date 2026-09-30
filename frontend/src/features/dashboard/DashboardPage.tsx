import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { useAgentRegistry } from '@/hooks/useAgentRegistry'
import { useEvaluations } from '@/hooks/useEvaluations'
import { useRunSummaries } from '@/hooks/useRunSummaries'
import { useToolActivity, useToolRegistry } from '@/hooks/useTools'
import { formatCostUsd, formatDurationMs, formatTokenCount, truncateId } from '@/lib/formatters'
import { agentDisplayName } from '@/types/agent'
import type { RunListItemSummary } from '@/types/api'
import type { ToolActivityEvent } from '@/types/tool'

const RECENT_LIMIT = 8
const EVALUATION_LIMIT = 5
const ACTIVITY_LIMIT = 5

function fullTimestamp(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString()
}

function Panel({
  title,
  description,
  action,
  children,
}: {
  title: string
  description?: string
  action?: ReactNode
  children: ReactNode
}) {
  return (
    <section className="flex min-w-0 flex-col gap-3 rounded-lg border border-border-subtle bg-surface-1 p-4" aria-label={title}>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">{title}</h2>
          {description && <p className="mt-1 text-xs leading-relaxed text-text-muted">{description}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  )
}

function MetricCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <article className="min-w-0 rounded-lg border border-border-subtle bg-surface-1 p-4">
      <h2 className="text-[11px] font-medium uppercase tracking-wide text-text-muted">{label}</h2>
      <p className="mt-2 break-words text-xl font-semibold text-text-primary">{value}</p>
      <p className="mt-1 text-xs text-text-muted">{detail}</p>
    </article>
  )
}

function LoadingRows({ label }: { label: string }) {
  return <div role="status" aria-label={label} className="flex flex-col gap-2"><div className="h-10 animate-pulse rounded bg-surface-2" /><div className="h-10 animate-pulse rounded bg-surface-2" /></div>
}

function RunStatus({ status }: { status: string }) {
  const style = status === 'completed'
    ? 'border-status-success/40 bg-status-success/10 text-status-success'
    : status === 'failed'
      ? 'border-status-danger/40 bg-status-danger-subtle text-status-danger'
      : 'border-border-default bg-surface-2 text-text-muted'
  return <span className={`w-fit rounded border px-2 py-0.5 text-[11px] font-medium ${style}`}>{status}</span>
}

function RecentRun({ run }: { run: RunListItemSummary }) {
  return (
    <article className="grid min-w-0 grid-cols-1 gap-2 border-b border-border-subtle py-3 last:border-b-0 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-center">
      <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1">
        <RunStatus status={run.status} />
        <Link to={`/runs/${encodeURIComponent(run.request_id)}`} className="font-mono text-xs text-accent hover:underline" title={run.request_id}>
          {truncateId(run.request_id, 14)}
        </Link>
        {run.agent && <Link to={`/agents/${encodeURIComponent(run.agent)}`} className="text-xs text-text-secondary hover:text-accent">{agentDisplayName(run.agent)}</Link>}
        <span className="text-xs text-text-muted">{run.route ? `Route ${run.route}` : run.agent ? 'Direct execution' : 'Route not reported'}</span>
      </div>
      <div className="flex min-w-0 flex-wrap gap-x-3 gap-y-1 text-xs text-text-muted sm:justify-end">
        <span>{formatDurationMs(run.duration_ms)}</span>
        <span>{formatTokenCount(run.usage?.total_tokens)} tokens</span>
        <span>{run.cost_usd === null ? 'Cost not reported' : formatCostUsd(run.cost_usd)}</span>
        <time dateTime={run.created_at}>{fullTimestamp(run.created_at)}</time>
      </div>
    </article>
  )
}

function RecentEvaluation({ evaluation }: { evaluation: ReturnType<typeof useEvaluations>['items'][number] }) {
  return (
    <article className="flex min-w-0 flex-col gap-2 border-b border-border-subtle py-3 last:border-b-0 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex min-w-0 flex-col gap-1">
        <Link to={`/evaluations/${encodeURIComponent(evaluation.evaluation_id)}`} className="w-fit text-sm font-medium text-accent hover:underline">
          {evaluation.dataset_name} <span className="font-mono text-xs text-text-muted">{truncateId(evaluation.evaluation_id, 12)}</span>
        </Link>
        <time dateTime={evaluation.created_at} className="text-xs text-text-muted">{fullTimestamp(evaluation.created_at)}</time>
      </div>
      <div className="flex flex-wrap gap-x-3 gap-y-1 text-xs text-text-secondary">
        <span>{evaluation.passed_cases} passed / {evaluation.total_cases} cases</span>
        <span>{evaluation.failed_cases} failed</span>
        <span>Execution {evaluation.execution_success_rate === null ? 'Not reported' : `${(evaluation.execution_success_rate * 100).toFixed(0)}%`}</span>
        <span>p50 {formatDurationMs(evaluation.metrics.latency_p50_ms)}</span>
        <span>{evaluation.metrics.total_tokens === null ? 'Tokens not reported' : `${formatTokenCount(evaluation.metrics.total_tokens)} tokens`}</span>
        <span>{evaluation.metrics.total_cost_usd === null ? 'Cost not reported' : formatCostUsd(evaluation.metrics.total_cost_usd)}</span>
      </div>
    </article>
  )
}

function ActivityRow({ event }: { event: ToolActivityEvent }) {
  const label = event.event_type === 'tool_completed' ? 'Completed' : event.event_type === 'tool_denied' ? 'Denied' : 'Failed'
  return (
    <article className="flex min-w-0 flex-wrap items-center justify-between gap-2 border-b border-border-subtle py-3 last:border-b-0">
      <div className="flex min-w-0 flex-wrap items-center gap-2 text-xs">
        <span className="rounded border border-border-default bg-surface-2 px-2 py-0.5 text-text-secondary">{label}</span>
        <span className="font-mono text-text-primary">{event.tool}</span>
        {event.agent && <Link to={`/agents/${encodeURIComponent(event.agent)}`} className="text-accent hover:underline">{agentDisplayName(event.agent)}</Link>}
        <span className="text-text-muted">{event.duration_ms === null ? 'Duration not reported' : formatDurationMs(event.duration_ms)}</span>
        <time dateTime={event.timestamp} className="text-text-muted">{fullTimestamp(event.timestamp)}</time>
      </div>
      <Link to={`/runs/${encodeURIComponent(event.request_id)}`} className="font-mono text-xs text-accent hover:underline">Run {truncateId(event.request_id, 12)}</Link>
    </article>
  )
}

export function DashboardPage() {
  const runs = useRunSummaries(RECENT_LIMIT)
  const evaluations = useEvaluations(EVALUATION_LIMIT)
  const activity = useToolActivity(ACTIVITY_LIMIT)
  const agents = useAgentRegistry()
  const tools = useToolRegistry()

  const completed = runs.items.filter((run) => run.status === 'completed').length
  const failed = runs.items.filter((run) => run.status === 'failed').length
  const averageDuration = runs.items.length
    ? runs.items.reduce((sum, run) => sum + run.duration_ms, 0) / runs.items.length
    : null
  const knownTokenRuns = runs.items.filter((run) => run.usage?.total_tokens !== null && run.usage?.total_tokens !== undefined)
  const knownTokenTotal = knownTokenRuns.reduce((sum, run) => sum + (run.usage?.total_tokens ?? 0), 0)
  const knownCostRuns = runs.items.filter((run) => run.cost_usd !== null)
  const knownCostTotal = knownCostRuns.reduce((sum, run) => sum + (run.cost_usd ?? 0), 0)
  const activeAgents = agents.agents.filter((agent) => agent.status === 'active')
  const activeTools = tools.tools.filter((tool) => tool.status === 'active')

  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto p-4 sm:p-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-accent">Runtime overview</p>
          <h1 className="mt-1 text-xl font-semibold text-text-primary">Dashboard</h1>
          <p className="mt-1 max-w-3xl text-sm leading-relaxed text-text-muted">
            Recent activity from this NEXUS API process. Run, evaluation, and tool history is bounded and may reset when the service restarts.
          </p>
        </div>
        <Link to="/playground" className="w-fit rounded-md bg-accent px-3 py-2 text-sm font-medium text-surface-0 hover:brightness-110 focus-visible:outline-offset-2">
          Open Playground
        </Link>
      </header>

      <section aria-label="Runtime metrics" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Retained runs"
          value={runs.status === 'ready' ? String(runs.total) : runs.status === 'loading' ? 'Loading...' : 'Unavailable'}
          detail={runs.status === 'error' ? 'Run summary could not be loaded' : 'Owned runs in the bounded process store'}
        />
        <MetricCard
          label="Recent outcomes"
          value={runs.status === 'ready' ? runs.items.length ? `${completed} completed · ${failed} failed` : 'No runs' : runs.status === 'loading' ? 'Loading...' : 'Unavailable'}
          detail={runs.status === 'ready' ? `Latest ${runs.items.length} run${runs.items.length === 1 ? '' : 's'} in the sample` : runs.status === 'error' ? 'Run summary could not be loaded' : 'Loading the recent run sample'}
        />
        <MetricCard
          label="Mean duration"
          value={runs.status === 'ready' ? averageDuration === null ? 'Not available' : formatDurationMs(averageDuration) : runs.status === 'loading' ? 'Loading...' : 'Unavailable'}
          detail={runs.status === 'error' ? 'Run summary could not be loaded' : averageDuration === null ? runs.status === 'ready' ? 'No retained run measurements' : 'Loading the recent run sample' : `Across ${runs.items.length} recent runs`}
        />
        <MetricCard
          label="Reported tokens"
          value={runs.status === 'ready' ? runs.items.length === 0 ? 'No run data' : knownTokenRuns.length ? formatTokenCount(knownTokenTotal) : 'Not reported' : runs.status === 'loading' ? 'Loading...' : 'Unavailable'}
          detail={runs.status === 'error' ? 'Run summary could not be loaded' : runs.status === 'ready' && knownTokenRuns.length < runs.items.length ? `Reported for ${knownTokenRuns.length} of ${runs.items.length} recent runs` : 'Across recent runs when provider usage is available'}
        />
        <MetricCard
          label="Reported cost"
          value={runs.status === 'ready' ? runs.items.length === 0 ? 'No run data' : knownCostRuns.length ? formatCostUsd(knownCostTotal) : 'Not reported' : runs.status === 'loading' ? 'Loading...' : 'Unavailable'}
          detail={runs.status === 'error' ? 'Run summary could not be loaded' : runs.status === 'ready' && knownCostRuns.length < runs.items.length ? `Reported for ${knownCostRuns.length} of ${runs.items.length} recent runs` : 'Across recent runs when pricing is configured'}
        />
        <MetricCard
          label="Evaluations"
          value={evaluations.status === 'ready' ? String(evaluations.total) : evaluations.status === 'loading' ? 'Loading...' : 'Unavailable'}
          detail="Owned evaluation records currently retained"
        />
        <MetricCard
          label="Active agents"
          value={agents.status === 'ready' ? `${activeAgents.length} / ${agents.agents.length}` : agents.status === 'loading' ? 'Loading...' : 'Unavailable'}
          detail="From the live agent registry"
        />
        <MetricCard
          label="Active tools"
          value={tools.status === 'ready' ? `${activeTools.length} / ${tools.tools.length}` : tools.status === 'loading' ? 'Loading...' : 'Unavailable'}
          detail="Bound and callable through supported agents"
        />
      </section>

      <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Recent runs" description="Lightweight summaries; open a run for its full trace." action={<Link to="/runs" className="text-xs text-accent hover:underline">All runs</Link>}>
          {runs.status === 'loading' && <LoadingRows label="Loading recent runs" />}
          {runs.status === 'error' && runs.error && <ErrorPanel error={runs.error} onRetry={runs.refetch} />}
          {runs.status === 'ready' && runs.items.length === 0 && (
            <div className="rounded-md border border-dashed border-border-subtle p-5 text-sm text-text-muted">
              No retained runs in this API process. Start a run in the <Link to="/playground" className="text-accent hover:underline">Playground</Link>; history resets when the service restarts.
            </div>
          )}
          {runs.status === 'ready' && runs.items.length > 0 && <div>{runs.items.map((run) => <RecentRun key={run.request_id} run={run} />)}</div>}
        </Panel>

        <Panel title="Recent evaluations" description="Recorded summaries from the bounded evaluation store." action={<Link to="/evaluations" className="text-xs text-accent hover:underline">All evaluations</Link>}>
          {evaluations.status === 'loading' && <LoadingRows label="Loading recent evaluations" />}
          {evaluations.status === 'error' && evaluations.error && <ErrorPanel error={evaluations.error} onRetry={evaluations.refetch} />}
          {evaluations.status === 'ready' && evaluations.items.length === 0 && (
            <div className="rounded-md border border-dashed border-border-subtle p-5 text-sm text-text-muted">
              No retained evaluations. Evaluation history is process-local and may be empty after a restart.
            </div>
          )}
          {evaluations.status === 'ready' && evaluations.items.length > 0 && <div>{evaluations.items.map((evaluation) => <RecentEvaluation key={evaluation.evaluation_id} evaluation={evaluation} />)}</div>}
        </Panel>
      </div>

      <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-2">
        <Panel title="Agent registry" description="Runtime-supported agents discovered from the API." action={<Link to="/agents" className="text-xs text-accent hover:underline">All agents</Link>}>
          {agents.status === 'loading' && <LoadingRows label="Loading agents" />}
          {agents.status === 'error' && agents.error && <ErrorPanel error={agents.error} onRetry={agents.refetch} />}
          {agents.status === 'ready' && agents.agents.length === 0 && <p className="text-sm text-text-muted">No agents are registered with this runtime.</p>}
          {agents.status === 'ready' && agents.agents.length > 0 && (
            <div className="flex flex-wrap gap-2">
              {agents.agents.map((agent) => (
                <Link key={agent.id} to={`/agents/${encodeURIComponent(agent.id)}`} className="rounded-md border border-border-default bg-surface-2 px-3 py-2 text-sm text-text-primary hover:border-border-strong hover:text-accent">
                  {agent.name}<span className="ml-2 text-[11px] text-text-muted">{agent.status}</span>
                </Link>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Tool registry" description="Available capabilities and their existing governance policy." action={<Link to="/tools" className="text-xs text-accent hover:underline">Tools and governance</Link>}>
          {tools.status === 'loading' && <LoadingRows label="Loading tools" />}
          {tools.status === 'error' && tools.error && <ErrorPanel error={tools.error} onRetry={tools.retry} />}
          {tools.status === 'ready' && tools.tools.length === 0 && <p className="text-sm text-text-muted">No tools are registered with this runtime.</p>}
          {tools.status === 'ready' && tools.tools.length > 0 && (
            <div className="flex flex-col gap-3">
              {tools.tools.map((tool) => (
                <article key={tool.id} className="flex min-w-0 flex-wrap items-start justify-between gap-3 border-b border-border-subtle pb-3 last:border-b-0 last:pb-0">
                  <div className="min-w-0">
                    <Link to="/tools" className="font-mono text-sm font-medium text-accent hover:underline">{tool.name}</Link>
                    <p className="mt-1 text-xs text-text-muted">{tool.status === 'active' ? 'Active' : 'Unavailable'} · {tool.execution_type} execution</p>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {tool.allowed_agents.map((agent) => <Link key={agent} to={`/agents/${encodeURIComponent(agent)}`} className="rounded border border-border-default px-2 py-1 font-mono text-xs text-text-secondary hover:text-accent">{agentDisplayName(agent)}</Link>)}
                  </div>
                </article>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Recent tool activity" description="Safe event metadata from runs you own. This is not a durable or complete audit history." action={<Link to="/tools" className="text-xs text-accent hover:underline">Open governance</Link>}>
        {activity.status === 'loading' && <LoadingRows label="Loading recent tool activity" />}
        {activity.status === 'error' && activity.error && <ErrorPanel error={activity.error} onRetry={activity.retry} />}
        {activity.status === 'ready' && activity.activity?.items.length === 0 && (
          <p className="rounded-md border border-dashed border-border-subtle p-5 text-sm text-text-muted">No retained tool activity for your runs.</p>
        )}
        {activity.status === 'ready' && activity.activity && activity.activity.items.length > 0 && (
          <>
            <p className="text-xs text-text-muted">Showing {activity.activity.items.length} of {activity.activity.total} retained events</p>
            <div>{activity.activity.items.map((event, index) => <ActivityRow key={`${event.request_id}-${event.timestamp}-${index}`} event={event} />)}</div>
          </>
        )}
      </Panel>
    </div>
  )
}
