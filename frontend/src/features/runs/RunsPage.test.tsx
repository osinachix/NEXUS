import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { NexusApiError } from '@/types/api'
import { AUTO_ROUTE_RUN, DIRECT_AGENT_RUN, FAILED_RUN } from '@/test/runFixtures'
import { MOCK_AGENTS } from '@/test/agentFixtures'

const { getRunsMock, getAgentsMock } = vi.hoisted(() => ({
  getRunsMock: vi.fn(),
  getAgentsMock: vi.fn(),
}))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getRuns: getRunsMock, getAgents: getAgentsMock },
}))

const { RunsPage } = await import('./RunsPage')

function renderPage(initialPath = '/runs') {
  render(
    <MemoryRouter initialEntries={[initialPath]}>
      <RunsPage />
    </MemoryRouter>,
  )
}

describe('RunsPage', () => {
  beforeEach(() => {
    getRunsMock.mockReset()
    getAgentsMock.mockReset()
    getAgentsMock.mockResolvedValue(MOCK_AGENTS)
  })

  it('shows a loading state, never fake runs, while the request is pending', () => {
    getRunsMock.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.queryByText('req-auto-1')).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('shows the empty state with a Playground link when there are no runs at all', async () => {
    getRunsMock.mockResolvedValue({ items: [], total: 0, limit: 50 })
    renderPage()
    await waitFor(() => expect(screen.getByText('No runs yet')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: 'Open Playground' })).toHaveAttribute('href', '/playground')
  })

  it('renders a row per run with status, agent, route, latency, and tokens', async () => {
    getRunsMock.mockResolvedValue({ items: [AUTO_ROUTE_RUN, DIRECT_AGENT_RUN], total: 2, limit: 50 })
    renderPage()
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())

    expect(screen.getByRole('cell', { name: 'Coding' })).toBeInTheDocument() // agent display name
    expect(screen.getByText('coding')).toBeInTheDocument() // route
    expect(screen.getByText('350 ms')).toBeInTheDocument()
    expect(screen.getByText('150')).toBeInTheDocument() // total_tokens

    expect(screen.getByRole('cell', { name: 'Logical' })).toBeInTheDocument()
    // Direct-agent run has no route -- rendered as "--", not a fake value.
    const dashCells = screen.getAllByText('--')
    expect(dashCells.length).toBeGreaterThan(0)
  })

  it('renders a failed run with a Failed status indicator', async () => {
    getRunsMock.mockResolvedValue({ items: [FAILED_RUN], total: 1, limit: 50 })
    renderPage()
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })

  it('links each row to its Run Detail page', async () => {
    getRunsMock.mockResolvedValue({ items: [AUTO_ROUTE_RUN], total: 1, limit: 50 })
    renderPage()
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())
    const link = screen.getByRole('link', { name: /req-auto-1/ })
    expect(link).toHaveAttribute('href', '/runs/req-auto-1')
  })

  it('re-fetches with the status filter applied', async () => {
    getRunsMock.mockResolvedValue({ items: [AUTO_ROUTE_RUN], total: 1, limit: 50 })
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())

    await user.selectOptions(screen.getByLabelText('Status'), 'failed')
    await waitFor(() => expect(getRunsMock).toHaveBeenLastCalledWith({ limit: 100, status: 'failed', agent: undefined }))
  })

  it('filters client-side by search text matching the request or thread ID', async () => {
    getRunsMock.mockResolvedValue({ items: [AUTO_ROUTE_RUN, DIRECT_AGENT_RUN], total: 2, limit: 50 })
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())

    await user.type(screen.getByLabelText('Search'), 'req-direct')

    expect(screen.queryByText('req-auto-1'.slice(0, 12))).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /req-direct-1/ })).toBeInTheDocument()
  })

  it('shows a filter-aware empty state when search matches nothing', async () => {
    getRunsMock.mockResolvedValue({ items: [AUTO_ROUTE_RUN], total: 1, limit: 50 })
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())

    await user.type(screen.getByLabelText('Search'), 'no-such-run')

    expect(screen.getByText('No runs match the current filters.')).toBeInTheDocument()
    expect(screen.queryByText('No runs yet')).not.toBeInTheDocument()
  })

  it('shows an error panel with retry when the request fails', async () => {
    getRunsMock.mockRejectedValueOnce(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    getRunsMock.mockResolvedValueOnce({ items: [AUTO_ROUTE_RUN], total: 1, limit: 50 })
    const user = userEvent.setup()
    renderPage()

    await waitFor(() => expect(screen.getByText(/nexus is unreachable/i)).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /retry/i }))
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())
  })

  it('applies a ?thread_id= URL param as a server-side filter (Session -> Runs navigation)', async () => {
    getRunsMock.mockResolvedValue({ items: [AUTO_ROUTE_RUN], total: 1, limit: 100 })
    renderPage('/runs?thread_id=thread-auto-1')

    await waitFor(() =>
      expect(getRunsMock).toHaveBeenCalledWith({
        limit: 100,
        status: undefined,
        agent: undefined,
        thread_id: 'thread-auto-1',
      }),
    )
    expect(screen.getByText(/showing runs for session/i)).toBeInTheDocument()
  })

  it('Clear on the thread filter banner removes the thread_id filter', async () => {
    getRunsMock.mockResolvedValue({ items: [AUTO_ROUTE_RUN], total: 1, limit: 100 })
    const user = userEvent.setup()
    renderPage('/runs?thread_id=thread-auto-1')
    await waitFor(() => expect(screen.getByText(/showing runs for session/i)).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Clear' }))

    await waitFor(() =>
      expect(getRunsMock).toHaveBeenLastCalledWith({
        limit: 100,
        status: undefined,
        agent: undefined,
        thread_id: undefined,
      }),
    )
    expect(screen.queryByText(/showing runs for session/i)).not.toBeInTheDocument()
  })
})
