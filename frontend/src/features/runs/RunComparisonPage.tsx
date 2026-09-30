import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { ExecutionTrace } from '@/features/playground/ExecutionTrace'
import { FinalResponse } from '@/features/playground/FinalResponse'
import { useRun } from '@/hooks/useRun'
import { useRuns } from '@/hooks/useRuns'
import { useRunComparison } from '@/hooks/useRunComparison'
import { formatCostUsd, formatDurationMs, formatTokenCount, truncateId } from '@/lib/formatters'
import { runToTraceState } from '@/lib/runToTrace'
import { agentDisplayName } from '@/types/agent'
import type { RunResponse } from '@/types/api'

function signedDelta(value: number | null, format: (value: number) => string): string {
  if (value === null) return 'Not available'
  return `${value > 0 ? '+' : value < 0 ? '−' : ''}${format(Math.abs(value))}`
}

function displayValue(value: string | number | null, fallback = 'Not reported'): string {
  return value === null ? fallback : String(value)
}

function toolNames(run: RunResponse): string {
  const names = [...new Set(run.tool_events.map((event) => event.tool))]
  return names.length ? names.join(', ') : 'No tool events'
}

export function RunComparisonPage() {
  const { requestId } = useParams<{ requestId: string }>()
  const { run: sourceRun, status: sourceStatus, error: sourceError } = useRun(requestId)
  const { runs, status: runsStatus, error: runsError } = useRuns({ limit: 100 })
  const { comparison, status, error, compare } = useRunComparison()
  const [selectedRunId, setSelectedRunId] = useState('')

  const candidates = useMemo(
    () => runs.filter((run) => run.request_id !== requestId),
    [runs, requestId],
  )
  const sourceTrace = useMemo(
    () => comparison ? runToTraceState(comparison.run_a) : null,
    [comparison],
  )
  const comparedTrace = useMemo(
    () => comparison ? runToTraceState(comparison.run_b) : null,
    [comparison],
  )

  if (sourceStatus === 'loading' || runsStatus === 'loading') {
    return <div className="p-6 text-sm text-text-muted" role="status">Loading retained runs…</div>
  }
  if (sourceStatus === 'not_found') {
    return <div className="p-6"><p className="text-sm text-text-primary">Run not found.</p><Link to="/runs" className="text-sm text-accent hover:underline">Back to Runs</Link></div>
  }
  if (sourceStatus === 'error' && sourceError) return <div className="p-6"><ErrorPanel error={sourceError} /></div>
  if (runsStatus === 'error' && runsError) return <div className="p-6"><ErrorPanel error={runsError} /></div>
  if (!sourceRun) return null

  const submitComparison = () => {
    if (requestId && selectedRunId && selectedRunId !== requestId) compare(requestId, selectedRunId)
  }

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
      <Link to={`/runs/${encodeURIComponent(sourceRun.request_id)}`} className="w-fit text-xs text-text-muted hover:text-text-secondary">
        &larr; Run {truncateId(sourceRun.request_id, 16)}
      </Link>
      <header className="flex flex-col gap-1">
        <h1 className="text-lg font-semibold text-text-primary">Compare runs</h1>
        <p className="text-sm text-text-muted">Differences are run B minus run A. Missing measurements stay unavailable; neither run is ranked.</p>
      </header>

      <div className="grid gap-3 rounded-md border border-border-subtle bg-surface-1 p-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
        <label className="flex min-w-0 flex-col gap-1 text-xs font-medium uppercase tracking-wide text-text-muted">
          Run B
          <select
            aria-label="Run B"
            value={selectedRunId}
            onChange={(event) => setSelectedRunId(event.target.value)}
            className="min-w-0 rounded-md border border-border-default bg-surface-2 px-2 py-2 text-sm normal-case text-text-primary"
          >
            <option value="">Select a retained run</option>
            {candidates.map((run) => (
              <option key={run.request_id} value={run.request_id}>
                {truncateId(run.request_id, 16)} · {run.agent ? agentDisplayName(run.agent) : 'Agent not reported'} · {run.status}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          disabled={!selectedRunId || selectedRunId === requestId || status === 'loading'}
          onClick={submitComparison}
          className="rounded-md border border-border-default bg-surface-2 px-3 py-2 text-sm text-text-primary hover:border-border-strong disabled:cursor-not-allowed disabled:opacity-50"
        >
          {status === 'loading' ? 'Comparing…' : 'Compare'}
        </button>
        {candidates.length === 0 && runsStatus === 'ready' && (
          <p className="text-xs text-text-muted sm:col-span-2">No other retained runs are available to compare.</p>
        )}
      </div>

      {status === 'error' && error && <ErrorPanel error={error} />}

      {comparison && status === 'ready' && sourceTrace && comparedTrace && (
        <>
          <div className="overflow-x-auto rounded-md border border-border-subtle">
            <table className="w-full min-w-[680px] text-left text-sm">
              <thead className="bg-surface-2 text-[11px] uppercase tracking-wide text-text-muted">
                <tr><th className="px-3 py-2">Field</th><th className="px-3 py-2">Run A</th><th className="px-3 py-2">Run B</th><th className="px-3 py-2">B − A</th></tr>
              </thead>
              <tbody className="divide-y divide-border-subtle text-text-secondary">
                <tr><th className="px-3 py-2 font-medium">Request ID</th><td className="px-3 py-2"><Link to={`/runs/${encodeURIComponent(comparison.run_a.request_id)}`} className="font-mono text-accent hover:underline">{truncateId(comparison.run_a.request_id, 16)}</Link></td><td className="px-3 py-2"><Link to={`/runs/${encodeURIComponent(comparison.run_b.request_id)}`} className="font-mono text-accent hover:underline">{truncateId(comparison.run_b.request_id, 16)}</Link></td><td className="px-3 py-2">Not applicable</td></tr>
                <tr><th className="px-3 py-2 font-medium">Status</th><td className="px-3 py-2">{comparison.run_a.status}</td><td className="px-3 py-2">{comparison.run_b.status}</td><td className="px-3 py-2">Not applicable</td></tr>
                <tr><th className="px-3 py-2 font-medium">Agent</th><td className="px-3 py-2">{comparison.run_a.agent ? agentDisplayName(comparison.run_a.agent) : 'Not reported'}</td><td className="px-3 py-2">{comparison.run_b.agent ? agentDisplayName(comparison.run_b.agent) : 'Not reported'}</td><td className="px-3 py-2">Not applicable</td></tr>
                <tr><th className="px-3 py-2 font-medium">Route</th><td className="px-3 py-2">{displayValue(comparison.run_a.route)}</td><td className="px-3 py-2">{displayValue(comparison.run_b.route)}</td><td className="px-3 py-2">Not applicable</td></tr>
                <tr><th className="px-3 py-2 font-medium">Duration</th><td className="px-3 py-2">{formatDurationMs(comparison.run_a.duration_ms)}</td><td className="px-3 py-2">{formatDurationMs(comparison.run_b.duration_ms)}</td><td className="px-3 py-2">{signedDelta(comparison.deltas.duration_ms, formatDurationMs)}</td></tr>
                <tr><th className="px-3 py-2 font-medium">Input tokens</th><td className="px-3 py-2">{formatTokenCount(comparison.run_a.usage?.input_tokens)}</td><td className="px-3 py-2">{formatTokenCount(comparison.run_b.usage?.input_tokens)}</td><td className="px-3 py-2">{signedDelta(comparison.deltas.input_tokens, formatTokenCount)}</td></tr>
                <tr><th className="px-3 py-2 font-medium">Output tokens</th><td className="px-3 py-2">{formatTokenCount(comparison.run_a.usage?.output_tokens)}</td><td className="px-3 py-2">{formatTokenCount(comparison.run_b.usage?.output_tokens)}</td><td className="px-3 py-2">{signedDelta(comparison.deltas.output_tokens, formatTokenCount)}</td></tr>
                <tr><th className="px-3 py-2 font-medium">Total tokens</th><td className="px-3 py-2">{formatTokenCount(comparison.run_a.usage?.total_tokens)}</td><td className="px-3 py-2">{formatTokenCount(comparison.run_b.usage?.total_tokens)}</td><td className="px-3 py-2">{signedDelta(comparison.deltas.total_tokens, formatTokenCount)}</td></tr>
                <tr><th className="px-3 py-2 font-medium">Cost</th><td className="px-3 py-2">{formatCostUsd(comparison.run_a.cost_usd)}</td><td className="px-3 py-2">{formatCostUsd(comparison.run_b.cost_usd)}</td><td className="px-3 py-2">{signedDelta(comparison.deltas.cost_usd, formatCostUsd)}</td></tr>
                <tr><th className="px-3 py-2 font-medium">Tool events</th><td className="px-3 py-2">{comparison.run_a.tool_events.length} · {toolNames(comparison.run_a)}</td><td className="px-3 py-2">{comparison.run_b.tool_events.length} · {toolNames(comparison.run_b)}</td><td className="px-3 py-2">{signedDelta(comparison.deltas.tool_event_count, (value) => String(value))}</td></tr>
              </tbody>
            </table>
          </div>

          <div className="grid gap-4 xl:grid-cols-2">
            <section className="flex min-w-0 flex-col gap-3" aria-label="Run A trace and response">
              <h2 className="text-sm font-semibold text-text-primary">Run A · {truncateId(comparison.run_a.request_id, 16)}</h2>
              <ExecutionTrace trace={sourceTrace} />
              {sourceTrace.runCompleted && sourceTrace.runCompleted.reply && <FinalResponse runCompleted={sourceTrace.runCompleted} />}
            </section>
            <section className="flex min-w-0 flex-col gap-3" aria-label="Run B trace and response">
              <h2 className="text-sm font-semibold text-text-primary">Run B · {truncateId(comparison.run_b.request_id, 16)}</h2>
              <ExecutionTrace trace={comparedTrace} />
              {comparedTrace.runCompleted && comparedTrace.runCompleted.reply && <FinalResponse runCompleted={comparedTrace.runCompleted} />}
            </section>
          </div>
        </>
      )}
    </div>
  )
}
