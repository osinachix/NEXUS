import { useEffect, useRef, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { NexusApiError } from '@/types/api'
import type { RunResponse } from '@/types/api'

export type RunDetailStatus = 'loading' | 'ready' | 'not_found' | 'error'

export interface UseRun {
  run: RunResponse | null
  status: RunDetailStatus
  error: NexusApiError | null
}

/** Fetches one run's full detail (`GET /v1/runs/{request_id}`). Distinguishes
 * `not_found` (RUN_NOT_FOUND -- may simply have been evicted from the
 * bounded store, or never existed) from any other failure, the same
 * pattern hooks/useAgent.ts uses for AGENT_NOT_FOUND. */
export function useRun(requestId: string | undefined): UseRun {
  const [run, setRun] = useState<RunResponse | null>(null)
  const [status, setStatus] = useState<RunDetailStatus>('loading')
  const [error, setError] = useState<NexusApiError | null>(null)
  const attempt = useRef(0)

  useEffect(() => {
    if (!requestId) {
      setRun(null)
      setStatus('not_found')
      return
    }
    const current = (attempt.current += 1)
    setStatus('loading')
    setError(null)
    nexusApi
      .getRun(requestId)
      .then((response) => {
        if (attempt.current !== current) return
        setRun(response)
        setStatus('ready')
      })
      .catch((err: unknown) => {
        if (attempt.current !== current) return
        setRun(null)
        if (err instanceof NexusApiError && err.code === 'RUN_NOT_FOUND') {
          setStatus('not_found')
          return
        }
        setStatus('error')
        setError(
          err instanceof NexusApiError
            ? err
            : new NexusApiError(0, { code: 'UNKNOWN_ERROR', message: 'Could not load this run.' }),
        )
      })
  }, [requestId])

  return { run, status, error }
}
