import { CopyButton } from '@/components/CopyButton'
import { formatCostUsd, formatDurationMs, formatTokenCount, formatTimestamp, truncateId } from '@/lib/formatters'
import { agentDisplayName } from '@/types/agent'
import type { RunResponse } from '@/types/api'

function Field({ label, value, copyValue }: { label: string; value: string; copyValue?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] tracking-wide text-text-muted uppercase">{label}</span>
      <div className="flex items-center gap-1.5">
        <span className="font-mono text-sm text-text-primary" title={value}>
          {value}
        </span>
        {copyValue && <CopyButton value={copyValue} label={label} />}
      </div>
    </div>
  )
}

/** The run's metadata summary (Phase 6.3 spec section 15/21) -- only
 * fields the backend actually returned, "Not reported" (never a fake
 * zero) for anything unavailable, exactly like RunMetadataPanel already
 * does in the Playground. */
export function RunSummary({ run }: { run: RunResponse }) {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-1 p-4">
      <span className="text-xs font-medium tracking-wide text-text-muted uppercase">Summary</span>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        <Field label="Agent" value={run.agent ? agentDisplayName(run.agent) : 'Not reported'} />
        <Field label="Route" value={run.route ?? 'Not reported'} />
        <Field label="Duration" value={formatDurationMs(run.duration_ms)} />
        <Field label="Tokens" value={formatTokenCount(run.usage?.total_tokens)} />
        <Field label="Cost" value={formatCostUsd(run.cost_usd)} />
        <Field label="Started At" value={formatTimestamp(run.started_at)} />
        <Field label="Completed At" value={formatTimestamp(run.completed_at)} />
        <Field label="Request ID" value={truncateId(run.request_id, 14)} copyValue={run.request_id} />
        <Field label="Thread ID" value={truncateId(run.thread_id, 14)} copyValue={run.thread_id} />
      </div>
    </div>
  )
}
