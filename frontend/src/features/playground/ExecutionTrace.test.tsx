import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { reduceTraceEvents } from '@/lib/traceReducer'
import type { NexusEvent } from '@/types/events'
import { initialTraceState } from '@/lib/traceReducer'
import { ExecutionTrace } from './ExecutionTrace'

function ev(event_type: string, extra: Partial<NexusEvent> = {}): NexusEvent {
  return { event_type, request_id: 'r1', thread_id: 't1', timestamp: '2026-01-01T00:00:00Z', ...extra }
}

describe('ExecutionTrace', () => {
  it('shows an empty-state message before any execution has started', () => {
    render(<ExecutionTrace trace={initialTraceState()} />)
    expect(screen.getByText(/send a message to see the execution trace live/i)).toBeInTheDocument()
  })

  it('renders steps as they accumulate (incremental arrival)', () => {
    const afterFirstEvent = reduceTraceEvents([ev('workflow_started')])
    const { rerender } = render(<ExecutionTrace trace={afterFirstEvent} />)
    expect(screen.getByText('Workflow')).toBeInTheDocument()
    expect(screen.queryByText(/logical agent/i)).not.toBeInTheDocument()

    const afterAgentStarted = reduceTraceEvents([ev('workflow_started'), ev('agent_started', { node: 'logical' })])
    rerender(<ExecutionTrace trace={afterAgentStarted} />)
    expect(screen.getByText('Logical Agent')).toBeInTheDocument()
  })

  it('shows a running status while a step is in progress', () => {
    const trace = reduceTraceEvents([ev('workflow_started'), ev('agent_started', { node: 'math' })])
    render(<ExecutionTrace trace={trace} />)
    expect(screen.getAllByText('Running').length).toBeGreaterThan(0)
  })

  it('shows a completed status once a step finishes successfully', () => {
    const trace = reduceTraceEvents([
      ev('workflow_started'),
      ev('agent_started', { node: 'math' }),
      ev('agent_completed', { node: 'math', success: true }),
    ])
    render(<ExecutionTrace trace={trace} />)
    expect(screen.getByText('Completed')).toBeInTheDocument()
  })

  it('shows a failed status when a step fails', () => {
    const trace = reduceTraceEvents([
      ev('workflow_started'),
      ev('agent_started', { node: 'math' }),
      ev('agent_completed', { node: 'math', success: false, error_type: 'RuntimeError' }),
    ])
    render(<ExecutionTrace trace={trace} />)
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })

  it('displays the selected route', () => {
    const trace = reduceTraceEvents([ev('workflow_started'), ev('route_selected', { route: 'coding' })])
    render(<ExecutionTrace trace={trace} />)
    expect(screen.getByText('Route: coding')).toBeInTheDocument()
  })

  it('displays tool activity with its status', () => {
    const trace = reduceTraceEvents([
      ev('workflow_started'),
      ev('tool_started', { tool: 'fetch' }),
      ev('tool_completed', { tool: 'fetch', success: true, duration_ms: 143 }),
    ])
    render(<ExecutionTrace trace={trace} />)
    expect(screen.getByText('fetch')).toBeInTheDocument()
    expect(screen.getByText('Completed')).toBeInTheDocument()
    expect(screen.getByText('143 ms')).toBeInTheDocument()
  })

  it('displays a denied tool with its reason, distinct from a failure', () => {
    const trace = reduceTraceEvents([
      ev('workflow_started'),
      ev('tool_started', { tool: 'fetch' }),
      ev('tool_denied', { tool: 'fetch', reason: 'PRIVATE_ADDRESS' }),
    ])
    render(<ExecutionTrace trace={trace} />)
    expect(screen.getByText('Denied')).toBeInTheDocument()
    expect(screen.getByText('PRIVATE_ADDRESS')).toBeInTheDocument()
  })
})
