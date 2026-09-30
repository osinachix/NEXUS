import { StatusIndicator } from '@/components/StatusIndicator'
import { ToolIcon } from '@/components/icons'
import { formatDurationMs } from '@/lib/formatters'
import type { TraceStep } from '@/types/trace'

const STATUS_DOT_CLASS: Record<TraceStep['status'], string> = {
  pending: 'border-border-strong bg-surface-2',
  running: 'border-accent bg-accent animate-pulse-ring',
  completed: 'border-status-success bg-status-success',
  failed: 'border-status-danger bg-status-danger',
  denied: 'border-status-warning bg-status-warning',
}

export function TraceStepItem({ step, isLast }: { step: TraceStep; isLast: boolean }) {
  return (
    <li className="relative flex gap-3 pb-4 pl-1 last:pb-0">
      {!isLast && <span className="absolute top-3 left-[7px] h-full w-px bg-border-default" aria-hidden="true" />}
      <span
        className={`relative z-10 mt-1 h-3.5 w-3.5 shrink-0 rounded-full border-2 ${STATUS_DOT_CLASS[step.status]}`}
        aria-hidden="true"
      />
      <div className="flex min-w-0 flex-1 flex-col gap-0.5">
        <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
          <span className="flex items-center gap-1.5 text-sm font-medium text-text-primary">
            {step.kind === 'tool' && <ToolIcon className="text-text-muted" />}
            {step.label}
          </span>
          <StatusIndicator status={step.status} />
        </div>
        {(step.detail || step.durationMs !== undefined) && (
          <div className="flex flex-wrap items-center gap-x-3 text-xs text-text-muted">
            {step.detail && <span className="font-mono">{step.detail}</span>}
            {step.durationMs !== undefined && <span>{formatDurationMs(step.durationMs)}</span>}
          </div>
        )}
      </div>
    </li>
  )
}
