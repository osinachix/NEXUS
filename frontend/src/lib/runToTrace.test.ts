import { describe, expect, it } from 'vitest'
import { AUTO_ROUTE_RUN, DIRECT_AGENT_RUN, FAILED_RUN } from '@/test/runFixtures'
import { runToTraceState } from './runToTrace'

describe('runToTraceState: reuses the same reducer as the live Playground trace', () => {
  it('reconstructs a historical Auto Route run with classifier and route steps', () => {
    const state = runToTraceState(AUTO_ROUTE_RUN)
    expect(state.outcome).toBe('completed')
    expect(state.steps.map((s) => s.kind)).toEqual(['workflow', 'classifier', 'route', 'agent'])
    expect(state.route).toBe('coding')
  })

  it('marks every step of a successful run as completed', () => {
    const state = runToTraceState(AUTO_ROUTE_RUN)
    expect(state.steps.every((s) => s.status === 'completed')).toBe(true)
  })

  it('carries the final response through runCompleted', () => {
    const state = runToTraceState(AUTO_ROUTE_RUN)
    expect(state.runCompleted?.reply).toBe('Here is the function you asked for.')
    expect(state.runCompleted?.success).toBe(true)
  })

  it('does NOT show a classifier or route step for a historical Direct Agent run', () => {
    const state = runToTraceState(DIRECT_AGENT_RUN)
    expect(state.steps.map((s) => s.kind)).not.toContain('classifier')
    expect(state.steps.map((s) => s.kind)).not.toContain('route')
    expect(state.steps.map((s) => s.kind)).toEqual(['workflow', 'agent', 'tool'])
  })

  it('renders tool execution from tool_events, completed status and duration', () => {
    const state = runToTraceState(DIRECT_AGENT_RUN)
    const toolStep = state.steps.find((s) => s.kind === 'tool')
    expect(toolStep?.label).toBe('fetch')
    expect(toolStep?.status).toBe('completed')
    expect(toolStep?.durationMs).toBe(150)
  })

  it('reflects a failed run with a safe failure reason, not a raw exception', () => {
    const state = runToTraceState(FAILED_RUN)
    expect(state.outcome).toBe('failed')
    expect(state.failureReason).toContain('RuntimeError')
    expect(state.runCompleted?.success).toBe(false)
  })

  it('never renders as idle for a real historical run', () => {
    expect(runToTraceState(AUTO_ROUTE_RUN).outcome).not.toBe('idle')
    expect(runToTraceState(DIRECT_AGENT_RUN).outcome).not.toBe('idle')
    expect(runToTraceState(FAILED_RUN).outcome).not.toBe('idle')
  })
})
