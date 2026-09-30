import { Link } from 'react-router-dom'
import { SpinnerIcon } from '@/components/icons'
import { truncateId } from '@/lib/formatters'
import { AgentGrid } from './AgentGrid'
import { AgentModeSelector } from './AgentModeSelector'
import { ErrorPanel } from './ErrorPanel'
import { ExecutionTrace } from './ExecutionTrace'
import { FinalResponse } from './FinalResponse'
import { MessageComposer } from './MessageComposer'
import { RouteVisualization } from './RouteVisualization'
import { RunMetadataPanel } from './RunMetadataPanel'
import { usePlaygroundExecution } from './usePlaygroundExecution'

/**
 * The Phase 6.1 vertical slice: a real NEXUS session, automatic or
 * direct-agent execution, a live SSE-driven execution trace, and the
 * real final response -- all against the actual running backend. See
 * usePlaygroundExecution.ts for the state/orchestration, lib/sseClient.ts
 * for the streaming transport, and lib/traceReducer.ts for how raw events
 * become the trace shown here.
 *
 * `initialAgentId` (Phase 6.2) comes from the Test Agent flow's
 * `/playground?agent=<id>` URL -- see PlaygroundPage.tsx, which is the
 * only thing that reads the URL. This component stays a plain,
 * URL-agnostic execution surface.
 */
export function Playground({ initialAgentId }: { initialAgentId?: string }) {
  const {
    threadId,
    sessionStatus,
    sessionError,
    mode,
    setMode,
    isRunning,
    trace,
    submitError,
    submit,
    cancel,
    retrySession,
    agents,
    agentsStatus,
    agentsError,
    retryAgents,
    invalidAgentRequested,
  } = usePlaygroundExecution(initialAgentId)

  const composerDisabled = sessionStatus !== 'ready'
  const composerDisabledReason =
    sessionStatus === 'creating' ? 'Creating session...' : sessionStatus === 'error' ? 'Session unavailable' : undefined

  return (
    <div className="flex h-full min-h-0 gap-4 overflow-hidden p-4">
      <aside className="flex w-[340px] shrink-0 flex-col gap-4 overflow-y-auto">
        <div className="flex flex-col gap-1 rounded-md border border-border-subtle bg-surface-1 p-3">
          <span className="text-xs font-medium tracking-wide text-text-muted uppercase">Session</span>
          {sessionStatus === 'creating' && (
            <span className="flex items-center gap-1.5 font-mono text-sm text-text-muted">
              <SpinnerIcon /> Creating session
            </span>
          )}
          {sessionStatus === 'ready' && threadId && (
            <div className="flex items-center justify-between gap-2">
              <span className="font-mono text-sm text-text-primary" title={threadId}>
                {truncateId(threadId, 20)}
              </span>
              {/* Only shown once a turn has actually completed: before that,
                  the thread has no persisted checkpoint state yet (session
                  creation alone doesn't write one), so Session Detail would
                  just 404 -- see the Phase 6.4 spec's "after a session
                  exists" wording. */}
              {trace.outcome !== 'idle' && (
                <Link to={`/sessions/${encodeURIComponent(threadId)}`} className="shrink-0 text-xs text-accent hover:underline">
                  View Session
                </Link>
              )}
            </div>
          )}
          {sessionStatus === 'error' && <span className="text-sm text-status-danger">Session unavailable</span>}
        </div>

        {sessionError && <ErrorPanel error={sessionError} onRetry={retrySession} />}

        {invalidAgentRequested && (
          <div role="alert" className="rounded-md border border-status-warning/40 bg-status-warning-subtle p-3 text-sm text-status-warning">
            &quot;{invalidAgentRequested}&quot; is not an available agent. Falling back to Auto Route.
          </div>
        )}

        {agentsStatus === 'error' && agentsError && <ErrorPanel error={agentsError} onRetry={retryAgents} />}

        <AgentModeSelector mode={mode} onChange={setMode} agents={agents} disabled={isRunning} />

        <AgentGrid trace={trace} agents={agents} />

        <MessageComposer
          onSubmit={submit}
          onCancel={cancel}
          isRunning={isRunning}
          disabled={composerDisabled}
          disabledReason={composerDisabledReason}
        />

        {submitError && <ErrorPanel error={submitError} />}
      </aside>

      <section className="flex min-w-0 flex-1 flex-col gap-4 overflow-hidden">
        {trace.outcome !== 'idle' && <RouteVisualization mode={mode} trace={trace} agents={agents} />}

        <ExecutionTrace trace={trace} />

        {trace.failureReason && (
          <div role="alert" className="rounded-md border border-status-danger/40 bg-status-danger-subtle p-3 text-sm text-status-danger">
            {trace.failureReason}
          </div>
        )}

        {trace.runCompleted && (
          <div className="flex shrink-0 flex-col gap-3">
            <FinalResponse runCompleted={trace.runCompleted} />
            <RunMetadataPanel
              requestId={trace.runCompleted.request_id}
              fallbackThreadId={trace.runCompleted.thread_id}
              fallbackDurationMs={trace.runCompleted.duration_ms}
              fallbackRoute={trace.runCompleted.route}
            />
          </div>
        )}
      </section>
    </div>
  )
}
