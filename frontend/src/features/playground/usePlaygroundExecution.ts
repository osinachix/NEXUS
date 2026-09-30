import { useCallback, useEffect, useRef, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { nexusSse, type SseHandle } from '@/lib/sseClient'
import { initialTraceState, reduceTraceEvent } from '@/lib/traceReducer'
import { NexusApiError } from '@/types/api'
import type { Agent, ExecutionMode } from '@/types/agent'
import type { TraceState } from '@/types/trace'
import { useAgentRegistry, type AgentRegistryStatus } from '@/hooks/useAgentRegistry'

export type SessionStatus = 'creating' | 'ready' | 'error'

export interface UsePlaygroundExecution {
  threadId: string | null
  sessionStatus: SessionStatus
  sessionError: NexusApiError | null
  mode: ExecutionMode
  setMode: (mode: ExecutionMode) => void
  isRunning: boolean
  trace: TraceState
  submitError: NexusApiError | null
  submit: (message: string) => void
  cancel: () => void
  retrySession: () => void
  agents: Agent[]
  agentsStatus: AgentRegistryStatus
  agentsError: NexusApiError | null
  retryAgents: () => void
  invalidAgentRequested: string | null
}

/**
 * Owns the Playground's application state -- connection/session status,
 * current execution mode, in-flight trace, and errors -- kept separate
 * from presentational components (see CLAUDE.md section 21: state
 * clearly separated from UI). One real NEXUS session (thread_id) is
 * created once and reused for every message sent from this hook, per
 * the Phase 6.1 spec's "do not create a new session for every message."
 *
 * `initialAgentId` (Phase 6.2) lets the Test Agent flow preselect a
 * direct-agent mode via the URL (`/playground?agent=<id>`). It is
 * applied at most once, and only against the real registry: an
 * unknown/inactive/auto-only agent id falls back to Auto Route and is
 * surfaced via `invalidAgentRequested`, never silently dropped.
 */
export function usePlaygroundExecution(initialAgentId?: string): UsePlaygroundExecution {
  const { agents, status: agentsStatus, error: agentsError, refetch: retryAgents } = useAgentRegistry()

  const [threadId, setThreadId] = useState<string | null>(null)
  const [sessionStatus, setSessionStatus] = useState<SessionStatus>('creating')
  const [sessionError, setSessionError] = useState<NexusApiError | null>(null)
  const [mode, setMode] = useState<ExecutionMode>({ kind: 'auto' })
  const [isRunning, setIsRunning] = useState(false)
  const [trace, setTrace] = useState<TraceState>(initialTraceState())
  const [submitError, setSubmitError] = useState<NexusApiError | null>(null)
  const [invalidAgentRequested, setInvalidAgentRequested] = useState<string | null>(null)

  const streamHandle = useRef<SseHandle | null>(null)
  const sessionAttempt = useRef(0)
  const appliedInitialAgent = useRef(false)

  useEffect(() => {
    if (!initialAgentId || appliedInitialAgent.current || agentsStatus !== 'ready') return
    appliedInitialAgent.current = true
    const candidate = agents.find((a) => a.id === initialAgentId)
    if (candidate && candidate.status === 'active' && candidate.execution_mode.includes('direct')) {
      setMode({ kind: 'direct', agent: candidate.id })
    } else {
      setInvalidAgentRequested(initialAgentId)
    }
  }, [initialAgentId, agentsStatus, agents])

  const createSession = useCallback(() => {
    const attempt = (sessionAttempt.current += 1)
    setSessionStatus('creating')
    setSessionError(null)
    nexusApi
      .createSession()
      .then((response) => {
        if (sessionAttempt.current !== attempt) return
        setThreadId(response.thread_id)
        setSessionStatus('ready')
      })
      .catch((error: unknown) => {
        if (sessionAttempt.current !== attempt) return
        setSessionStatus('error')
        setSessionError(
          error instanceof NexusApiError
            ? error
            : new NexusApiError(0, { code: 'UNKNOWN_ERROR', message: 'Could not create a NEXUS session.' }),
        )
      })
  }, [])

  useEffect(() => {
    createSession()
    return () => {
      streamHandle.current?.cancel()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const submit = useCallback(
    (message: string) => {
      if (!threadId || isRunning) return

      setSubmitError(null)
      setTrace(initialTraceState())
      setIsRunning(true)

      const agent = mode.kind === 'direct' ? mode.agent : undefined

      streamHandle.current = nexusSse.stream(
        threadId,
        { message, agent },
        {
          onEvent: (event) => setTrace((prev) => reduceTraceEvent(prev, event)),
          onError: (error) => {
            setSubmitError(error)
            setIsRunning(false)
          },
          onClose: () => {
            setIsRunning(false)
          },
        },
      )
    },
    [threadId, isRunning, mode],
  )

  const cancel = useCallback(() => {
    streamHandle.current?.cancel()
  }, [])

  return {
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
    retrySession: createSession,
    agents,
    agentsStatus,
    agentsError,
    retryAgents,
    invalidAgentRequested,
  }
}
