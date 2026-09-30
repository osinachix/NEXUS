import type { RunResponse } from '@/types/api'

/** A realistic Auto Route run's stored record (see run_store.build_run_record). */
export const AUTO_ROUTE_RUN: RunResponse = {
  request_id: 'req-auto-1',
  thread_id: 'thread-auto-1',
  status: 'completed',
  route: 'coding',
  agent: 'coding',
  duration_ms: 350,
  success: true,
  created_at: '2026-01-01T00:00:05.000Z',
  message_type: 'coding',
  started_at: '2026-01-01T00:00:00.000Z',
  completed_at: '2026-01-01T00:00:05.000Z',
  response: 'Here is the function you asked for.',
  events: [
    { event_type: 'workflow_started', node: null, duration_ms: null, success: null, error_type: null, route: null, timestamp: '2026-01-01T00:00:00.000Z' },
    { event_type: 'classifier_started', node: 'classifier', duration_ms: null, success: null, error_type: null, route: null, timestamp: '2026-01-01T00:00:01.000Z' },
    { event_type: 'classifier_completed', node: 'classifier', duration_ms: 50, success: true, error_type: null, route: null, timestamp: '2026-01-01T00:00:01.500Z' },
    { event_type: 'route_selected', node: null, duration_ms: null, success: null, error_type: null, route: 'coding', timestamp: '2026-01-01T00:00:02.000Z' },
    { event_type: 'agent_started', node: 'coding', duration_ms: null, success: null, error_type: null, route: null, timestamp: '2026-01-01T00:00:02.500Z' },
    { event_type: 'agent_completed', node: 'coding', duration_ms: 200, success: true, error_type: null, route: null, timestamp: '2026-01-01T00:00:04.500Z' },
    { event_type: 'workflow_completed', node: null, duration_ms: 350, success: true, error_type: null, route: null, timestamp: '2026-01-01T00:00:05.000Z' },
  ],
  tool_events: [],
  usage: { input_tokens: 100, output_tokens: 50, total_tokens: 150 },
  cost_usd: 0.002,
  error_type: null,
  replayable: true,
  replay_unavailable_reason: null,
  replay_of: null,
}

/** A Direct Agent run: no classifier_started/route_selected events at
 * all (see main.py's DIRECT_AGENT_GRAPH_BUILDERS) -- `route` stays null,
 * but `agent` (Phase 6.3) still identifies which specialist ran. Also
 * includes a tool call, to exercise tool-event rendering. */
export const DIRECT_AGENT_RUN: RunResponse = {
  request_id: 'req-direct-1',
  thread_id: 'thread-direct-1',
  status: 'completed',
  route: null,
  agent: 'logical',
  duration_ms: 420,
  success: true,
  created_at: '2026-01-01T01:00:03.000Z',
  message_type: null,
  started_at: '2026-01-01T01:00:00.000Z',
  completed_at: '2026-01-01T01:00:03.000Z',
  response: 'Based on the page, the answer is 42.',
  events: [
    { event_type: 'workflow_started', node: null, duration_ms: null, success: null, error_type: null, route: null, timestamp: '2026-01-01T01:00:00.000Z' },
    { event_type: 'agent_started', node: 'logical', duration_ms: null, success: null, error_type: null, route: null, timestamp: '2026-01-01T01:00:00.500Z' },
    { event_type: 'agent_completed', node: 'logical', duration_ms: 400, success: true, error_type: null, route: null, timestamp: '2026-01-01T01:00:02.900Z' },
    { event_type: 'workflow_completed', node: null, duration_ms: 420, success: true, error_type: null, route: null, timestamp: '2026-01-01T01:00:03.000Z' },
  ],
  tool_events: [
    { tool: 'fetch', event_type: 'tool_started', duration_ms: null, success: null, reason: null, error_type: null, timestamp: '2026-01-01T01:00:01.000Z' },
    { tool: 'fetch', event_type: 'tool_completed', duration_ms: 150, success: true, reason: null, error_type: null, timestamp: '2026-01-01T01:00:01.150Z' },
  ],
  usage: null,
  cost_usd: null,
  error_type: null,
  replayable: true,
  replay_unavailable_reason: null,
  replay_of: null,
}

/** A failed run (workflow-level failure) -- still has a safe fallback
 * reply, per Phase 0 behavior. */
export const FAILED_RUN: RunResponse = {
  request_id: 'req-failed-1',
  thread_id: 'thread-failed-1',
  status: 'failed',
  route: null,
  agent: null,
  duration_ms: 12,
  success: false,
  created_at: '2026-01-01T02:00:00.100Z',
  message_type: null,
  started_at: '2026-01-01T02:00:00.000Z',
  completed_at: '2026-01-01T02:00:00.100Z',
  response: "Sorry, I couldn't get a response due to a temporary issue with the AI provider or an external tool. Please try again in a moment.",
  events: [
    { event_type: 'workflow_started', node: null, duration_ms: null, success: null, error_type: null, route: null, timestamp: '2026-01-01T02:00:00.000Z' },
    { event_type: 'workflow_failed', node: null, duration_ms: 12, success: false, error_type: 'RuntimeError', route: null, timestamp: '2026-01-01T02:00:00.100Z' },
  ],
  tool_events: [],
  usage: null,
  cost_usd: null,
  error_type: 'RuntimeError',
  replayable: false,
  replay_unavailable_reason: 'input_not_retained',
  replay_of: null,
}
