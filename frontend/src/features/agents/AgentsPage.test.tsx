import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { NexusApiError } from '@/types/api'
import { MOCK_AGENTS } from '@/test/agentFixtures'

const { getAgentsMock } = vi.hoisted(() => ({ getAgentsMock: vi.fn() }))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getAgents: getAgentsMock },
}))

const { AgentsPage } = await import('./AgentsPage')

function renderPage() {
  render(
    <MemoryRouter>
      <AgentsPage />
    </MemoryRouter>,
  )
}

describe('AgentsPage', () => {
  beforeEach(() => {
    getAgentsMock.mockReset()
  })

  it('shows loading skeletons, never fake agent data, while the registry is loading', () => {
    getAgentsMock.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.queryByText('Logical')).not.toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Test Agent' })).not.toBeInTheDocument()
  })

  it('renders a card per registered agent once loaded', async () => {
    getAgentsMock.mockResolvedValue(MOCK_AGENTS)
    renderPage()
    await waitFor(() => expect(screen.getByText('Logical')).toBeInTheDocument())
    expect(screen.getByText('Math')).toBeInTheDocument()
    expect(screen.getByText('Coding')).toBeInTheDocument()
    expect(screen.getByText('Counselor')).toBeInTheDocument()
  })

  it('shows an empty state when the registry has no agents', async () => {
    getAgentsMock.mockResolvedValue([])
    renderPage()
    await waitFor(() => expect(screen.getByText(/no agents are registered/i)).toBeInTheDocument())
  })

  it('shows an error panel with retry when the registry fails to load', async () => {
    getAgentsMock.mockRejectedValueOnce(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    getAgentsMock.mockResolvedValueOnce(MOCK_AGENTS)
    const user = userEvent.setup()
    renderPage()

    await waitFor(() => expect(screen.getByText(/nexus is unreachable/i)).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /retry/i }))
    await waitFor(() => expect(screen.getByText('Logical')).toBeInTheDocument())
  })
})
