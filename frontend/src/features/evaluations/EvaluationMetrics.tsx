import { formatCostUsd, formatDurationMs, formatTokenCount } from '@/lib/formatters'
import type { RunMetrics } from '@/types/api'

function rate(value: number | null): string {
  return value === null ? 'Not available' : `${(value * 100).toFixed(1)}%`
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-1 rounded-md border border-border-subtle bg-surface-1 p-3">
      <span className="text-[11px] font-medium uppercase tracking-wide text-text-muted">{label}</span>
      <span className="truncate text-sm font-medium text-text-primary" title={value}>{value}</span>
    </div>
  )
}

export function EvaluationMetrics({ metrics, routingAccuracy, executionSuccessRate, toolSuccessRate }: {
  metrics: RunMetrics
  routingAccuracy: number | null
  executionSuccessRate: number
  toolSuccessRate: number | null
}) {
  return (
    <section className="flex flex-col gap-3" aria-label="Evaluation metrics">
      <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Aggregate metrics</h2>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-4">
        <Metric label="Latency p50" value={formatDurationMs(metrics.latency_p50_ms)} />
        <Metric label="Latency p95" value={formatDurationMs(metrics.latency_p95_ms)} />
        <Metric label="Latency p99" value={formatDurationMs(metrics.latency_p99_ms)} />
        <Metric label="Total tokens" value={formatTokenCount(metrics.total_tokens)} />
        <Metric label="Input tokens" value={formatTokenCount(metrics.total_input_tokens)} />
        <Metric label="Output tokens" value={formatTokenCount(metrics.total_output_tokens)} />
        <Metric label="Cost" value={metrics.total_cost_usd === null ? 'Not available' : formatCostUsd(metrics.total_cost_usd)} />
        <Metric label="Routing accuracy" value={rate(routingAccuracy)} />
        <Metric label="Execution success" value={rate(executionSuccessRate)} />
        <Metric label="Tool checks" value={rate(toolSuccessRate)} />
      </div>
    </section>
  )
}
