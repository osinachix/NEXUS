import { Link, useParams } from 'react-router-dom'
import { useAgent } from '@/hooks/useAgent'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { AgentStatusBadge } from './AgentStatusBadge'

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <span className="text-[11px] font-medium tracking-wide text-text-muted uppercase">{title}</span>
      {children}
    </div>
  )
}

/**
 * The agent detail view (Phase 6.2 spec section 12). Deliberately
 * compact: capabilities, tools, and supported execution modes -- never a
 * system prompt or any internal model configuration (see agents.py /
 * SECURITY.md). "Test Agent" here is the same navigation-to-Playground
 * action as the Agents page card -- no second execution surface.
 */
export function AgentDetailPage() {
  const { agentId } = useParams<{ agentId: string }>()
  const { agent, status, error } = useAgent(agentId)

  if (status === 'loading') {
    return (
      <div className="flex h-full flex-col gap-4 p-6" aria-busy="true">
        <div className="h-6 w-40 animate-pulse rounded bg-surface-3" />
        <div className="h-4 w-24 animate-pulse rounded bg-surface-3" />
        <div className="h-16 w-full max-w-lg animate-pulse rounded bg-surface-3" />
      </div>
    )
  }

  if (status === 'not_found') {
    return (
      <div className="flex h-full flex-col items-start gap-3 p-6">
        <p className="text-sm text-text-secondary">
          No agent named <span className="font-mono text-text-primary">{agentId}</span> is registered.
        </p>
        <Link to="/agents" className="text-sm text-accent hover:underline">
          Back to Agents
        </Link>
      </div>
    )
  }

  if (status === 'error' && error) {
    return (
      <div className="max-w-md p-6">
        <ErrorPanel error={error} />
      </div>
    )
  }

  if (!agent) return null

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto p-6">
      <div className="flex flex-col gap-2">
        <Link to="/agents" className="w-fit text-xs text-text-muted hover:text-text-secondary">
          &larr; Agents
        </Link>
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-text-primary">{agent.name} Agent</h1>
          <AgentStatusBadge status={agent.status} />
        </div>
        <p className="max-w-lg text-sm leading-relaxed text-text-secondary">{agent.description}</p>
      </div>

      <div className="flex max-w-lg flex-col gap-5 rounded-md border border-border-subtle bg-surface-1 p-4">
        <Section title="Capabilities">
          {agent.capabilities.length > 0 ? (
            <ul className="flex flex-col gap-0.5 text-sm text-text-primary">
              {agent.capabilities.map((c) => (
                <li key={c} className="font-mono">{c}</li>
              ))}
            </ul>
          ) : (
            <span className="text-sm text-text-muted">None reported</span>
          )}
        </Section>

        <Section title="Tools">
          {agent.tools.length > 0 ? (
            <ul className="flex flex-col gap-0.5 text-sm text-text-primary">
              {agent.tools.map((t) => (
              <li key={t}>
                <Link to="/tools" className="font-mono text-accent hover:underline">{t}</Link>
              </li>
              ))}
            </ul>
          ) : (
            <span className="text-sm text-text-muted">None</span>
          )}
        </Section>

        <Section title="Execution">
          <span className="text-sm text-text-primary">
            {agent.execution_mode.includes('direct') ? 'Direct agent execution supported' : 'Auto Route only'}
          </span>
        </Section>
      </div>

      {agent.status === 'active' ? (
        <Link
          to={`/playground?agent=${encodeURIComponent(agent.id)}`}
          className="flex w-fit items-center justify-center rounded-md bg-accent px-4 py-2 text-sm font-medium text-surface-0 transition-opacity hover:opacity-90"
        >
          Test Agent
        </Link>
      ) : (
        <span className="flex w-fit cursor-not-allowed items-center justify-center rounded-md border border-border-default bg-surface-2 px-4 py-2 text-sm font-medium text-text-muted">
          Test Agent (unavailable)
        </span>
      )}
    </div>
  )
}
