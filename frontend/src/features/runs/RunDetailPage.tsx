import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { useRun } from '@/hooks/useRun'
import { StatusIndicator } from '@/components/StatusIndicator'
import { CopyButton } from '@/components/CopyButton'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { ExecutionTrace } from '@/features/playground/ExecutionTrace'
import { FinalResponse } from '@/features/playground/FinalResponse'
import { runToTraceState } from '@/lib/runToTrace'
import { truncateId } from '@/lib/formatters'
import { agentDisplayName } from '@/types/agent'
import { RunSummary } from './RunSummary'
import { useRunReplay } from '@/hooks/useRunReplay'

/**
 * One run's full execution record (Phase 6.3). The execution trace below
 * is rendered by the SAME `ExecutionTrace`/`FinalResponse` components the
 * Playground uses for a live SSE run -- `runToTraceState` (lib/runToTrace.ts)
 * is the only new code, and its job is reshaping stored data into the
 * same `TraceState` shape, not re-implementing trace rendering. A
 * direct-agent run's trace correctly shows no classifier/route step here,
 * exactly as it does live, because those events were never recorded.
 */
export function RunDetailPage() {
  const { requestId } = useParams<{ requestId: string }>()
  const { run, status, error } = useRun(requestId)
  const [confirmReplay, setConfirmReplay] = useState(false)
  const replay = useRunReplay()

  const trace = useMemo(() => (run ? runToTraceState(run) : null), [run])

  if (status === 'loading') {
    return (
      <div className="flex h-full flex-col gap-4 p-6" aria-busy="true">
        <div className="h-6 w-48 animate-pulse rounded bg-surface-3" />
        <div className="h-24 w-full max-w-xl animate-pulse rounded bg-surface-3" />
        <div className="h-64 w-full animate-pulse rounded bg-surface-3" />
      </div>
    )
  }

  if (status === 'not_found') {
    return (
      <div className="flex h-full flex-col items-start gap-3 p-6">
        <p className="text-sm font-medium text-text-primary">Run not found</p>
        <p className="max-w-md text-sm text-text-secondary">
          This run may have expired from the bounded runtime store or may no longer be available.
        </p>
        <Link to="/runs" className="text-sm text-accent hover:underline">
          Back to Runs
        </Link>
      </div>
    )
  }

  if (status === 'error' && error) {
    return (
      <div className="max-w-md p-6">
        <ErrorPanel error={error} />
      </div>
    )
  }

  if (!run || !trace) return null

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
      <div className="flex flex-col gap-2">
        <Link to="/runs" className="w-fit text-xs text-text-muted hover:text-text-secondary">
          &larr; Runs
        </Link>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-text-primary">Run</h1>
            <div className="flex items-center gap-1.5">
              <span className="font-mono text-sm text-text-secondary" title={run.request_id}>
                {truncateId(run.request_id, 16)}
              </span>
              <CopyButton value={run.request_id} label="request ID" />
            </div>
            <StatusIndicator status={run.status === 'completed' ? 'completed' : 'failed'} />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Link
              to={`/runs/${encodeURIComponent(run.request_id)}/compare`}
              className="rounded-md border border-border-default bg-surface-2 px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
            >
              Compare
            </Link>
            {run.agent && (
              <Link
                to={`/agents/${encodeURIComponent(run.agent)}`}
                className="rounded-md border border-border-default bg-surface-2 px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
              >
                Agent {agentDisplayName(run.agent)}
              </Link>
            )}
            {run.tool_events.length > 0 && (
              <Link
                to="/tools"
                className="rounded-md border border-border-default bg-surface-2 px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
              >
                Tool activity
              </Link>
            )}
            <button
              type="button"
              disabled={!run.replayable || replay.status === 'loading'}
              onClick={() => { replay.reset(); setConfirmReplay(true) }}
              className="rounded-md border border-border-default bg-surface-2 px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-50"
            >
              Re-run
            </button>
            <Link
              to={`/sessions/${encodeURIComponent(run.thread_id)}`}
              className="rounded-md border border-border-default bg-surface-2 px-3 py-1.5 text-sm text-text-secondary transition-colors hover:border-border-strong hover:text-text-primary"
            >
              View Session
            </Link>
          </div>
        </div>
      </div>

      {run.replay_of && (
        <p className="text-xs text-text-muted">
          Re-run of{' '}
          <Link to={`/runs/${encodeURIComponent(run.replay_of)}`} className="font-mono text-accent hover:underline">
            {truncateId(run.replay_of, 16)}
          </Link>
          {' '}in a new session.
        </p>
      )}

      {!run.replayable && (
        <p className="text-xs text-text-muted">
          {run.replay_unavailable_reason === 'thread_has_prior_state'
            ? 'Re-run unavailable: this turn used earlier conversation state that is not retained with the run.'
            : 'Re-run unavailable: the original input is not retained.'}
        </p>
      )}

      {confirmReplay && (
        <div role="alertdialog" aria-labelledby="replay-confirm-title" className="flex flex-col gap-3 rounded-md border border-border-default bg-surface-1 p-4">
          <div>
            <h2 id="replay-confirm-title" className="text-sm font-semibold text-text-primary">Run this input again?</h2>
            <p className="mt-1 text-sm text-text-secondary">
              This creates a new run in a fresh session and may execute agents and tools again. The original run and session stay unchanged. This is a fresh re-run, not a deterministic replay.
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={replay.status === 'loading'}
              onClick={async () => {
                setConfirmReplay(false)
                await replay.replay(run.request_id)
              }}
              className="rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-surface-0 disabled:opacity-50"
            >
              {replay.status === 'loading' ? 'Running…' : 'Confirm re-run'}
            </button>
            <button type="button" onClick={() => setConfirmReplay(false)} className="rounded-md border border-border-default px-3 py-1.5 text-sm text-text-secondary">
              Cancel
            </button>
          </div>
        </div>
      )}

      {replay.status === 'loading' && <p role="status" className="text-sm text-text-muted">Starting a new run…</p>}
      {replay.status === 'error' && replay.error && <ErrorPanel error={replay.error} />}
      {replay.status === 'ready' && replay.replayedRun && (
        <div role="status" className="rounded-md border border-status-success/40 bg-status-success-subtle p-3 text-sm text-text-primary">
          New run created:{' '}
          <Link to={`/runs/${encodeURIComponent(replay.replayedRun.request_id)}`} className="font-mono text-accent hover:underline">
            {truncateId(replay.replayedRun.request_id, 16)}
          </Link>
          . The source run is unchanged.
        </div>
      )}

      <RunSummary run={run} />

      {run.status === 'failed' && (
        <div role="alert" className="flex flex-col gap-1 rounded-md border border-status-danger/40 bg-status-danger-subtle p-3 text-sm">
          <span className="font-medium text-status-danger">Execution failed</span>
          {run.error_type && (
            <span className="text-text-secondary">
              Error type: <span className="font-mono">{run.error_type}</span>
            </span>
          )}
        </div>
      )}

      <div className="min-h-0 flex-1">
        <ExecutionTrace trace={trace} />
      </div>

      {trace.runCompleted && trace.runCompleted.reply ? (
        <FinalResponse runCompleted={trace.runCompleted} />
      ) : (
        <div className="rounded-md border border-border-subtle bg-surface-1 p-4 text-sm text-text-muted">
          No response was produced.
        </div>
      )}
    </div>
  )
}
