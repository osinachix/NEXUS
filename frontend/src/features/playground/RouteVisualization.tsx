import { agentDisplayName, type Agent, type ExecutionMode } from '@/types/agent'
import type { TraceState } from '@/types/trace'

interface Props {
  mode: ExecutionMode
  trace: TraceState
  agents: Agent[]
}

function labelFor(agentId: string, agents: Agent[]): string {
  return agents.find((a) => a.id === agentId)?.name ?? agentDisplayName(agentId)
}

/**
 * Makes the actual execution path visually explicit, and never claims
 * the classifier ran when it didn't (see the Phase 6.1 spec's Route
 * Visualization requirements) -- this reads `mode`, which reflects what
 * the caller actually requested, never inferring it after the fact.
 * `agents` (Phase 6.2) is the fetched registry, used to show the real
 * display name; falls back to a simple capitalization if the registry
 * hasn't loaded yet.
 */
export function RouteVisualization({ mode, trace, agents }: Props) {
  if (mode.kind === 'direct') {
    return (
      <div className="flex flex-col gap-1.5 rounded-md border border-border-subtle bg-surface-2 p-3">
        <span className="text-xs font-medium tracking-wide text-text-muted uppercase">Direct Agent</span>
        <span className="font-mono text-sm text-text-primary">{labelFor(mode.agent, agents)} Agent</span>
      </div>
    )
  }

  const classifierStep = trace.steps.find((s) => s.kind === 'classifier')
  const routeLabel = trace.route

  return (
    <div className="flex flex-col gap-1.5 rounded-md border border-border-subtle bg-surface-2 p-3">
      <span className="text-xs font-medium tracking-wide text-text-muted uppercase">Auto Route</span>
      <div className="flex items-center gap-2 font-mono text-sm">
        <span className={classifierStep ? 'text-text-primary' : 'text-text-muted'}>Classifier</span>
        <span className="text-text-muted">&rarr;</span>
        <span
          className={
            routeLabel
              ? 'rounded border border-accent-dim bg-accent-subtle px-2 py-0.5 text-accent'
              : 'text-text-muted'
          }
        >
          {routeLabel ?? 'pending'}
        </span>
        <span className="text-text-muted">&rarr;</span>
        <span className={routeLabel ? 'text-text-primary' : 'text-text-muted'}>
          {routeLabel ? `${labelFor(routeLabel, agents)} Agent` : 'Agent'}
        </span>
      </div>
    </div>
  )
}
