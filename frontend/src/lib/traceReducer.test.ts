import { describe, expect, it } from 'vitest'
import type { NexusEvent } from '@/types/events'
import { initialTraceState, reduceTraceEvents } from './traceReducer'

function ev(event_type: string, extra: Partial<NexusEvent> = {}): NexusEvent {
  return { event_type, request_id: 'req-1', thread_id: 'thread-1', timestamp: '2026-01-01T00:00:00Z', ...extra }
}

describe('reduceTraceEvents: auto-route happy path', () => {
  const events = [
    ev('workflow_started'),
    ev('classifier_started', { node: 'classifier' }),
    ev('classifier_completed', { node: 'classifier', success: true, duration_ms: 120 }),
    ev('route_selected', { route: 'logical', message_type: 'logical' }),
    ev('agent_started', { node: 'logical' }),
    ev('tool_started', { tool: 'fetch' }),
    ev('tool_completed', { tool: 'fetch', success: true, duration_ms: 300 }),
    ev('agent_completed', { node: 'logical', success: true, duration_ms: 900 }),
    ev('workflow_completed', { success: true, duration_ms: 950 }),
    ev('run_completed', { status: 'completed', success: true, route: 'logical', reply: 'the answer', duration_ms: 950 }),
  ]

  it('produces one step per lifecycle stage, in order', () => {
    const state = reduceTraceEvents(events)
    expect(state.steps.map((s) => s.kind)).toEqual(['workflow', 'classifier', 'route', 'agent', 'tool'])
  })

  it('marks every step completed', () => {
    const state = reduceTraceEvents(events)
    expect(state.steps.every((s) => s.status === 'completed')).toBe(true)
  })

  it('records the selected route', () => {
    expect(reduceTraceEvents(events).route).toBe('logical')
  })

  it('reaches a completed outcome', () => {
    expect(reduceTraceEvents(events).outcome).toBe('completed')
  })

  it('captures the run_completed payload', () => {
    const state = reduceTraceEvents(events)
    expect(state.runCompleted).toEqual({
      request_id: 'req-1',
      thread_id: 'thread-1',
      status: 'completed',
      success: true,
      route: 'logical',
      reply: 'the answer',
      duration_ms: 950,
      timestamp: '2026-01-01T00:00:00Z',
    })
  })

  it('carries duration onto the completed steps', () => {
    const state = reduceTraceEvents(events)
    const agentStep = state.steps.find((s) => s.kind === 'agent')
    expect(agentStep?.durationMs).toBe(900)
  })
})

describe('reduceTraceEvents: incremental building (events appear one at a time)', () => {
  it('shows a running step immediately after its _started event, before completion', () => {
    const state = reduceTraceEvents([ev('workflow_started'), ev('agent_started', { node: 'math' })])
    const agentStep = state.steps.find((s) => s.kind === 'agent')
    expect(agentStep?.status).toBe('running')
    expect(agentStep?.label).toBe('Math Agent')
  })

  it('outcome becomes running as soon as workflow_started arrives', () => {
    expect(initialTraceState().outcome).toBe('idle')
    const state = reduceTraceEvents([ev('workflow_started')])
    expect(state.outcome).toBe('running')
  })
})

describe('reduceTraceEvents: direct-agent mode', () => {
  it('never produces classifier or route steps', () => {
    const state = reduceTraceEvents([
      ev('workflow_started'),
      ev('agent_started', { node: 'coding' }),
      ev('agent_completed', { node: 'coding', success: true, duration_ms: 200 }),
      ev('workflow_completed', { success: true }),
    ])
    expect(state.steps.some((s) => s.kind === 'classifier' || s.kind === 'route')).toBe(false)
    expect(state.route).toBeNull()
  })
})

describe('reduceTraceEvents: failures', () => {
  it('marks the agent step failed on agent_completed with success=false', () => {
    const state = reduceTraceEvents([
      ev('workflow_started'),
      ev('agent_started', { node: 'math' }),
      ev('agent_completed', { node: 'math', success: false, error_type: 'RuntimeError' }),
    ])
    expect(state.steps.find((s) => s.kind === 'agent')?.status).toBe('failed')
  })

  it('workflow_failed sets outcome=failed and a safe, human failureReason', () => {
    const state = reduceTraceEvents([ev('workflow_started'), ev('workflow_failed', { error_type: 'RuntimeError' })])
    expect(state.outcome).toBe('failed')
    expect(state.failureReason).toContain('RuntimeError')
    expect(state.failureReason).not.toContain('Traceback')
  })

  it('tool_denied marks the tool step denied with the reason as detail', () => {
    const state = reduceTraceEvents([
      ev('workflow_started'),
      ev('tool_started', { tool: 'fetch' }),
      ev('tool_denied', { tool: 'fetch', reason: 'PRIVATE_ADDRESS' }),
    ])
    const toolStep = state.steps.find((s) => s.kind === 'tool')
    expect(toolStep?.status).toBe('denied')
    expect(toolStep?.detail).toBe('PRIVATE_ADDRESS')
  })

  it('tool_denied with no prior tool_started still produces a denied step (authz gate runs first)', () => {
    const state = reduceTraceEvents([ev('workflow_started'), ev('tool_denied', { tool: 'fetch', reason: 'TOOL_NOT_AUTHORIZED' })])
    expect(state.steps).toHaveLength(2)
    expect(state.steps[1].status).toBe('denied')
  })

  it('tool_failed marks the tool step failed', () => {
    const state = reduceTraceEvents([
      ev('workflow_started'),
      ev('tool_started', { tool: 'fetch' }),
      ev('tool_failed', { tool: 'fetch', error_type: 'ConnectError' }),
    ])
    expect(state.steps.find((s) => s.kind === 'tool')?.status).toBe('failed')
  })
})

describe('reduceTraceEvents: robustness', () => {
  it('ignores an unknown event type rather than crashing', () => {
    const state = reduceTraceEvents([ev('workflow_started'), ev('some_future_event' as never)])
    expect(state.steps).toHaveLength(1)
  })

  it('ignores a _completed event with no matching running step', () => {
    const state = reduceTraceEvents([ev('agent_completed', { node: 'math', success: true })])
    expect(state.steps).toHaveLength(0)
  })

  it('distinguishes concurrent-looking tool steps by tool name', () => {
    const state = reduceTraceEvents([
      ev('workflow_started'),
      ev('tool_started', { tool: 'fetch' }),
      ev('tool_started', { tool: 'other_tool' }),
      ev('tool_completed', { tool: 'other_tool', success: true, duration_ms: 10 }),
    ])
    const fetchStep = state.steps.find((s) => s.label === 'fetch')
    const otherStep = state.steps.find((s) => s.label === 'other_tool')
    expect(fetchStep?.status).toBe('running')
    expect(otherStep?.status).toBe('completed')
  })
})
