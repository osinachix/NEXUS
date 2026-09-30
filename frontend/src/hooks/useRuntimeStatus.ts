import { useEffect, useRef, useState } from 'react'
import { nexusApi } from '@/lib/apiClient'

export type RuntimeStatus = 'checking' | 'online' | 'offline' | 'error'

const POLL_INTERVAL_MS = 15_000

/** Polls the real backend /health endpoint (never hardcodes "Online" --
 * see the Phase 6.1 spec's Top Bar requirements). `offline` means the
 * request could not be made at all (backend not running / network
 * error); `error` means the backend responded but reported it is not
 * healthy. */
export function useRuntimeStatus(): RuntimeStatus {
  const [status, setStatus] = useState<RuntimeStatus>('checking')
  const mounted = useRef(true)

  useEffect(() => {
    mounted.current = true

    const check = async () => {
      try {
        const health = await nexusApi.health()
        if (!mounted.current) return
        setStatus(health.status === 'ok' ? 'online' : 'error')
      } catch {
        if (!mounted.current) return
        setStatus('offline')
      }
    }

    void check()
    const interval = setInterval(() => void check(), POLL_INTERVAL_MS)

    return () => {
      mounted.current = false
      clearInterval(interval)
    }
  }, [])

  return status
}
