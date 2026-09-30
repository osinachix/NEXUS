import type { TraceStepStatus } from '@/types/trace'
import { BanIcon, CheckIcon, CrossIcon, DotIcon, SpinnerIcon } from './icons'

const STATUS_CONFIG: Record<
  TraceStepStatus,
  { label: string; textClass: string; icon: (props: { className?: string }) => React.ReactElement }
> = {
  pending: { label: 'Pending', textClass: 'text-text-muted', icon: DotIcon },
  running: { label: 'Running', textClass: 'text-accent', icon: SpinnerIcon },
  completed: { label: 'Completed', textClass: 'text-status-success', icon: CheckIcon },
  failed: { label: 'Failed', textClass: 'text-status-danger', icon: CrossIcon },
  denied: { label: 'Denied', textClass: 'text-status-warning', icon: BanIcon },
}

/** Renders a trace step's status as icon + text together, never color
 * alone (see the Phase 6.1 spec's accessibility requirements). */
export function StatusIndicator({ status, compact = false }: { status: TraceStepStatus; compact?: boolean }) {
  const config = STATUS_CONFIG[status]
  const Icon = config.icon
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${config.textClass}`}>
      <Icon />
      {!compact && <span>{config.label}</span>}
    </span>
  )
}
