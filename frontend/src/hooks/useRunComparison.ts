import { useCallback, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { NexusApiError } from '@/types/api'
import type { RunComparisonResponse } from '@/types/api'

export type RunComparisonStatus = 'idle' | 'loading' | 'ready' | 'error'

export function useRunComparison() {
  const [comparison, setComparison] = useState<RunComparisonResponse | null>(null)
  const [status, setStatus] = useState<RunComparisonStatus>('idle')
  const [error, setError] = useState<NexusApiError | null>(null)

  const compare = useCallback((requestIdA: string, requestIdB: string) => {
    setStatus('loading')
    setError(null)
    setComparison(null)
    nexusApi.compareRuns(requestIdA, requestIdB).then((result) => {
      setComparison(result)
      setStatus('ready')
    }).catch((reason: unknown) => {
      setError(reason instanceof NexusApiError ? reason : new NexusApiError(0, {
        code: 'UNKNOWN_ERROR',
        message: 'Could not compare these runs.',
      }))
      setStatus('error')
    })
  }, [])

  return { comparison, status, error, compare }
}
