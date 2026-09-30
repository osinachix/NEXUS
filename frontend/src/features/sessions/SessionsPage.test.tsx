import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { NexusApiError } from '@/types/api'
import { SESSION_SUMMARY_A, SESSION_SUMMARY_B } from '@/test/sessionFixtures'

const { getSessionsMock } = vi.hoisted(() => ({ getSessionsMock: vi.fn() }))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getSessions: getSessionsMock },
}))

const { SessionsPage } = await import('./SessionsPage')

function renderPage() {
  render(
    <MemoryRouter>
      <SessionsPage />
    </MemoryRouter>,
  )
}

describe('SessionsPage', () => {
  beforeEach(() => {
    getSessionsMock.mockReset()
  })

  it('shows a loading state, never fake sessions, while the request is pending', () => {
    getSessionsMock.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.queryByText('thread-aaa111'.slice(0, 12))).not.toBeInTheDocument()
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('shows the empty state with a Playground link when there are no sessions at all', async () => {
    getSessionsMock.mockResolvedValue({ items: [], limit: 50 })
    renderPage()
    await waitFor(() => expect(screen.getByText('No sessions yet')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: 'Open Playground' })).toHaveAttribute('href', '/playground')
  })

  it('renders a row per session with message count, route, and classification', async () => {
    getSessionsMock.mockResolvedValue({ items: [SESSION_SUMMARY_A, SESSION_SUMMARY_B], limit: 50 })
    renderPage()
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())

    expect(screen.getByRole('cell', { name: '4' })).toBeInTheDocument()
    // "coding" legitimately appears twice in one row: last_route and
    // last_message_type are the same value for an auto-routed turn.
    expect(screen.getAllByRole('cell', { name: 'coding' }).length).toBe(2)
    expect(screen.getAllByRole('cell', { name: 'math' }).length).toBe(2)
  })

  it('links each row to its Session Detail page', async () => {
    getSessionsMock.mockResolvedValue({ items: [SESSION_SUMMARY_A], limit: 50 })
    renderPage()
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())
    const link = screen.getByRole('link', { name: /thread-aaa111/ })
    expect(link).toHaveAttribute('href', '/sessions/thread-aaa111')
  })

  it('filters client-side by search text matching thread id, route, or classification', async () => {
    getSessionsMock.mockResolvedValue({ items: [SESSION_SUMMARY_A, SESSION_SUMMARY_B], limit: 50 })
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())

    await user.type(screen.getByLabelText('Search'), 'math')

    expect(screen.queryByRole('link', { name: /thread-aaa111/ })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /thread-bbb222/ })).toBeInTheDocument()
  })

  it('shows a filter-aware empty state when search matches nothing', async () => {
    getSessionsMock.mockResolvedValue({ items: [SESSION_SUMMARY_A], limit: 50 })
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())

    await user.type(screen.getByLabelText('Search'), 'no-such-session')

    expect(screen.getByText('No sessions match this search.')).toBeInTheDocument()
    expect(screen.queryByText('No sessions yet')).not.toBeInTheDocument()
  })

  it('sorts oldest first when selected', async () => {
    getSessionsMock.mockResolvedValue({ items: [SESSION_SUMMARY_A, SESSION_SUMMARY_B], limit: 50 })
    const user = userEvent.setup()
    renderPage()
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())

    await user.selectOptions(screen.getByLabelText('Order'), 'oldest')

    const links = screen.getAllByRole('link', { name: /thread-/ })
    expect(links[0]).toHaveAttribute('href', '/sessions/thread-bbb222')
  })

  it('shows an error panel with retry when the request fails', async () => {
    getSessionsMock.mockRejectedValueOnce(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    getSessionsMock.mockResolvedValueOnce({ items: [SESSION_SUMMARY_A], limit: 50 })
    const user = userEvent.setup()
    renderPage()

    await waitFor(() => expect(screen.getByText(/nexus is unreachable/i)).toBeInTheDocument())
    await user.click(screen.getByRole('button', { name: /retry/i }))
    await waitFor(() => expect(screen.getByRole('table')).toBeInTheDocument())
  })
})
