import { Link } from 'react-router-dom'
import type { Agent } from '@/types/agent'
import { AgentStatusBadge } from './AgentStatusBadge'

/**
 * One agent as a platform resource, not a chatbot persona: name,
 * concise description, real status, real tool metadata, and a direct
 * "Test Agent" action into the Playground -- see the Phase 6.2 spec's
 * Agent Card Design section. All data comes from the registry (`agent`
 * prop); nothing here is hardcoded.
 */
export function AgentCard({ agent }: { agent: Agent }) {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-1 p-4 transition-colors hover:border-border-default">
      <div className="flex items-start justify-between gap-2">
        <Link to={`/agents/${agent.id}`} className="text-base font-semibold text-text-primary hover:text-accent">
          {agent.name}
        </Link>
        <AgentStatusBadge status={agent.status} />
      </div>

      <p className="min-h-10 text-sm leading-relaxed text-text-secondary">{agent.description}</p>

      <div className="flex flex-col gap-1">
        <span className="text-[11px] font-medium tracking-wide text-text-muted uppercase">Tools</span>
        <span className="font-mono text-xs text-text-secondary">
          {agent.tools.length > 0 ? agent.tools.join(', ') : 'None'}
        </span>
      </div>

      {agent.status === 'active' ? (
        <Link
          to={`/playground?agent=${encodeURIComponent(agent.id)}`}
          className="mt-1 flex items-center justify-center rounded-md bg-accent py-2 text-sm font-medium text-surface-0 transition-opacity hover:opacity-90"
        >
          Test Agent
        </Link>
      ) : (
        <span
          className="mt-1 flex cursor-not-allowed items-center justify-center rounded-md border border-border-default bg-surface-2 py-2 text-sm font-medium text-text-muted"
          title="This agent is currently unavailable"
        >
          Test Agent
        </span>
      )}
    </div>
  )
}
