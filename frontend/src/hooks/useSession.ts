import { useCallback, useEffect, useRef, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { NexusApiError } from '@/types/api'
import type { SessionResponse } from '@/types/api'

export type SessionDetailStatus = 'loading' | 'ready' | 'not_found' | 'error'

export interface UseSession {
  session: SessionResponse | null
  status: SessionDetailStatus
  error: NexusApiError | null
  refetch: () => void
}

/** Fetches one session's full detail (`GET /v1/sessions/{thread_id}`),
 * including message history. Distinguishes `not_found` (SESSION_NOT_FOUND)
 * from any other failure, the same pattern hooks/useAgent.ts and
 * hooks/useRun.ts use. Exposes `refetch` for the Session Detail page's
 * "Refresh" action (Phase 6.4 spec: a simple refresh, not polling). */
export function useSession(threadId: string | undefined): UseSession {
  const [session, setSession] = useState<SessionResponse | null>(null)
  const [status, setStatus] = useState<SessionDetailStatus>('loading')
  const [error, setError] = useState<NexusApiError | null>(null)
  const attempt = useRef(0)

  const fetchSession = useCallback(() => {
    if (!threadId) {
      setSession(null)
      setStatus('not_found')
      return
    }
    const current = (attempt.current += 1)
    setStatus('loading')
    setError(null)
    nexusApi
      .getSession(threadId)
      .then((response) => {
        if (attempt.current !== current) return
        setSession(response)
        setStatus('ready')
      })
      .catch((err: unknown) => {
        if (attempt.current !== current) return
        setSession(null)
        if (err instanceof NexusApiError && err.code === 'SESSION_NOT_FOUND') {
          setStatus('not_found')
          return
        }
        setStatus('error')
        setError(
          err instanceof NexusApiError
            ? err
            : new NexusApiError(0, { code: 'UNKNOWN_ERROR', message: 'Could not load this session.' }),
        )
      })
  }, [threadId])

  useEffect(() => {
    fetchSession()
  }, [fetchSession])

  return { session, status, error, refetch: fetchSession }
}
