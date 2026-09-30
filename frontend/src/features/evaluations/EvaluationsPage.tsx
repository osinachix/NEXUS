import { Link, useNavigate } from 'react-router-dom'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { formatCostUsd, formatDurationMs, formatTimestamp, formatTokenCount, truncateId } from '@/lib/formatters'
import { useEvaluations, useRunEvaluation } from '@/hooks/useEvaluations'
import { EvaluationComparisonPanel } from './EvaluationComparisonPanel'

const LIST_LIMIT = 100

export function EvaluationsPage() {
  const navigate = useNavigate()
  const { items, total, status, error, refetch } = useEvaluations(LIST_LIMIT)
  const { run, running, error: runError, clearError } = useRunEvaluation()

  const startEvaluation = async () => {
    clearError()
    try {
      const result = await run()
      refetch()
      navigate(`/evaluations/${encodeURIComponent(result.evaluation_id)}`)
    } catch {
      // The hook keeps the safe API error for the page to render.
    }
  }

  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto p-4 sm:p-6">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-text-primary">Evaluations</h1>
          <p className="mt-1 max-w-2xl text-sm text-text-muted">Run the baseline dataset through the NEXUS runtime, inspect measured case results, and compare evaluation summaries.</p>
        </div>
        <button type="button" onClick={startEvaluation} disabled={running} className="shrink-0 rounded-md bg-accent px-4 py-2 text-sm font-medium text-surface-0 transition-opacity hover:opacity-90 disabled:cursor-wait disabled:opacity-60">
          {running ? 'Running evaluation…' : 'Run Evaluation'}
        </button>
      </header>

      {running && (
        <div role="status" className="flex items-start gap-3 rounded-md border border-accent-dim bg-accent-subtle p-3 text-sm text-accent">
          <span className="mt-1 h-2 w-2 shrink-0 animate-pulse rounded-full bg-accent" />
          <span>The baseline evaluation runs synchronously. This request stays open until all cases finish; progress events are not available.</span>
        </div>
      )}
      {runError && <div className="max-w-xl"><ErrorPanel error={runError} onRetry={startEvaluation} /></div>}

      <section className="flex flex-col gap-3" aria-labelledby="recent-evaluations-heading">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="recent-evaluations-heading" className="text-xs font-semibold uppercase tracking-wide text-text-muted">Recent history</h2>
          {status === 'ready' && <span className="text-xs text-text-muted">{total} stored evaluation{total === 1 ? '' : 's'}</span>}
        </div>
        {status === 'loading' && <div className="flex flex-col gap-2" aria-label="Loading evaluations" aria-busy="true">{[0, 1, 2].map((item) => <div key={item} className="h-[74px] animate-pulse rounded-md border border-border-subtle bg-surface-1" />)}</div>}
        {status === 'error' && error && <div className="max-w-xl"><ErrorPanel error={error} onRetry={refetch} /></div>}
        {status === 'ready' && items.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-md border border-dashed border-border-subtle px-4 py-10 text-center">
            <p className="text-sm font-medium text-text-primary">No evaluations in this runtime</p>
            <p className="max-w-md text-sm text-text-muted">Run the baseline dataset to create a real evaluation. History is held in bounded process memory and clears when the API restarts.</p>
          </div>
        )}
        {status === 'ready' && items.length > 0 && (
          <div className="overflow-x-auto rounded-md border border-border-subtle">
            <table className="w-full min-w-[700px] text-left text-sm">
              <thead className="bg-surface-2 text-[11px] font-medium uppercase tracking-wide text-text-muted"><tr><th className="px-3 py-2.5">Evaluation</th><th className="px-3 py-2.5">Status</th><th className="px-3 py-2.5">Created</th><th className="px-3 py-2.5">Cases</th><th className="px-3 py-2.5">Latency p50</th><th className="px-3 py-2.5">Tokens</th><th className="px-3 py-2.5">Cost</th></tr></thead>
              <tbody className="divide-y divide-border-subtle">
                {items.map((evaluation) => (
                  <tr key={evaluation.evaluation_id} className="text-text-secondary hover:bg-surface-2/60">
                    <td className="px-3 py-3"><Link to={`/evaluations/${encodeURIComponent(evaluation.evaluation_id)}`} className="font-mono text-xs text-accent hover:underline" title={evaluation.evaluation_id}>{truncateId(evaluation.evaluation_id, 16)}</Link><span className="mt-1 block text-xs text-text-muted">{evaluation.dataset_name} · {evaluation.dataset_version}</span></td>
                    <td className="px-3 py-3"><span className="rounded border border-status-success/30 bg-status-success/10 px-2 py-1 text-xs text-status-success">Completed</span></td>
                    <td className="px-3 py-3 text-xs">{formatTimestamp(evaluation.created_at)}</td>
                    <td className="px-3 py-3 text-xs"><span className="text-status-success">{evaluation.passed_cases} passed</span><span className="mt-1 block text-text-muted">{evaluation.failed_cases} failed / {evaluation.total_cases} total</span></td>
                    <td className="px-3 py-3 text-xs">{formatDurationMs(evaluation.metrics.latency_p50_ms)}</td>
                    <td className="px-3 py-3 text-xs">{formatTokenCount(evaluation.metrics.total_tokens)}</td>
                    <td className="px-3 py-3 text-xs">{evaluation.metrics.total_cost_usd === null ? 'Not available' : formatCostUsd(evaluation.metrics.total_cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {status === 'ready' && items.length >= 2 && <EvaluationComparisonPanel evaluations={items} />}
      {status === 'ready' && items.length === 1 && <p className="text-xs text-text-muted">Run another evaluation to compare two stored evaluations.</p>}

    </div>
  )
}
