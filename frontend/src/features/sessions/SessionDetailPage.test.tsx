import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { NexusApiError } from '@/types/api'
import { SESSION_DETAIL } from '@/test/sessionFixtures'

const { getSessionMock } = vi.hoisted(() => ({ getSessionMock: vi.fn() }))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getSession: getSessionMock },
}))

const { SessionDetailPage } = await import('./SessionDetailPage')

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/sessions/:threadId" element={<SessionDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('SessionDetailPage', () => {
  beforeEach(() => {
    getSessionMock.mockReset()
  })

  it('renders the header, summary metadata, and message history', async () => {
    getSessionMock.mockResolvedValue(SESSION_DETAIL)
    renderAt('/sessions/thread-aaa111')

    await waitFor(() => expect(screen.getAllByText(/thread-aaa111/).length).toBeGreaterThan(0))
    expect(screen.getByText('4')).toBeInTheDocument() // message count
    // "coding" legitimately appears twice: Last Route and Classification
    // are the same value for an auto-routed turn.
    expect(screen.getAllByText('coding', { selector: 'span' }).length).toBe(2)
    expect(screen.getByText('write a function that adds two numbers')).toBeInTheDocument()
  })

  it('renders messages oldest first with User/Agent role labels', async () => {
    getSessionMock.mockResolvedValue(SESSION_DETAIL)
    renderAt('/sessions/thread-aaa111')
    await waitFor(() => expect(screen.getAllByText('User').length).toBeGreaterThan(0))

    const roleLabels = screen.getAllByText(/^(User|Agent)$/)
    expect(roleLabels.map((el) => el.textContent)).toEqual(['User', 'Agent', 'User', 'Agent'])
  })

  it('renders message content as plain text, never interpreted as HTML', async () => {
    getSessionMock.mockResolvedValue({
      ...SESSION_DETAIL,
      messages: [{ role: 'human', content: '<script>alert(1)</script>' }],
    })
    renderAt('/sessions/thread-aaa111')
    await waitFor(() => expect(screen.getByText('<script>alert(1)</script>')).toBeInTheDocument())
    expect(document.querySelector('script[src], script:not(:empty)')).not.toBeInTheDocument()
  })

  it('links View Runs to the runs page filtered by this thread', async () => {
    getSessionMock.mockResolvedValue(SESSION_DETAIL)
    renderAt('/sessions/thread-aaa111')
    await waitFor(() => expect(screen.getByRole('link', { name: 'View Runs' })).toBeInTheDocument())
    expect(screen.getByRole('link', { name: 'View Runs' })).toHaveAttribute('href', '/runs?thread_id=thread-aaa111')
  })

  it('Refresh re-fetches the session', async () => {
    getSessionMock.mockResolvedValue(SESSION_DETAIL)
    const user = userEvent.setup()
    renderAt('/sessions/thread-aaa111')
    await waitFor(() => expect(screen.getByRole('button', { name: 'Refresh' })).toBeInTheDocument())

    await user.click(screen.getByRole('button', { name: 'Refresh' }))
    await waitFor(() => expect(getSessionMock).toHaveBeenCalledTimes(2))
  })

  it('shows a polished not-found state for a 404, with navigation back to Sessions', async () => {
    getSessionMock.mockRejectedValue(
      new NexusApiError(404, { code: 'SESSION_NOT_FOUND', message: 'No session exists for this thread_id.' }),
    )
    renderAt('/sessions/thread-does-not-exist')
    await waitFor(() => expect(screen.getByText('Session not found')).toBeInTheDocument())
    expect(screen.getByRole('link', { name: /back to sessions/i })).toHaveAttribute('href', '/sessions')
  })

  it('shows an error panel for a generic failure, distinct from not-found', async () => {
    getSessionMock.mockRejectedValue(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    renderAt('/sessions/thread-aaa111')
    await waitFor(() => expect(screen.getByText(/nexus is unreachable/i)).toBeInTheDocument())
  })
})
