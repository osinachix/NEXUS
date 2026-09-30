import { useEffect, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { formatCostUsd, formatDurationMs, formatTokenCount, truncateId } from '@/lib/formatters'
import type { RunResponse } from '@/types/api'

interface Props {
  requestId: string
  fallbackThreadId: string
  fallbackDurationMs: number
  fallbackRoute: string | null
}

function Field({ label, value, mono = true }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] tracking-wide text-text-muted uppercase">{label}</span>
      <span className={`text-sm text-text-primary ${mono ? 'font-mono' : ''}`} title={value}>
        {value}
      </span>
    </div>
  )
}

/**
 * Displays only values the backend actually returned (GET
 * /v1/runs/{request_id}) -- never invents token/cost figures. Fetches
 * the full RunResponse once the run completes, since the SSE
 * `run_completed` event itself deliberately doesn't carry token usage or
 * cost (see api.py's _sse_event_source: those live in the recorded
 * RunRecord, not the observability event stream).
 */
export function RunMetadataPanel({ requestId, fallbackThreadId, fallbackDurationMs, fallbackRoute }: Props) {
  const [run, setRun] = useState<RunResponse | null>(null)
  const [loadFailed, setLoadFailed] = useState(false)

  useEffect(() => {
    let cancelled = false
    setRun(null)
    setLoadFailed(false)
    nexusApi
      .getRun(requestId)
      .then((response) => {
        if (!cancelled) setRun(response)
      })
      .catch(() => {
        if (!cancelled) setLoadFailed(true)
      })
    return () => {
      cancelled = true
    }
  }, [requestId])

  const route = run?.route ?? fallbackRoute
  const durationMs = run?.duration_ms ?? fallbackDurationMs
  const threadId = run?.thread_id ?? fallbackThreadId

  return (
    <div className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-1 p-4">
      <span className="text-xs font-medium tracking-wide text-text-muted uppercase">Run Metadata</span>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-3">
        <Field label="Request ID" value={truncateId(requestId, 12)} />
        <Field label="Thread ID" value={truncateId(threadId, 12)} />
        <Field label="Route" value={route ?? 'Not reported'} />
        <Field label="Duration" value={formatDurationMs(durationMs)} />
        <Field label="Tokens" value={run ? formatTokenCount(run.usage?.total_tokens) : loadFailed ? 'Not reported' : 'Loading...'} />
        <Field label="Cost" value={run ? formatCostUsd(run.cost_usd) : loadFailed ? 'Not reported' : 'Loading...'} />
      </div>
    </div>
  )
}
