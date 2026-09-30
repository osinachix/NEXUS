import type { Agent } from '@/types/agent'
import type { TraceState } from '@/types/trace'

/**
 * Represents the registered agents (Phase 6.2: fetched from
 * `GET /v1/agents`, not hardcoded) consistently -- name, description,
 * execution state. Execution state is derived from the real trace, not
 * invented: a card only shows "running"/"completed"/"failed" when an
 * actual agent_started/agent_completed event named that agent.
 */
export function AgentGrid({ trace, agents }: { trace: TraceState; agents: Agent[] }) {
  const agentStep = trace.steps.filter((s) => s.kind === 'agent').at(-1)
  const activeAgentName = agentStep?.label.replace(/ Agent$/, '')

  return (
    // Always 2 columns: this grid lives inside the Playground's fixed-width
    // sidebar, not the full viewport -- a viewport-width breakpoint (e.g.
    // lg:grid-cols-4) would try to fit 4 columns into ~340px and clip the
    // "Tools" badge (found during Phase 6.1's live visual verification).
    <div className="grid grid-cols-2 gap-2">
      {agents.map((agent) => {
        const isActive = activeAgentName === agent.name
        const dotClass = !isActive
          ? agent.status === 'active'
            ? 'bg-border-strong'
            : 'bg-status-warning'
          : agentStep?.status === 'running'
            ? 'bg-accent animate-pulse-ring'
            : agentStep?.status === 'failed'
              ? 'bg-status-danger'
              : 'bg-status-success'

        return (
          <div
            key={agent.id}
            className={`flex flex-col gap-1 rounded-md border p-2.5 transition-colors ${
              isActive ? 'border-accent-dim bg-accent-subtle' : 'border-border-subtle bg-surface-2'
            }`}
          >
            <div className="flex items-center gap-1.5">
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${dotClass}`} aria-hidden="true" />
              <span className="text-sm font-medium text-text-primary">{agent.name}</span>
              {agent.tools.length > 0 && (
                <span className="ml-auto rounded border border-border-default px-1 text-[10px] text-text-muted uppercase">
                  Tools
                </span>
              )}
            </div>
            <p className="text-[11px] leading-snug text-text-muted">{agent.description}</p>
          </div>
        )
      })}
    </div>
  )
}
