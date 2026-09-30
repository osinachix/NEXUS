/**
 * Agent domain types (Phase 6.2). `Agent` mirrors the backend's
 * `agents.AgentDefinition` (agents.py) exactly -- the NEXUS API's agent
 * registry (`GET /v1/agents`) is now the source of truth, not a
 * hardcoded frontend list:
 *
 *     NEXUS API -> Agent Registry -> Console
 *
 * not
 *
 *     React source code -> ["logical", "coding", "math", "counselor"]
 *
 * See hooks/useAgentRegistry.ts for how this data is fetched, and
 * lib/apiClient.ts's getAgents()/getAgent().
 */

export type AgentId = string
export type AgentStatus = 'active' | 'unavailable'
export type AgentExecutionMode = 'auto_route' | 'direct'

export interface Agent {
  id: AgentId
  name: string
  description: string
  status: AgentStatus
  execution_mode: AgentExecutionMode[]
  tools: string[]
  capabilities: string[]
  tags: string[]
  version: string
}

/** The Playground's execution mode: either automatic routing, or one
 * specific agent selected directly (by id -- validity is a backend
 * concern, enforced by the registry; see api.py's MessageRequest
 * validator). */
export type ExecutionMode = { kind: 'auto' } | { kind: 'direct'; agent: AgentId }

/**
 * A registry-independent, always-safe display label for an agent id
 * seen in a live execution trace (e.g. a `route_selected` event's
 * `route` field, or an `agent_started` event's `node` field). Used only
 * by lib/traceReducer.ts, which is a pure function with no access to
 * asynchronously-fetched registry data and must never block or fail on
 * an unrecognized id. Everywhere else (the Agents page, the Playground's
 * mode selector and agent grid) uses real `Agent` objects from the
 * registry instead of this fallback.
 */
export function agentDisplayName(id: string): string {
  if (!id) return 'Unknown'
  return `${id.charAt(0).toUpperCase()}${id.slice(1)}`
}
