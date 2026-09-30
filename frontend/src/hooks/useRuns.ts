import { useCallback, useEffect, useRef, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { NexusApiError } from '@/types/api'
import type { RunListParams, RunResponse } from '@/types/api'

export type RunsStatus = 'loading' | 'ready' | 'error'

export interface UseRuns {
  runs: RunResponse[]
  total: number
  status: RunsStatus
  error: NexusApiError | null
  refetch: () => void
}

/**
 * Fetches recent runs (`GET /v1/runs`, Phase 6.3) once per mount/params
 * change. Reflects only the bounded, process-local RunStore -- never
 * fake runs while loading, and a fresh fetch after a backend restart may
 * simply come back empty (see README "Known limitations").
 */
export function useRuns(params: RunListParams = {}): UseRuns {
  const [runs, setRuns] = useState<RunResponse[]>([])
  const [total, setTotal] = useState(0)
  const [status, setStatus] = useState<RunsStatus>('loading')
  const [error, setError] = useState<NexusApiError | null>(null)
  const attempt = useRef(0)

  // Stable-ish dependency: re-fetch when the actual filter values change,
  // not merely when the caller passes a new object literal.
  const paramsKey = JSON.stringify(params)

  const fetchRuns = useCallback(() => {
    const current = (attempt.current += 1)
    setStatus('loading')
    setError(null)
    nexusApi
      .getRuns(params)
      .then((response) => {
        if (attempt.current !== current) return
        setRuns(response.items)
        setTotal(response.total)
        setStatus('ready')
      })
      .catch((err: unknown) => {
        if (attempt.current !== current) return
        setRuns([])
        setTotal(0)
        setStatus('error')
        setError(
          err instanceof NexusApiError
            ? err
            : new NexusApiError(0, { code: 'UNKNOWN_ERROR', message: 'Could not load runs.' }),
        )
      })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paramsKey])

  useEffect(() => {
    fetchRuns()
  }, [fetchRuns])

  return { runs, total, status, error, refetch: fetchRuns }
}
