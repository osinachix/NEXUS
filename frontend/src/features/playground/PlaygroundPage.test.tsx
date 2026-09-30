import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { MOCK_AGENTS } from '@/test/agentFixtures'

const { createSessionMock, getAgentsMock, streamMock } = vi.hoisted(() => ({
  createSessionMock: vi.fn(),
  getAgentsMock: vi.fn(),
  streamMock: vi.fn(),
}))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: {
    createSession: createSessionMock,
    getAgents: getAgentsMock,
    health: vi.fn().mockResolvedValue({ status: 'ok', service: 'nexus-api' }),
  },
}))

vi.mock('@/lib/sseClient', () => ({
  nexusSse: { stream: streamMock },
}))

const { PlaygroundPage } = await import('./PlaygroundPage')

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <PlaygroundPage />
    </MemoryRouter>,
  )
}

describe('PlaygroundPage', () => {
  beforeEach(() => {
    createSessionMock.mockReset()
    getAgentsMock.mockReset()
    streamMock.mockReset()
    createSessionMock.mockResolvedValue({ thread_id: 'thread-1' })
    getAgentsMock.mockResolvedValue(MOCK_AGENTS)
  })

  it('with no ?agent param, defaults to Auto Route', async () => {
    renderAt('/playground')
    await waitFor(() => expect(screen.getByLabelText(/message to nexus/i)).toBeEnabled())
    expect(screen.getByLabelText(/execution mode/i)).toHaveValue('auto')
  })

  it('preselects the direct-agent mode named in ?agent, matching the Test Agent flow', async () => {
    renderAt('/playground?agent=coding')
    await waitFor(() => expect(screen.getByLabelText(/message to nexus/i)).toBeEnabled())
    await waitFor(() => expect(screen.getByLabelText(/execution mode/i)).toHaveValue('coding'))
    expect(screen.getByText(/runs the coding agent directly/i)).toBeInTheDocument()
  })

  it('falls back to Auto Route and shows a clear notice for an unknown ?agent id', async () => {
    renderAt('/playground?agent=does-not-exist')
    await waitFor(() => expect(screen.getByLabelText(/message to nexus/i)).toBeEnabled())
    expect(screen.getByLabelText(/execution mode/i)).toHaveValue('auto')
    await waitFor(() => expect(screen.getByText(/"does-not-exist" is not an available agent/i)).toBeInTheDocument())
  })

  it('falls back to Auto Route for an agent id that exists but is unavailable', async () => {
    getAgentsMock.mockResolvedValue([...MOCK_AGENTS, { ...MOCK_AGENTS[0], id: 'retired', name: 'Retired', status: 'unavailable' as const }])
    renderAt('/playground?agent=retired')
    await waitFor(() => expect(screen.getByLabelText(/message to nexus/i)).toBeEnabled())
    expect(screen.getByLabelText(/execution mode/i)).toHaveValue('auto')
    await waitFor(() => expect(screen.getByText(/"retired" is not an available agent/i)).toBeInTheDocument())
  })
})
