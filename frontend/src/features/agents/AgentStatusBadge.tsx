import type { AgentStatus } from '@/types/agent'

const CONFIG: Record<AgentStatus, { label: string; textClass: string; dotClass: string }> = {
  active: { label: 'Active', textClass: 'text-status-success', dotClass: 'bg-status-success' },
  unavailable: { label: 'Unavailable', textClass: 'text-status-danger', dotClass: 'bg-status-danger' },
}

/** Dot + text together, never color alone (same convention as
 * components/StatusIndicator.tsx). Reflects the real backend-determined
 * status from the agent registry -- see agents.py's `_logical_status`. */
export function AgentStatusBadge({ status }: { status: AgentStatus }) {
  const config = CONFIG[status]
  return (
    <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${config.textClass}`}>
      <span aria-hidden="true" className={`h-1.5 w-1.5 rounded-full ${config.dotClass}`} />
      {config.label}
    </span>
  )
}
