import { useCallback, useEffect, useRef, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { NexusApiError } from '@/types/api'
import type { Agent } from '@/types/agent'

export type AgentRegistryStatus = 'loading' | 'ready' | 'error'

export interface UseAgentRegistry {
  agents: Agent[]
  status: AgentRegistryStatus
  error: NexusApiError | null
  refetch: () => void
}

/**
 * Fetches the NEXUS agent registry (`GET /v1/agents`) once per mount --
 * the shared data source for the Agents page and the Playground's mode
 * selector/agent grid (Phase 6.2). Never renders fake agent data while
 * loading: `agents` is empty until `status` is 'ready'.
 */
export function useAgentRegistry(): UseAgentRegistry {
  const [agents, setAgents] = useState<Agent[]>([])
  const [status, setStatus] = useState<AgentRegistryStatus>('loading')
  const [error, setError] = useState<NexusApiError | null>(null)
  const attempt = useRef(0)

  const fetchAgents = useCallback(() => {
    const current = (attempt.current += 1)
    setStatus('loading')
    setError(null)
    nexusApi
      .getAgents()
      .then((response) => {
        if (attempt.current !== current) return
        setAgents(response)
        setStatus('ready')
      })
      .catch((err: unknown) => {
        if (attempt.current !== current) return
        setAgents([])
        setStatus('error')
        setError(
          err instanceof NexusApiError
            ? err
            : new NexusApiError(0, { code: 'UNKNOWN_ERROR', message: 'Could not load the agent registry.' }),
        )
      })
  }, [])

  useEffect(() => {
    fetchAgents()
  }, [fetchAgents])

  return { agents, status, error, refetch: fetchAgents }
}
