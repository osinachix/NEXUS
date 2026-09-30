import { useCallback, useEffect, useRef, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { NexusApiError } from '@/types/api'
import type { ToolActivityResponse, ToolDefinition } from '@/types/tool'

type LoadStatus = 'loading' | 'ready' | 'error'

function safeError(error: unknown, message: string): NexusApiError {
  return error instanceof NexusApiError
    ? error
    : new NexusApiError(0, { code: 'UNKNOWN_ERROR', message })
}

export function useToolRegistry() {
  const [tools, setTools] = useState<ToolDefinition[]>([])
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [error, setError] = useState<NexusApiError | null>(null)
  const [attempt, setAttempt] = useState(0)
  const currentAttempt = useRef(0)

  const retry = useCallback(() => setAttempt((value) => value + 1), [])

  useEffect(() => {
    const current = (currentAttempt.current += 1)
    setStatus('loading')
    setError(null)
    nexusApi.getTools().then((result) => {
      if (current !== currentAttempt.current) return
      setTools(result)
      setStatus('ready')
    }).catch((cause: unknown) => {
      if (current !== currentAttempt.current) return
      setTools([])
      setError(safeError(cause, 'Could not load registered tools.'))
      setStatus('error')
    })
  }, [attempt])

  return { tools, status, error, retry }
}

export function useToolActivity(limit = 50) {
  const [activity, setActivity] = useState<ToolActivityResponse | null>(null)
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [error, setError] = useState<NexusApiError | null>(null)
  const [attempt, setAttempt] = useState(0)
  const currentAttempt = useRef(0)

  const retry = useCallback(() => setAttempt((value) => value + 1), [])

  useEffect(() => {
    const current = (currentAttempt.current += 1)
    setStatus('loading')
    setError(null)
    nexusApi.getToolActivity(limit).then((result) => {
      if (current !== currentAttempt.current) return
      setActivity(result)
      setStatus('ready')
    }).catch((cause: unknown) => {
      if (current !== currentAttempt.current) return
      setActivity(null)
      setError(safeError(cause, 'Could not load retained tool activity.'))
      setStatus('error')
    })
  }, [attempt, limit])

  return { activity, status, error, retry }
}
