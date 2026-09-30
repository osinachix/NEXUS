/**
 * Typed HTTP client for the NEXUS API (api.py). The only place in the
 * frontend that calls `fetch` for non-streaming requests -- components
 * must go through this, not call `fetch` directly (see CLAUDE.md
 * section 20). The SSE streaming endpoint has its own dedicated client;
 * see lib/sseClient.ts.
 */

import { NexusApiError } from '@/types/api'
import type {
  HealthResponse,
  EvaluationComparison,
  EvaluationListResponse,
  EvaluationResult,
  EvaluationSummary,
  MessageRequest,
  MessageResponse,
  ReadinessResponse,
  RunListParams,
  RunListResponse,
  RunSummaryListResponse,
  RunComparisonResponse,
  RunResponse,
  SessionCreateResponse,
  SessionListParams,
  SessionListResponse,
  SessionResponse,
} from '@/types/api'
import type { Agent } from '@/types/agent'
import type { ToolActivityResponse, ToolDefinition } from '@/types/tool'
import { nexusConfig, type NexusConfig } from './config'

export class NexusApiClient {
  private readonly baseUrl: string
  private readonly token: string | null

  constructor(config: NexusConfig = nexusConfig) {
    this.baseUrl = config.apiBaseUrl
    this.token = config.apiToken
  }

  private authHeaders(): HeadersInit {
    return this.token ? { Authorization: `Bearer ${this.token}` } : {}
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    let response: Response
    try {
      response = await fetch(`${this.baseUrl}${path}`, {
        ...init,
        headers: {
          ...this.authHeaders(),
          ...(init.body ? { 'Content-Type': 'application/json' } : {}),
          ...init.headers,
        },
      })
    } catch {
      // A connection-level failure (backend not running, DNS, CORS, ...).
      // The underlying error may contain low-level connection details
      // that aren't a documented safe error shape, so it's deliberately
      // not surfaced -- just a clear, actionable message.
      throw new NexusApiError(0, {
        code: 'NETWORK_ERROR',
        message: 'Could not reach the NEXUS API. Is the backend running?',
      })
    }

    if (!response.ok) {
      const retryAfterHeader = response.headers.get('Retry-After')
      const retryAfterSeconds = retryAfterHeader ? Number.parseInt(retryAfterHeader, 10) : null
      let detail = { code: 'UNKNOWN_ERROR', message: `Request failed with status ${response.status}.` }
      try {
        const body = (await response.json()) as { error?: { code: string; message: string } }
        if (body.error) {
          detail = body.error
        }
      } catch {
        // Response body wasn't the expected safe JSON error shape (e.g. a
        // proxy/gateway error) -- fall back to the generic message above
        // rather than surfacing raw response text.
      }
      throw new NexusApiError(response.status, detail, retryAfterSeconds)
    }

    if (response.status === 204) {
      return undefined as T
    }
    return (await response.json()) as T
  }

  health(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health')
  }

  ready(): Promise<ReadinessResponse> {
    return this.request<ReadinessResponse>('/ready')
  }

  createSession(): Promise<SessionCreateResponse> {
    return this.request<SessionCreateResponse>('/v1/sessions', { method: 'POST' })
  }

  getSession(threadId: string): Promise<SessionResponse> {
    return this.request<SessionResponse>(`/v1/sessions/${encodeURIComponent(threadId)}`)
  }

  /** Recent sessions (Phase 6.4) -- discovered directly from checkpoint
   * state, most recently updated first. See types/api.ts's
   * SessionListResponse doc comment. */
  getSessions(params: SessionListParams = {}): Promise<SessionListResponse> {
    const query = new URLSearchParams()
    if (params.limit !== undefined) query.set('limit', String(params.limit))
    const qs = query.toString()
    return this.request<SessionListResponse>(`/v1/sessions${qs ? `?${qs}` : ''}`)
  }

  sendMessage(threadId: string, body: MessageRequest): Promise<MessageResponse> {
    return this.request<MessageResponse>(`/v1/sessions/${encodeURIComponent(threadId)}/messages`, {
      method: 'POST',
      body: JSON.stringify(body),
    })
  }

  getRun(requestId: string): Promise<RunResponse> {
    return this.request<RunResponse>(`/v1/runs/${encodeURIComponent(requestId)}`)
  }

  compareRuns(requestIdA: string, requestIdB: string): Promise<RunComparisonResponse> {
    return this.request<RunComparisonResponse>(
      `/v1/runs/compare/${encodeURIComponent(requestIdA)}/${encodeURIComponent(requestIdB)}`,
    )
  }

  replayRun(requestId: string): Promise<RunResponse> {
    return this.request<RunResponse>(`/v1/runs/${encodeURIComponent(requestId)}/replay`, { method: 'POST' })
  }

  getEvaluations(limit = 50): Promise<EvaluationListResponse> {
    const query = new URLSearchParams({ limit: String(limit) })
    return this.request<EvaluationListResponse>(`/v1/evaluations?${query}`)
  }

  runEvaluation(): Promise<EvaluationSummary> {
    return this.request<EvaluationSummary>('/v1/evaluations', { method: 'POST' })
  }

  getEvaluation(evaluationId: string): Promise<EvaluationSummary> {
    return this.request<EvaluationSummary>(`/v1/evaluations/${encodeURIComponent(evaluationId)}`)
  }

  getEvaluationResults(evaluationId: string): Promise<EvaluationResult[]> {
    return this.request<EvaluationResult[]>(`/v1/evaluations/${encodeURIComponent(evaluationId)}/results`)
  }

  getEvaluationMetrics(evaluationId: string): Promise<EvaluationSummary['metrics']> {
    return this.request<EvaluationSummary['metrics']>(`/v1/evaluations/${encodeURIComponent(evaluationId)}/metrics`)
  }

  compareEvaluations(evaluationA: string, evaluationB: string): Promise<EvaluationComparison> {
    return this.request<EvaluationComparison>(
      `/v1/evaluations/compare/${encodeURIComponent(evaluationA)}/${encodeURIComponent(evaluationB)}`,
    )
  }

  /** Recent executions (Phase 6.3) -- reflects only the bounded,
   * process-local RunStore, most recent first. See types/api.ts's
   * RunListResponse doc comment. */
  getRuns(params: RunListParams = {}): Promise<RunListResponse> {
    const query = new URLSearchParams()
    if (params.limit !== undefined) query.set('limit', String(params.limit))
    if (params.status) query.set('status', params.status)
    if (params.agent) query.set('agent', params.agent)
    if (params.route) query.set('route', params.route)
    if (params.thread_id) query.set('thread_id', params.thread_id)
    const qs = query.toString()
    return this.request<RunListResponse>(`/v1/runs${qs ? `?${qs}` : ''}`)
  }

  /** Lightweight, ownership-filtered runs for overview surfaces. */
  getRunSummaries(limit = 10): Promise<RunSummaryListResponse> {
    const query = new URLSearchParams({ limit: String(limit) })
    return this.request<RunSummaryListResponse>(`/v1/runs/summary?${query}`)
  }

  /** The NEXUS agent registry (Phase 6.2) -- the source of truth for
   * which agents exist and are currently usable. See types/agent.ts. */
  getAgents(): Promise<Agent[]> {
    return this.request<Agent[]>('/v1/agents')
  }

  getAgent(agentId: string): Promise<Agent> {
    return this.request<Agent>(`/v1/agents/${encodeURIComponent(agentId)}`)
  }

  getTools(): Promise<ToolDefinition[]> {
    return this.request<ToolDefinition[]>('/v1/tools')
  }

  getToolActivity(limit = 50): Promise<ToolActivityResponse> {
    const query = new URLSearchParams({ limit: String(limit) })
    return this.request<ToolActivityResponse>(`/v1/tools/activity?${query}`)
  }

  /** Absolute URL for the SSE streaming endpoint -- used by sseClient.ts,
   * which needs to construct its own fetch/EventSource-style request
   * rather than going through `request()` above (streaming responses
   * aren't a single JSON body). */
  streamUrl(threadId: string): string {
    return `${this.baseUrl}/v1/sessions/${encodeURIComponent(threadId)}/messages/stream`
  }

  authHeadersForStream(): HeadersInit {
    return this.authHeaders()
  }
}

export const nexusApi = new NexusApiClient()
