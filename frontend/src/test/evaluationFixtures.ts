import type { EvaluationResult, EvaluationSummary } from '@/types/api'

export const EVALUATION_A: EvaluationSummary = {
  evaluation_id: 'eval-aaa111', dataset_name: 'baseline', dataset_version: '1.0', created_at: '2026-09-30T12:00:00Z',
  total_cases: 1, passed_cases: 1, failed_cases: 0, routing_accuracy: 1, execution_success_rate: 1, tool_success_rate: null,
  metrics: { count: 1, latency_min_ms: 350, latency_max_ms: 350, latency_mean_ms: 350, latency_p50_ms: 350, latency_p95_ms: 350, latency_p99_ms: 350, total_input_tokens: null, total_output_tokens: null, total_tokens: null, total_cost_usd: null },
}

export const EVALUATION_B: EvaluationSummary = {
  ...EVALUATION_A, evaluation_id: 'eval-bbb222', created_at: '2026-09-30T12:01:00Z', passed_cases: 0, failed_cases: 1,
}

export const EVALUATION_RESULT: EvaluationResult = {
  case_id: 'case-1', case_name: 'Basic arithmetic', request_id: 'req-eval-1', thread_id: 'eval-aaa111-case-1', passed: true,
  dimensions: [{ dimension: 'execution', passed: true, detail: '' }, { dimension: 'routing', passed: true, detail: 'expected route' }],
  run: {
    request_id: 'req-eval-1', thread_id: 'eval-aaa111-case-1', status: 'completed', success: true, route: 'math', agent: 'math', message_type: 'math', reply: 'The answer is 42.',
    started_at: '2026-09-30T12:00:00Z', completed_at: '2026-09-30T12:00:00Z', duration_ms: 350, events: [], tool_events: [], usage: null, cost_usd: null, error_type: null,
  },
}
