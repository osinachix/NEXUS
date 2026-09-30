import { useState } from 'react'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { formatCostUsd, formatDurationMs } from '@/lib/formatters'
import type { EvaluationSummary } from '@/types/api'
import { useEvaluationComparison } from '@/hooks/useEvaluations'

function delta(value: number | null, format: (value: number) => string): string {
  if (value === null) return 'Not available'
  const sign = value > 0 ? '+' : ''
  return `${sign}${format(value)}`
}

const count = (value: number) => String(value)

export function EvaluationComparisonPanel({ evaluations }: { evaluations: EvaluationSummary[] }) {
  const [evaluationA, setEvaluationA] = useState('')
  const [evaluationB, setEvaluationB] = useState('')
  const { comparison, status, error, compare } = useEvaluationComparison()
  const options = evaluations.map((evaluation) => (
    <option key={evaluation.evaluation_id} value={evaluation.evaluation_id}>
      {evaluation.evaluation_id} · {evaluation.dataset_name} {evaluation.dataset_version}
    </option>
  ))

  return (
    <section className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-1 p-4" aria-labelledby="compare-heading">
      <div>
        <h2 id="compare-heading" className="text-sm font-semibold text-text-primary">Compare evaluations</h2>
        <p className="mt-1 text-xs text-text-muted">Deltas are evaluation B minus evaluation A. They describe measured values without ranking either run.</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto]">
        <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">
          Evaluation A
          <select aria-label="Evaluation A" value={evaluationA} onChange={(event) => setEvaluationA(event.target.value)} className="min-w-0 rounded-md border border-border-default bg-surface-2 px-2 py-2 text-xs normal-case text-text-primary">
            <option value="">Select evaluation</option>{options}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-[11px] font-medium uppercase tracking-wide text-text-muted">
          Evaluation B
          <select aria-label="Evaluation B" value={evaluationB} onChange={(event) => setEvaluationB(event.target.value)} className="min-w-0 rounded-md border border-border-default bg-surface-2 px-2 py-2 text-xs normal-case text-text-primary">
            <option value="">Select evaluation</option>{options}
          </select>
        </label>
        <button type="button" disabled={!evaluationA || !evaluationB || evaluationA === evaluationB || status === 'loading'} onClick={() => compare(evaluationA, evaluationB)} className="self-end rounded-md border border-border-default bg-surface-2 px-3 py-2 text-sm text-text-primary hover:border-border-strong disabled:cursor-not-allowed disabled:opacity-50">
          {status === 'loading' ? 'Comparing…' : 'Compare'}
        </button>
      </div>
      {status === 'error' && error && <ErrorPanel error={error} />}
      {comparison && status === 'ready' && (
        <div className="overflow-x-auto rounded-md border border-border-subtle">
          <table className="w-full min-w-[500px] text-left text-sm">
            <thead className="bg-surface-2 text-[11px] uppercase tracking-wide text-text-muted"><tr><th className="px-3 py-2">Metric</th><th className="px-3 py-2">Evaluation A</th><th className="px-3 py-2">Evaluation B</th><th className="px-3 py-2">Delta</th></tr></thead>
            <tbody className="divide-y divide-border-subtle text-text-secondary">
              <tr><th className="px-3 py-2 font-medium">Passed cases</th><td className="px-3 py-2">{comparison.summary_a.passed_cases}</td><td className="px-3 py-2">{comparison.summary_b.passed_cases}</td><td className="px-3 py-2">{delta(comparison.passed_cases_delta, count)}</td></tr>
              <tr><th className="px-3 py-2 font-medium">Routing accuracy</th><td className="px-3 py-2">{comparison.summary_a.routing_accuracy === null ? 'Not available' : `${(comparison.summary_a.routing_accuracy * 100).toFixed(1)}%`}</td><td className="px-3 py-2">{comparison.summary_b.routing_accuracy === null ? 'Not available' : `${(comparison.summary_b.routing_accuracy * 100).toFixed(1)}%`}</td><td className="px-3 py-2">{delta(comparison.routing_accuracy_delta, (value) => `${(value * 100).toFixed(1)} pp`)}</td></tr>
              <tr><th className="px-3 py-2 font-medium">Execution success</th><td className="px-3 py-2">{(comparison.summary_a.execution_success_rate * 100).toFixed(1)}%</td><td className="px-3 py-2">{(comparison.summary_b.execution_success_rate * 100).toFixed(1)}%</td><td className="px-3 py-2">{delta(comparison.execution_success_rate_delta, (value) => `${(value * 100).toFixed(1)} pp`)}</td></tr>
              <tr><th className="px-3 py-2 font-medium">Tool checks</th><td className="px-3 py-2">{comparison.summary_a.tool_success_rate === null ? 'Not available' : `${(comparison.summary_a.tool_success_rate * 100).toFixed(1)}%`}</td><td className="px-3 py-2">{comparison.summary_b.tool_success_rate === null ? 'Not available' : `${(comparison.summary_b.tool_success_rate * 100).toFixed(1)}%`}</td><td className="px-3 py-2">{delta(comparison.tool_success_rate_delta, (value) => `${(value * 100).toFixed(1)} pp`)}</td></tr>
              <tr><th className="px-3 py-2 font-medium">Latency p50</th><td className="px-3 py-2">{formatDurationMs(comparison.summary_a.metrics.latency_p50_ms)}</td><td className="px-3 py-2">{formatDurationMs(comparison.summary_b.metrics.latency_p50_ms)}</td><td className="px-3 py-2">{delta(comparison.latency_p50_delta_ms, formatDurationMs)}</td></tr>
              <tr><th className="px-3 py-2 font-medium">Latency p95</th><td className="px-3 py-2">{formatDurationMs(comparison.summary_a.metrics.latency_p95_ms)}</td><td className="px-3 py-2">{formatDurationMs(comparison.summary_b.metrics.latency_p95_ms)}</td><td className="px-3 py-2">{delta(comparison.latency_p95_delta_ms, formatDurationMs)}</td></tr>
              <tr><th className="px-3 py-2 font-medium">Latency p99</th><td className="px-3 py-2">{formatDurationMs(comparison.summary_a.metrics.latency_p99_ms)}</td><td className="px-3 py-2">{formatDurationMs(comparison.summary_b.metrics.latency_p99_ms)}</td><td className="px-3 py-2">{delta(comparison.latency_p99_delta_ms, formatDurationMs)}</td></tr>
              <tr><th className="px-3 py-2 font-medium">Cost</th><td className="px-3 py-2">{comparison.summary_a.metrics.total_cost_usd === null ? 'Not available' : formatCostUsd(comparison.summary_a.metrics.total_cost_usd)}</td><td className="px-3 py-2">{comparison.summary_b.metrics.total_cost_usd === null ? 'Not available' : formatCostUsd(comparison.summary_b.metrics.total_cost_usd)}</td><td className="px-3 py-2">{delta(comparison.total_cost_usd_delta, formatCostUsd)}</td></tr>
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
