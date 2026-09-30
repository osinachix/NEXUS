/**
 * Session domain helpers (Phase 6.4). A session is persistent
 * thread/workflow STATE (LangGraph checkpoint state), distinct from a
 * run (one execution) -- see CLAUDE.md section 16, "State vs Memory",
 * and the Console's own Runs vs. Sessions split. This module does not
 * implement or imply long-term memory: it only presents what the
 * checkpointer already durably persists for the active workflow.
 */

/** Display label for a message's raw backend `role` ('human'/'ai', the
 * LangChain message type as-is -- see types/api.ts's SessionMessage).
 * Presentational only; the backend contract itself is unchanged. */
export function sessionRoleLabel(role: string): string {
  if (role === 'human') return 'User'
  if (role === 'ai') return 'Agent'
  return role
}
