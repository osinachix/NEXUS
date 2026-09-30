import { useCallback, useEffect, useRef, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { NexusApiError } from '@/types/api'
import type { RunSummaryListResponse } from '@/types/api'

type LoadStatus = 'loading' | 'ready' | 'error'

export function useRunSummaries(limit = 10) {
  const [data, setData] = useState<RunSummaryListResponse>({ items: [], total: 0, limit })
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [error, setError] = useState<NexusApiError | null>(null)
  const [reload, setReload] = useState(0)
  const attempt = useRef(0)

  const refetch = useCallback(() => {
    setStatus('loading')
    setError(null)
    setReload((value) => value + 1)
  }, [])

  useEffect(() => {
    const current = ++attempt.current
    nexusApi.getRunSummaries(limit).then((result) => {
      if (attempt.current !== current) return
      setData(result)
      setStatus('ready')
    }).catch((cause: unknown) => {
      if (attempt.current !== current) return
      setData({ items: [], total: 0, limit })
      setError(cause instanceof NexusApiError
        ? cause
        : new NexusApiError(0, { code: 'UNKNOWN_ERROR', message: 'Could not load recent run summaries.' }))
      setStatus('error')
    })
  }, [limit, reload])
  return { ...data, status, error, refetch }
}
