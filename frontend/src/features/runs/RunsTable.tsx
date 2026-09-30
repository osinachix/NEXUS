import { Link } from 'react-router-dom'
import { CopyButton } from '@/components/CopyButton'
import { StatusIndicator } from '@/components/StatusIndicator'
import { formatDurationMs, formatTimestamp, truncateId } from '@/lib/formatters'
import type { RunResponse } from '@/types/api'
import { agentDisplayName } from '@/types/agent'

const HEADERS = ['Status', 'Agent', 'Route', 'Request ID', 'Time', 'Duration', 'Tokens', 'Cost']

/** A run's overall status only ever comes back as 'completed' or 'failed'
 * (see run_store.RunRecord.status) -- both map directly onto
 * TraceStepStatus, so StatusIndicator (already used throughout the
 * Playground trace) is reused as-is rather than building a second status
 * badge component. */
function RunRow({ run }: { run: RunResponse }) {
  return (
    <tr className="border-b border-border-subtle last:border-0 hover:bg-surface-2">
      <td className="px-3 py-2">
        <StatusIndicator status={run.status === 'completed' ? 'completed' : 'failed'} compact />
      </td>
      <td className="px-3 py-2 text-text-primary">{run.agent ? agentDisplayName(run.agent) : '--'}</td>
      <td className="px-3 py-2 font-mono text-xs text-text-secondary">{run.route ?? '--'}</td>
      <td className="px-3 py-2">
        <div className="flex items-center gap-1.5">
          <Link
            to={`/runs/${encodeURIComponent(run.request_id)}`}
            className="font-mono text-xs text-accent hover:underline"
            title={run.request_id}
          >
            {truncateId(run.request_id, 12)}
          </Link>
          <CopyButton value={run.request_id} label="request ID" />
        </div>
      </td>
      <td className="px-3 py-2 whitespace-nowrap text-text-secondary">{formatTimestamp(run.completed_at)}</td>
      <td className="px-3 py-2 text-text-secondary">{formatDurationMs(run.duration_ms)}</td>
      <td className="px-3 py-2 text-text-secondary">{run.usage?.total_tokens?.toLocaleString() ?? '--'}</td>
      <td className="px-3 py-2 text-text-secondary">
        {run.cost_usd === null || run.cost_usd === undefined ? '--' : `$${run.cost_usd.toFixed(run.cost_usd < 0.01 ? 6 : 4)}`}
      </td>
    </tr>
  )
}

export function RunsTable({ runs }: { runs: RunResponse[] }) {
  return (
    <div className="overflow-x-auto rounded-md border border-border-subtle">
      <table className="w-full min-w-[720px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border-default bg-surface-1 text-[11px] tracking-wide text-text-muted uppercase">
            {HEADERS.map((header) => (
              <th key={header} className="px-3 py-2 font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {runs.map((run) => (
            <RunRow key={run.request_id} run={run} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
