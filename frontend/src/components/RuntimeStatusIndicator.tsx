import { useRuntimeStatus, type RuntimeStatus } from '@/hooks/useRuntimeStatus'
import { CrossIcon, DotIcon, SpinnerIcon } from './icons'

const CONFIG: Record<RuntimeStatus, { label: string; textClass: string; dotClass: string }> = {
  checking: { label: 'Checking', textClass: 'text-text-muted', dotClass: 'text-text-muted' },
  online: { label: 'Runtime Online', textClass: 'text-status-success', dotClass: 'text-status-success' },
  offline: { label: 'Runtime Offline', textClass: 'text-status-danger', dotClass: 'text-status-danger' },
  error: { label: 'Runtime Error', textClass: 'text-status-warning', dotClass: 'text-status-warning' },
}

/** Reflects the real backend GET /health result -- never a hardcoded
 * "Online" (see the Phase 6.1 spec's Top Bar requirements). */
export function RuntimeStatusIndicator() {
  const status = useRuntimeStatus()
  const config = CONFIG[status]

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex items-center gap-2 rounded-full border border-border-default bg-surface-2 px-3 py-1.5"
    >
      {status === 'checking' ? (
        <SpinnerIcon className={config.dotClass} />
      ) : status === 'offline' || status === 'error' ? (
        <CrossIcon className={config.dotClass} />
      ) : (
        <DotIcon className={config.dotClass} />
      )}
      <span className={`text-xs font-medium ${config.textClass}`}>{config.label}</span>
    </div>
  )
}
