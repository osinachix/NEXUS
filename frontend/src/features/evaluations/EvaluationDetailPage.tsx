import { Link, useParams } from 'react-router-dom'
import { CopyButton } from '@/components/CopyButton'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { StatusIndicator } from '@/components/StatusIndicator'
import { useEvaluation } from '@/hooks/useEvaluations'
import { formatTimestamp, truncateId } from '@/lib/formatters'
import { EvaluationMetrics } from './EvaluationMetrics'

export function EvaluationDetailPage() {
  const { evaluationId } = useParams<{ evaluationId: string }>()
  const { summary, results, metrics, status, error, refetch } = useEvaluation(evaluationId)

  if (status === 'loading') return <div className="flex h-full flex-col gap-4 p-4 sm:p-6" aria-busy="true"><div className="h-6 w-48 animate-pulse rounded bg-surface-3" /><div className="h-28 max-w-2xl animate-pulse rounded bg-surface-3" /><div className="h-56 animate-pulse rounded bg-surface-3" /></div>
  if (status === 'error' && error) return <div className="max-w-xl p-4 sm:p-6"><ErrorPanel error={error} onRetry={refetch} /><Link to="/evaluations" className="mt-4 inline-block text-sm text-accent hover:underline">Back to Evaluations</Link></div>
  if (!summary || !metrics) return null

  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto p-4 sm:p-6">
      <header className="flex flex-col gap-3">
        <Link to="/evaluations" className="w-fit text-xs text-text-muted hover:text-text-secondary">&larr; Evaluations</Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2"><h1 className="text-lg font-semibold text-text-primary">Evaluation</h1><StatusIndicator status="completed" /><span className="font-mono text-sm text-text-secondary" title={summary.evaluation_id}>{truncateId(summary.evaluation_id, 18)}</span><CopyButton value={summary.evaluation_id} label="evaluation ID" /></div>
            <p className="mt-1 text-sm text-text-muted">{summary.dataset_name} · {summary.dataset_version} · Created {formatTimestamp(summary.created_at)}</p>
          </div>
        </div>
      </header>

      <section className="grid grid-cols-2 gap-2 rounded-md border border-border-subtle bg-surface-1 p-4 sm:grid-cols-4">
        <div><span className="block text-[11px] uppercase tracking-wide text-text-muted">Cases</span><span className="mt-1 block text-sm text-text-primary">{summary.total_cases}</span></div>
        <div><span className="block text-[11px] uppercase tracking-wide text-text-muted">Passed</span><span className="mt-1 block text-sm text-status-success">{summary.passed_cases}</span></div>
        <div><span className="block text-[11px] uppercase tracking-wide text-text-muted">Failed</span><span className="mt-1 block text-sm text-status-danger">{summary.failed_cases}</span></div>
        <div><span className="block text-[11px] uppercase tracking-wide text-text-muted">Created at</span><span className="mt-1 block text-sm text-text-primary">{formatTimestamp(summary.created_at)}</span></div>
      </section>

      <EvaluationMetrics metrics={metrics} routingAccuracy={summary.routing_accuracy} executionSuccessRate={summary.execution_success_rate} toolSuccessRate={summary.tool_success_rate} />

      <section className="flex flex-col gap-3" aria-labelledby="case-results-heading">
        <div><h2 id="case-results-heading" className="text-xs font-semibold uppercase tracking-wide text-text-muted">Case results</h2><p className="mt-1 text-xs text-text-muted">Pass means every dimension evaluated for that case passed. Dimensions not configured for a case are omitted.</p></div>
        {results.map((result) => (
          <article key={result.case_id} className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-1 p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div><h3 className="text-sm font-medium text-text-primary">{result.case_name}</h3><p className="mt-1 font-mono text-[11px] text-text-muted">{result.case_id}</p></div>
              <span className={`rounded border px-2 py-1 text-xs ${result.passed ? 'border-status-success/30 bg-status-success/10 text-status-success' : 'border-status-danger/30 bg-status-danger/10 text-status-danger'}`}>{result.passed ? 'Passed' : 'Failed'}</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {result.dimensions.map((dimension, index) => <span key={`${dimension.dimension}-${index}`} className={`rounded border px-2 py-1 text-xs ${dimension.passed ? 'border-status-success/20 text-status-success' : 'border-status-danger/20 text-status-danger'}`} title={dimension.detail}>{dimension.dimension}: {dimension.passed ? 'passed' : 'failed'}</span>)}
              {result.dimensions.length === 0 && <span className="text-xs text-text-muted">No dimensions were evaluated.</span>}
            </div>
            <div className="rounded border border-border-subtle bg-surface-0/40 p-3">
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">Actual response</p>
              <p className="whitespace-pre-wrap break-words text-sm text-text-secondary">{result.run.reply || 'No response was produced.'}</p>
            </div>
            {result.run.error_type && <p className="text-xs text-status-warning">Execution error type: <span className="font-mono">{result.run.error_type}</span></p>}
            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border-subtle pt-2 text-xs text-text-muted">
              <span>Duration: {Math.round(result.run.duration_ms)} ms</span>
              <Link to={`/runs/${encodeURIComponent(result.request_id)}`} className="text-accent hover:underline">View related run {truncateId(result.request_id, 12)} &rarr;</Link>
            </div>
          </article>
        ))}
      </section>
    </div>
  )
}
