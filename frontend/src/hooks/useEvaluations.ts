import { useCallback, useEffect, useRef, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'
import { NexusApiError } from '@/types/api'
import type { EvaluationComparison, EvaluationListResponse, EvaluationResult, EvaluationSummary, RunMetrics } from '@/types/api'

type LoadStatus = 'loading' | 'ready' | 'error'

function safeError(error: unknown, fallback: string): NexusApiError {
  return error instanceof NexusApiError
    ? error
    : new NexusApiError(0, { code: 'UNKNOWN_ERROR', message: fallback })
}

export function useEvaluations(limit = 50) {
  const [data, setData] = useState<EvaluationListResponse>({ items: [], total: 0, limit })
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [error, setError] = useState<NexusApiError | null>(null)
  const attempt = useRef(0)

  const refetch = useCallback(() => {
    const current = ++attempt.current
    setStatus('loading')
    setError(null)
    nexusApi.getEvaluations(limit).then((response) => {
      if (attempt.current !== current) return
      setData(response)
      setStatus('ready')
    }).catch((reason: unknown) => {
      if (attempt.current !== current) return
      setData({ items: [], total: 0, limit })
      setError(safeError(reason, 'Could not load evaluations.'))
      setStatus('error')
    })
  }, [limit])

  useEffect(() => { refetch() }, [refetch])
  return { ...data, status, error, refetch }
}

export function useEvaluation(evaluationId: string | undefined) {
  const [summary, setSummary] = useState<EvaluationSummary | null>(null)
  const [results, setResults] = useState<EvaluationResult[]>([])
  const [metrics, setMetrics] = useState<RunMetrics | null>(null)
  const [status, setStatus] = useState<LoadStatus>('loading')
  const [error, setError] = useState<NexusApiError | null>(null)
  const attempt = useRef(0)

  const refetch = useCallback(() => {
    if (!evaluationId) return
    const current = ++attempt.current
    setStatus('loading')
    setError(null)
    Promise.all([
      nexusApi.getEvaluation(evaluationId),
      nexusApi.getEvaluationResults(evaluationId),
      nexusApi.getEvaluationMetrics(evaluationId),
    ]).then(([nextSummary, nextResults, nextMetrics]) => {
      if (attempt.current !== current) return
      setSummary(nextSummary)
      setResults(nextResults)
      setMetrics(nextMetrics)
      setStatus('ready')
    }).catch((reason: unknown) => {
      if (attempt.current !== current) return
      setError(safeError(reason, 'Could not load this evaluation.'))
      setStatus('error')
    })
  }, [evaluationId])

  useEffect(() => { refetch() }, [refetch])
  return { summary, results, metrics, status, error, refetch }
}

export function useEvaluationComparison() {
  const [comparison, setComparison] = useState<EvaluationComparison | null>(null)
  const [status, setStatus] = useState<'idle' | 'loading' | 'ready' | 'error'>('idle')
  const [error, setError] = useState<NexusApiError | null>(null)

  const compare = useCallback((evaluationA: string, evaluationB: string) => {
    setStatus('loading')
    setError(null)
    setComparison(null)
    nexusApi.compareEvaluations(evaluationA, evaluationB).then((result) => {
      setComparison(result)
      setStatus('ready')
    }).catch((reason: unknown) => {
      setError(safeError(reason, 'Could not compare evaluations.'))
      setStatus('error')
    })
  }, [])
  return { comparison, status, error, compare }
}

export function useRunEvaluation() {
  const [running, setRunning] = useState(false)
  const [error, setError] = useState<NexusApiError | null>(null)

  const run = useCallback(async () => {
    setRunning(true)
    setError(null)
    try {
      return await nexusApi.runEvaluation()
    } catch (reason) {
      const apiError = safeError(reason, 'Could not run the baseline evaluation.')
      setError(apiError)
      throw apiError
    } finally {
      setRunning(false)
    }
  }, [])
  return { run, running, error, clearError: () => setError(null) }
}
