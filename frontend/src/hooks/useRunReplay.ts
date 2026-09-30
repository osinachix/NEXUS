import { useCallback, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { NexusApiError } from '@/types/api'
import type { RunResponse } from '@/types/api'

export type RunReplayStatus = 'idle' | 'loading' | 'ready' | 'error'

export function useRunReplay() {
  const [replayedRun, setReplayedRun] = useState<RunResponse | null>(null)
  const [status, setStatus] = useState<RunReplayStatus>('idle')
  const [error, setError] = useState<NexusApiError | null>(null)

  const replay = useCallback(async (requestId: string) => {
    setStatus('loading')
    setError(null)
    setReplayedRun(null)
    try {
      const result = await nexusApi.replayRun(requestId)
      setReplayedRun(result)
      setStatus('ready')
      return result
    } catch (reason) {
      const safeError = reason instanceof NexusApiError
        ? reason
        : new NexusApiError(0, { code: 'UNKNOWN_ERROR', message: 'Could not re-run this execution.' })
      setError(safeError)
      setStatus('error')
      return null
    }
  }, [])

  const reset = useCallback(() => {
    setReplayedRun(null)
    setError(null)
    setStatus('idle')
  }, [])

  return { replayedRun, status, error, replay, reset }
}
