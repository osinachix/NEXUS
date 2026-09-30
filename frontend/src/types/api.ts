/**
 * Types mirroring NEXUS API's Pydantic response/request models (api.py).
 * Kept hand-written and deliberately minimal rather than generated: the
 * backend contract is small and stable, and a generation step would be
 * unnecessary complexity for four endpoints (see CLAUDE.md section 20).
 * Field names and optionality match api.py exactly as of Phase 6.1.
 */

import type { AgentId } from './agent'

export interface HealthResponse {
  status: string
  service: string
}

export interface ReadinessResponse {
  status: string
  service: string
  checkpointer: string
}

export interface SessionCreateResponse {
  thread_id: string
}

/** One persisted turn's message (Phase 6.4). `role` is the raw LangChain
 * message type ('human'/'ai') as returned by the backend -- not
 * translated server-side, see types/session.ts's display mapping. */
export interface SessionMessage {
  role: string
  content: string
}

export interface SessionResponse {
  thread_id: string
  status: string
  message_count: number
  last_message_type: string | null
  last_route: string | null
  updated_at: string | null
  /** Phase 6.4: full message history, oldest first. Only populated by
   * GET /v1/sessions/{thread_id} -- null (not an empty array) in
   * GET /v1/sessions' list results, which never fetch full content. */
  messages: SessionMessage[] | null
}

/** GET /v1/sessions (Phase 6.4). Reflects only sessions discoverable
 * within the checkpointer's bounded scan window -- see README "Known
 * limitations". */
export interface SessionListResponse {
  items: SessionResponse[]
  limit: number
}

export interface SessionListParams {
  limit?: number
}

export interface MessageRequest {
  message: string
  /** Phase 6.1: run a specific agent directly, bypassing the classifier/router. */
  agent?: AgentId | null
}

export interface MessageResponse {
  thread_id: string
  request_id: string
  response: string
  route: string | null
  status: string
  duration_ms: number
}

export interface RunEvent {
  event_type: string
  node: string | null
  duration_ms: number | null
  success: boolean | null
  error_type: string | null
  /** Only present on a route_selected event. */
  route: string | null
  timestamp: string
}

export interface ToolEvent {
  tool: string
  event_type: string
  duration_ms: number | null
  success: boolean | null
  reason: string | null
  error_type: string | null
  timestamp: string
}

export interface TokenUsage {
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
}

export interface RunResponse {
  request_id: string
  thread_id: string
  status: string
  route: string | null
  /** Phase 6.3: which specialist agent actually ran -- populated for both
   * Auto Route and Direct Agent runs, unlike `route` (auto-route only). */
  agent: string | null
  duration_ms: number
  success: boolean
  created_at: string
  message_type: string | null
  started_at: string
  completed_at: string
  /** Phase 6.3: the assistant's final reply for this run. */
  response: string
  events: RunEvent[]
  tool_events: ToolEvent[]
  usage: TokenUsage | null
  cost_usd: number | null
  error_type: string | null
  replayable: boolean
  replay_unavailable_reason: 'input_not_retained' | 'thread_has_prior_state' | null
  replay_of: string | null
}

/** GET /v1/runs (Phase 6.3). Reflects only the bounded, in-process
 * RunStore -- not a durable run history; see README "Known limitations". */
export interface RunListResponse {
  items: RunResponse[]
  total: number
  limit: number
}

/** Lightweight `GET /v1/runs/summary` response for overview surfaces. It omits
 * full traces, final responses, and thread IDs, and still reflects only the
 * bounded, process-local RunStore. */
export interface RunListItemSummary {
  request_id: string
  status: string
  route: string | null
  agent: string | null
  duration_ms: number
  success: boolean
  created_at: string
  started_at: string
  completed_at: string
  usage: TokenUsage | null
  cost_usd: number | null
}

export interface RunSummaryListResponse {
  items: RunListItemSummary[]
  total: number
  limit: number
}

export interface RunListParams {
  limit?: number
  status?: string
  agent?: string
  route?: string
  /** Phase 6.4: restrict to runs on this thread -- used by Session Detail's "View Runs" link. */
  thread_id?: string
}

export interface RunComparisonDeltas {
  duration_ms: number | null
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  cost_usd: number | null
  tool_event_count: number
}

/** Read-only comparison of two retained runs. Deltas are run B minus run A. */
export interface RunComparisonResponse {
  run_a: RunResponse
  run_b: RunResponse
  deltas: RunComparisonDeltas
}

export interface RunMetrics {
  count: number
  latency_min_ms: number | null
  latency_max_ms: number | null
  latency_mean_ms: number | null
  latency_p50_ms: number | null
  latency_p95_ms: number | null
  latency_p99_ms: number | null
  total_input_tokens: number | null
  total_output_tokens: number | null
  total_tokens: number | null
  total_cost_usd: number | null
}

export interface EvaluationSummary {
  evaluation_id: string
  dataset_name: string
  dataset_version: string
  created_at: string
  total_cases: number
  passed_cases: number
  failed_cases: number
  routing_accuracy: number | null
  execution_success_rate: number
  tool_success_rate: number | null
  metrics: RunMetrics
}

export interface EvaluationListResponse {
  items: EvaluationSummary[]
  total: number
  limit: number
}

export interface DimensionResult {
  dimension: 'routing' | 'execution' | 'tools' | 'response' | 'latency'
  passed: boolean
  detail: string
}

export interface EvaluationResult {
  case_id: string
  case_name: string
  request_id: string
  thread_id: string
  passed: boolean
  dimensions: DimensionResult[]
  run: Pick<RunResponse, 'request_id' | 'thread_id' | 'status' | 'success' | 'route' | 'agent' | 'duration_ms' | 'started_at' | 'completed_at' | 'events' | 'tool_events' | 'usage' | 'cost_usd' | 'error_type'> & {
    message_type: string | null
    reply: string
  }
}

export interface EvaluationComparison {
  evaluation_id_a: string
  evaluation_id_b: string
  summary_a: EvaluationSummary
  summary_b: EvaluationSummary
  total_cases_a: number
  total_cases_b: number
  passed_cases_delta: number
  routing_accuracy_delta: number | null
  execution_success_rate_delta: number | null
  tool_success_rate_delta: number | null
  latency_p50_delta_ms: number | null
  latency_p95_delta_ms: number | null
  latency_p99_delta_ms: number | null
  total_cost_usd_delta: number | null
}

export interface ErrorDetail {
  code: string
  message: string
}

export interface ErrorResponse {
  error: ErrorDetail
}

/** Thrown by the API client for any non-2xx response with a parsed,
 * safe error body (api.py never returns raw stack traces -- see
 * SECURITY.md section 12). */
export class NexusApiError extends Error {
  readonly status: number
  readonly code: string
  readonly retryAfterSeconds: number | null

  constructor(status: number, body: ErrorDetail, retryAfterSeconds: number | null = null) {
    super(body.message)
    this.name = 'NexusApiError'
    this.status = status
    this.code = body.code
    this.retryAfterSeconds = retryAfterSeconds
  }
}
