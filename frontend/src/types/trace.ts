import type { NexusEvent } from './events'

/** Lifecycle states a trace step can be in. `denied` is distinct from
 * `failed`: a tool_denied event is a deterministic policy decision, not
 * an error (see SECURITY.md section 2) -- the UI should not present a
 * denial as a malfunction. */
export type TraceStepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'denied'

export type TraceStepKind = 'workflow' | 'classifier' | 'route' | 'agent' | 'tool'

/** One human-readable row in the execution trace, built by reducing the
 * raw NexusEvent stream (see lib/traceReducer.ts). Never rendered from
 * a single raw event directly -- always through this translation. */
export interface TraceStep {
  id: string
  kind: TraceStepKind
  /** Human-readable label, e.g. "Logical Agent", "secure_fetch". */
  label: string
  status: TraceStepStatus
  /** Short supplementary detail, e.g. a route name or a denial reason code. */
  detail?: string
  durationMs?: number
  /** Timestamp of the step's most recent event (started or completed). */
  timestamp: string
  /** Every raw event that contributed to this step, preserved for
   * debugging/inspection -- never the primary UI, per the Phase 6.1 spec. */
  raw: NexusEvent[]
}

export type TraceOutcome = 'idle' | 'running' | 'completed' | 'failed'

export interface RunCompletedInfo {
  request_id: string
  thread_id: string
  status: string
  success: boolean
  route: string | null
  reply: string
  duration_ms: number
  timestamp: string
}

/** The full reduced state of one execution, derived entirely from the
 * events observed so far -- see lib/traceReducer.ts. */
export interface TraceState {
  outcome: TraceOutcome
  steps: TraceStep[]
  route: string | null
  runCompleted: RunCompletedInfo | null
  /** Set when the workflow_failed event (or a connection/stream-level
   * failure) occurred; a safe, user-facing summary, never a raw exception. */
  failureReason: string | null
}

export const EMPTY_TRACE_STATE: TraceState = {
  outcome: 'idle',
  steps: [],
  route: null,
  runCompleted: null,
  failureReason: null,
}
