import { render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { NexusApiError } from '@/types/api'
import { MOCK_AGENTS } from '@/test/agentFixtures'

const { getAgentMock } = vi.hoisted(() => ({ getAgentMock: vi.fn() }))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getAgent: getAgentMock },
}))

const { AgentDetailPage } = await import('./AgentDetailPage')

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/agents/:agentId" element={<AgentDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('AgentDetailPage', () => {
  beforeEach(() => {
    getAgentMock.mockReset()
  })

  it('shows the agent name, capabilities, tools, and a Test Agent link once loaded', async () => {
    getAgentMock.mockResolvedValue(MOCK_AGENTS[0])
    renderAt('/agents/logical')
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Logical Agent' })).toBeInTheDocument())
    expect(screen.getByText('reasoning')).toBeInTheDocument()
    expect(screen.getByText('web_retrieval')).toBeInTheDocument()
    expect(screen.getByText('fetch')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'fetch' })).toHaveAttribute('href', '/tools')
    expect(screen.getByRole('link', { name: 'Test Agent' })).toHaveAttribute('href', '/playground?agent=logical')
  })

  it('shows a clear not-found state for an unknown agent id, never a blank page', async () => {
    getAgentMock.mockRejectedValue(new NexusApiError(404, { code: 'AGENT_NOT_FOUND', message: 'No agent with this id is registered.' }))
    renderAt('/agents/ghost')
    await waitFor(() => expect(screen.getByText(/no agent named/i)).toBeInTheDocument())
    expect(screen.getByRole('link', { name: /back to agents/i })).toHaveAttribute('href', '/agents')
  })

  it('shows an error state for a generic failure, distinct from not-found', async () => {
    getAgentMock.mockRejectedValue(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    renderAt('/agents/logical')
    await waitFor(() => expect(screen.getByText(/nexus is unreachable/i)).toBeInTheDocument())
  })

  it('disables Test Agent for an unavailable agent', async () => {
    getAgentMock.mockResolvedValue({ ...MOCK_AGENTS[0], status: 'unavailable' })
    renderAt('/agents/logical')
    await waitFor(() => expect(screen.getByText('Unavailable')).toBeInTheDocument())
    expect(screen.queryByRole('link', { name: 'Test Agent' })).not.toBeInTheDocument()
    expect(screen.getByText(/test agent \(unavailable\)/i)).toBeInTheDocument()
  })
})
