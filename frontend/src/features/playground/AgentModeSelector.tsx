import type { Agent, ExecutionMode } from '@/types/agent'
import { ChevronDownIcon } from '@/components/icons'

interface Props {
  mode: ExecutionMode
  onChange: (mode: ExecutionMode) => void
  agents: Agent[]
  disabled?: boolean
}

const modeValue = (mode: ExecutionMode) => (mode.kind === 'auto' ? 'auto' : mode.agent)

/**
 * Distinguishes Auto Route (classifier decides) from Direct Agent (the
 * caller picks one specific agent, bypassing the classifier entirely --
 * see main.py's DIRECT_AGENT_GRAPH_BUILDERS). The direct-agent options
 * come from the NEXUS agent registry (Phase 6.2, `GET /v1/agents`), not
 * a hardcoded list -- see types/agent.ts. Only agents with status
 * 'active' and 'direct' in their execution_mode are offered; the
 * registry itself decides what's actually usable, not this component.
 */
export function AgentModeSelector({ mode, onChange, agents, disabled }: Props) {
  const directOptions = agents.filter(
    (a) => a.status === 'active' && a.execution_mode.includes('direct'),
  )
  const selectedAgent = mode.kind === 'direct' ? agents.find((a) => a.id === mode.agent) : undefined

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor="execution-mode" className="text-xs font-medium tracking-wide text-text-secondary uppercase">
        Execution Mode
      </label>
      <div className="relative">
        <select
          id="execution-mode"
          disabled={disabled}
          value={modeValue(mode)}
          onChange={(event) => {
            const value = event.target.value
            onChange(value === 'auto' ? { kind: 'auto' } : { kind: 'direct', agent: value })
          }}
          className="w-full appearance-none rounded-md border border-border-default bg-surface-2 py-2 pr-8 pl-3 text-sm text-text-primary transition-colors hover:border-border-strong focus:border-accent disabled:cursor-not-allowed disabled:opacity-50"
        >
          <option value="auto">Auto Route</option>
          {directOptions.map((agent) => (
            <option key={agent.id} value={agent.id}>
              Direct Agent: {agent.name}
            </option>
          ))}
        </select>
        <ChevronDownIcon className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 text-text-muted" />
      </div>
      <p className="text-xs text-text-muted">
        {mode.kind === 'auto'
          ? 'The classifier picks a specialist agent automatically.'
          : `Runs the ${selectedAgent?.name ?? mode.agent} agent directly. The classifier does not run.`}
      </p>
    </div>
  )
}
