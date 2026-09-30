import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import type { NexusEvent } from '@/types/events'
import { NexusApiError } from '@/types/api'
import { MOCK_AGENTS } from '@/test/agentFixtures'

const { createSessionMock, getRunMock, streamMock, getAgentsMock } = vi.hoisted(() => ({
  createSessionMock: vi.fn(),
  getRunMock: vi.fn(),
  streamMock: vi.fn(),
  getAgentsMock: vi.fn(),
}))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: {
    createSession: createSessionMock,
    getRun: getRunMock,
    getAgents: getAgentsMock,
    health: vi.fn().mockResolvedValue({ status: 'ok', service: 'nexus-api' }),
  },
}))

vi.mock('@/lib/sseClient', () => ({
  nexusSse: { stream: streamMock },
}))

// Imported after the mocks above so the module picks up the mocked deps.
const { Playground } = await import('./Playground')

function renderPlayground() {
  return render(
    <MemoryRouter>
      <Playground />
    </MemoryRouter>,
  )
}

function emit(handlers: Parameters<typeof streamMock>[2], events: Partial<NexusEvent>[]) {
  for (const event of events) {
    handlers.onEvent({ request_id: 'req-1', thread_id: 'thread-1', timestamp: 't', ...event } as NexusEvent)
  }
}

describe('Playground', () => {
  beforeEach(() => {
    createSessionMock.mockReset()
    getRunMock.mockReset()
    streamMock.mockReset()
    getAgentsMock.mockReset()
    createSessionMock.mockResolvedValue({ thread_id: 'thread-1' })
    getAgentsMock.mockResolvedValue(MOCK_AGENTS)
    getRunMock.mockResolvedValue({
      request_id: 'req-1',
      thread_id: 'thread-1',
      status: 'completed',
      route: 'math',
      duration_ms: 120,
      success: true,
      created_at: 't',
      message_type: 'math',
      started_at: 't',
      completed_at: 't',
      events: [],
      tool_events: [],
      usage: { input_tokens: 10, output_tokens: 5, total_tokens: 15 },
      cost_usd: 0.0021,
      error_type: null,
    })
  })

  it('creates a real session on mount and enables the composer once ready', async () => {
    renderPlayground()
    expect(createSessionMock).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(screen.getByLabelText(/message to nexus/i)).toBeEnabled())
    expect(screen.getByText('thread-1')).toBeInTheDocument()
    // Phase 6.4: "View Session" only appears once a turn has actually
    // completed -- before that the thread has no persisted checkpoint
    // state yet, and Session Detail would just 404.
    expect(screen.queryByRole('link', { name: 'View Session' })).not.toBeInTheDocument()
  })

  it('disables the composer while the session is being created', () => {
    createSessionMock.mockReturnValue(new Promise(() => {})) // never resolves
    renderPlayground()
    expect(screen.getByLabelText(/message to nexus/i)).toBeDisabled()
  })

  it('shows an error panel with retry when session creation fails', async () => {
    createSessionMock.mockRejectedValue(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    renderPlayground()
    await waitFor(() => expect(screen.getByText(/nexus is unreachable/i)).toBeInTheDocument())
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
  })

  it('sends a message and renders the live trace as events arrive, then the final response', async () => {
    const user = userEvent.setup()
    renderPlayground()
    await waitFor(() => expect(screen.getByLabelText(/message to nexus/i)).toBeEnabled())

    await user.type(screen.getByLabelText(/message to nexus/i), 'what is 2+2?{Enter}')

    expect(streamMock).toHaveBeenCalledWith('thread-1', { message: 'what is 2+2?', agent: undefined }, expect.anything())
    const handlers = streamMock.mock.calls[0][2]

    emit(handlers, [
      { event_type: 'workflow_started' },
      { event_type: 'classifier_started', node: 'classifier' },
      { event_type: 'classifier_completed', success: true },
      { event_type: 'route_selected', route: 'math' },
      { event_type: 'agent_started', node: 'math' },
      { event_type: 'agent_completed', node: 'math', success: true },
      { event_type: 'workflow_completed', success: true },
    ])

    // "Math Agent" legitimately appears twice once routed (the route
    // visualization's flow arrow, and the trace step itself).
    await waitFor(() => expect(screen.getAllByText('Math Agent').length).toBeGreaterThan(0))
    expect(screen.getByText('Route: math')).toBeInTheDocument()

    emit(handlers, [{ event_type: 'run_completed', status: 'completed', success: true, route: 'math', reply: '2+2 is 4', duration_ms: 400 }])
    handlers.onClose('completed')

    await waitFor(() => expect(screen.getByText('2+2 is 4')).toBeInTheDocument())
    await waitFor(() => expect(screen.getByText('15')).toBeInTheDocument()) // total tokens from GET /v1/runs
    expect(screen.getByRole('link', { name: 'View Session' })).toHaveAttribute('href', '/sessions/thread-1')
  })

  it('sends the selected agent when in direct-agent mode, and the classifier never appears', async () => {
    const user = userEvent.setup()
    renderPlayground()
    await waitFor(() => expect(screen.getByLabelText(/message to nexus/i)).toBeEnabled())
    await waitFor(() => expect(screen.getByRole('option', { name: /Direct Agent: Coding/ })).toBeInTheDocument())

    await user.selectOptions(screen.getByLabelText(/execution mode/i), 'coding')
    await user.type(screen.getByLabelText(/message to nexus/i), 'write a function{Enter}')

    expect(streamMock).toHaveBeenCalledWith('thread-1', { message: 'write a function', agent: 'coding' }, expect.anything())
    const handlers = streamMock.mock.calls[0][2]
    emit(handlers, [{ event_type: 'workflow_started' }, { event_type: 'agent_started', node: 'coding' }])

    // "Coding Agent" legitimately appears twice in direct mode (the
    // "Direct Agent" panel, and the trace step itself).
    await waitFor(() => expect(screen.getAllByText('Coding Agent').length).toBeGreaterThan(0))
    expect(screen.queryByText('Classifier')).not.toBeInTheDocument()
  })

  it('shows an error panel when the run itself errors, and stops the running state', async () => {
    const user = userEvent.setup()
    renderPlayground()
    await waitFor(() => expect(screen.getByLabelText(/message to nexus/i)).toBeEnabled())

    await user.type(screen.getByLabelText(/message to nexus/i), 'hello{Enter}')
    const handlers = streamMock.mock.calls[0][2]
    handlers.onError(new NexusApiError(429, { code: 'RATE_LIMITED', message: 'Rate limit exceeded.' }, 30))

    await waitFor(() => expect(screen.getByText(/rate limit reached/i)).toBeInTheDocument())
    expect(screen.getByText(/retry after 30s/i)).toBeInTheDocument()
    // Composer is usable again (not stuck in a running state).
    expect(screen.getByLabelText(/send message/i)).toBeInTheDocument()
  })
})
