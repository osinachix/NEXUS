import { useAgentRegistry } from '@/hooks/useAgentRegistry'
import { ErrorPanel } from '@/features/playground/ErrorPanel'
import { AgentCard } from './AgentCard'
import { AgentCardSkeleton } from './AgentCardSkeleton'

/**
 * The NEXUS Agent Registry, rendered (Phase 6.2). Real API data only --
 * see hooks/useAgentRegistry.ts. This is the first Console page besides
 * the Playground; deliberately scoped to listing + linking into agent
 * detail/Test Agent, nothing else (no editing, no creation -- see
 * CLAUDE.md's "Do not overbuild" guidance and the Phase 6.2 spec's
 * explicit phase boundary).
 */
export function AgentsPage() {
  const { agents, status, error, refetch } = useAgentRegistry()

  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto p-6">
      <div className="flex flex-col gap-1">
        <h1 className="text-lg font-semibold text-text-primary">Agents</h1>
        <p className="text-sm text-text-muted">
          Reference agents registered with this NEXUS runtime. Select an agent to view details or
          test it directly in the Playground.
        </p>
      </div>

      {status === 'error' && error && (
        <div className="max-w-md">
          <ErrorPanel error={error} onRetry={refetch} />
        </div>
      )}

      {status === 'loading' && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            // eslint-disable-next-line react/no-array-index-key
            <AgentCardSkeleton key={i} />
          ))}
        </div>
      )}

      {status === 'ready' && agents.length === 0 && (
        <div className="flex flex-1 items-center justify-center rounded-md border border-dashed border-border-subtle text-sm text-text-muted">
          No agents are registered with this NEXUS runtime.
        </div>
      )}

      {status === 'ready' && agents.length > 0 && (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {agents.map((agent) => (
            <AgentCard key={agent.id} agent={agent} />
          ))}
        </div>
      )}
    </div>
  )
}
