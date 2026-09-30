import { useSearchParams } from 'react-router-dom'
import { Playground } from './Playground'

/**
 * Thin URL adapter (Phase 6.2): reads the optional `?agent=` query param
 * set by the Test Agent flow (AgentCard / AgentDetailPage) and passes it
 * into the existing Playground as `initialAgentId`. This is the only
 * place the Playground route touches the URL -- Playground.tsx itself
 * stays a plain, URL-agnostic execution surface, and no second execution
 * mechanism is introduced.
 */
export function PlaygroundPage() {
  const [searchParams] = useSearchParams()
  const agent = searchParams.get('agent') ?? undefined
  return <Playground initialAgentId={agent} />
}
