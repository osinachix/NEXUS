/**
 * Turns a historical `RunResponse` (GET /v1/runs/{request_id}) into the
 * exact same `TraceState` the Playground builds live from SSE (Phase 6.3
 * requirement: reuse the trace visualization, don't duplicate it).
 *
 *     RunResponse.events + .tool_events  ->  NexusEvent[]  ->  reduceTraceEvents  ->  TraceState
 *
 * `reduceTraceEvents` (lib/traceReducer.ts) doesn't know or care whether
 * its input came from a live SSE stream or a stored run -- this module's
 * only job is reshaping the stored, already-safe event data into the same
 * `NexusEvent` shape SSE produces, then folding it through the same
 * reducer `ExecutionTrace`/`RouteVisualization`/`FinalResponse` already
 * render. A direct-agent run's stored events never include
 * classifier_started/route_selected (see main.py's DIRECT_AGENT_GRAPH_BUILDERS),
 * so the reduced trace correctly omits them here exactly as it does live.
 */

import type { RunResponse } from '@/types/api'
import type { NexusEvent } from '@/types/events'
import { reduceTraceEvents } from './traceReducer'
import type { TraceState } from '@/types/trace'

function toNexusEvents(run: RunResponse): NexusEvent[] {
  const base = { request_id: run.request_id, thread_id: run.thread_id }

  const lifecycle: NexusEvent[] = run.events.map((event) => ({
    ...base,
    event_type: event.event_type,
    timestamp: event.timestamp,
    node: event.node ?? undefined,
    duration_ms: event.duration_ms ?? undefined,
    success: event.success ?? undefined,
    error_type: event.error_type ?? undefined,
    route: event.route ?? undefined,
  }))

  const toolEvents: NexusEvent[] = run.tool_events.map((event) => ({
    ...base,
    event_type: event.event_type,
    timestamp: event.timestamp,
    tool: event.tool,
    duration_ms: event.duration_ms ?? undefined,
    success: event.success ?? undefined,
    error_type: event.error_type ?? undefined,
    reason: event.reason ?? undefined,
  }))

  const merged = [...lifecycle, ...toolEvents].sort((a, b) => a.timestamp.localeCompare(b.timestamp))

  // Synthesized exactly like api.py's _sse_event_source appends one after
  // the raw lifecycle events -- observability events themselves never
  // carry the reply/final status (see observability.py), so this step is
  // built from the RunResponse's own top-level fields instead.
  const runCompleted: NexusEvent = {
    ...base,
    event_type: 'run_completed',
    timestamp: run.completed_at,
    status: run.status,
    success: run.success,
    route: run.route ?? undefined,
    reply: run.response,
    duration_ms: run.duration_ms,
  }

  return [...merged, runCompleted]
}

export function runToTraceState(run: RunResponse): TraceState {
  return reduceTraceEvents(toNexusEvents(run))
}
