/**
 * The NEXUS structured observability event vocabulary, as streamed live
 * over SSE by POST /v1/sessions/{thread_id}/messages/stream (api.py:
 * _sse_event_source / observability.stream_events). This is the SAME
 * event vocabulary documented in ARCHITECTURE.md's "Observability model"
 * and used by GET /v1/runs/{request_id} -- not a separate frontend event
 * model. `run_completed` is the one addition api.py makes on top of the
 * raw backend lifecycle events, carrying the final reply.
 */

export const NEXUS_EVENT_TYPES = [
  'workflow_started',
  'classifier_started',
  'classifier_completed',
  'route_selected',
  'agent_started',
  'agent_completed',
  'tool_started',
  'tool_completed',
  'tool_denied',
  'tool_failed',
  'workflow_failed',
  'workflow_completed',
  'run_completed',
] as const

export type NexusEventType = (typeof NEXUS_EVENT_TYPES)[number]

export function isNexusEventType(value: string): value is NexusEventType {
  return (NEXUS_EVENT_TYPES as readonly string[]).includes(value)
}

/**
 * One event as it arrives over the wire. Fields beyond `event_type` /
 * `request_id` / `thread_id` / `timestamp` are present only when the
 * originating observability.log_event() call included them (see
 * observability.py: metadata is only ever added when actually known --
 * never a fabricated/zeroed placeholder). Kept as a single loosely-typed
 * shape (rather than a per-event-type discriminated union) because that
 * is an honest reflection of the wire format itself.
 */
export interface NexusEvent {
  event_type: string
  request_id: string
  thread_id: string
  timestamp: string
  node?: string
  duration_ms?: number
  success?: boolean
  error_type?: string
  route?: string
  message_type?: string
  tool?: string
  reason?: string
  model_name?: string
  // run_completed-only fields (see api.py's _sse_event_source):
  status?: string
  reply?: string
}
