import { useEffect, useRef, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { NexusApiError } from '@/types/api'
import type { Agent } from '@/types/agent'

export type AgentDetailStatus = 'loading' | 'ready' | 'not_found' | 'error'

export interface UseAgent {
  agent: Agent | null
  status: AgentDetailStatus
  error: NexusApiError | null
}

/** Fetches one agent's detail (`GET /v1/agents/{id}`) -- used by the
 * agent detail view. Distinguishes 'not_found' (AGENT_NOT_FOUND, a 404)
 * from other errors so the UI can show a clear "no such agent" state
 * rather than a generic failure panel. */
export function useAgent(agentId: string | undefined): UseAgent {
  const [agent, setAgent] = useState<Agent | null>(null)
  const [status, setStatus] = useState<AgentDetailStatus>('loading')
  const [error, setError] = useState<NexusApiError | null>(null)
  const attempt = useRef(0)

  useEffect(() => {
    if (!agentId) {
      setAgent(null)
      setStatus('not_found')
      return
    }
    const current = (attempt.current += 1)
    setStatus('loading')
    setError(null)
    nexusApi
      .getAgent(agentId)
      .then((response) => {
        if (attempt.current !== current) return
        setAgent(response)
        setStatus('ready')
      })
      .catch((err: unknown) => {
        if (attempt.current !== current) return
        setAgent(null)
        if (err instanceof NexusApiError && err.code === 'AGENT_NOT_FOUND') {
          setStatus('not_found')
          return
        }
        setStatus('error')
        setError(
          err instanceof NexusApiError
            ? err
            : new NexusApiError(0, { code: 'UNKNOWN_ERROR', message: 'Could not load this agent.' }),
        )
      })
  }, [agentId])

  return { agent, status, error }
}
