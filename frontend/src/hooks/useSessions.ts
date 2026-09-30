import { useCallback, useEffect, useRef, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { NexusApiError } from '@/types/api'
import type { SessionListParams, SessionResponse } from '@/types/api'

export type SessionsStatus = 'loading' | 'ready' | 'error'

export interface UseSessions {
  sessions: SessionResponse[]
  status: SessionsStatus
  error: NexusApiError | null
  refetch: () => void
}

/**
 * Fetches recent sessions (`GET /v1/sessions`, Phase 6.4) once per
 * mount/params change. Reflects only sessions discoverable within the
 * checkpointer's bounded scan window -- never fake sessions while
 * loading, and this never fetches per-session message content (see
 * `useSession` for that).
 */
export function useSessions(params: SessionListParams = {}): UseSessions {
  const [sessions, setSessions] = useState<SessionResponse[]>([])
  const [status, setStatus] = useState<SessionsStatus>('loading')
  const [error, setError] = useState<NexusApiError | null>(null)
  const attempt = useRef(0)

  const paramsKey = JSON.stringify(params)

  const fetchSessions = useCallback(() => {
    const current = (attempt.current += 1)
    setStatus('loading')
    setError(null)
    nexusApi
      .getSessions(params)
      .then((response) => {
        if (attempt.current !== current) return
        setSessions(response.items)
        setStatus('ready')
      })
      .catch((err: unknown) => {
        if (attempt.current !== current) return
        setSessions([])
        setStatus('error')
        setError(
          err instanceof NexusApiError
            ? err
            : new NexusApiError(0, { code: 'UNKNOWN_ERROR', message: 'Could not load sessions.' }),
        )
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  return { sessions, status, error, refetch: fetchSessions }
}
