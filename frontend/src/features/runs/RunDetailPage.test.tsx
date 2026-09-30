import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { NexusApiError } from '@/types/api'
import { AUTO_ROUTE_RUN, DIRECT_AGENT_RUN, FAILED_RUN } from '@/test/runFixtures'

const { getRunMock, replayRunMock } = vi.hoisted(() => ({ getRunMock: vi.fn(), replayRunMock: vi.fn() }))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getRun: getRunMock, replayRun: replayRunMock },
}))

const { RunDetailPage } = await import('./RunDetailPage')

function renderAt(path: string) {
  render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/runs/:requestId" element={<RunDetailPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RunDetailPage', () => {
  beforeEach(() => {
    getRunMock.mockReset()
    replayRunMock.mockReset()
  })

  it('renders the run header, summary metadata, and final response for an Auto Route run', async () => {
    getRunMock.mockResolvedValue(AUTO_ROUTE_RUN)
    renderAt('/runs/req-auto-1')

    // "Completed" legitimately appears twice: the header status badge and
    // the workflow trace step (both reuse StatusIndicator).
    await waitFor(() => expect(screen.getAllByText('Completed').length).toBeGreaterThan(0))
    expect(screen.getAllByText(/req-auto-1/).length).toBeGreaterThan(0)
    expect(screen.getByText('coding', { selector: 'span' })).toBeInTheDocument()
    expect(screen.getByText('150')).toBeInTheDocument() // total tokens
    expect(screen.getByText('Here is the function you asked for.')).toBeInTheDocument()
  })

  it('renders the shared execution trace, including classifier and route steps', async () => {
    getRunMock.mockResolvedValue(AUTO_ROUTE_RUN)
    renderAt('/runs/req-auto-1')
    await waitFor(() => expect(screen.getByLabelText('Execution trace')).toBeInTheDocument())
    expect(screen.getByText('Classifier')).toBeInTheDocument()
    expect(screen.getByText('Route: coding')).toBeInTheDocument()
  })

  it('does not show a classifier or route step for a historical Direct Agent run', async () => {
    getRunMock.mockResolvedValue(DIRECT_AGENT_RUN)
    renderAt('/runs/req-direct-1')
    await waitFor(() => expect(screen.getByLabelText('Execution trace')).toBeInTheDocument())
    expect(screen.queryByText('Classifier')).not.toBeInTheDocument()
    expect(screen.queryByText(/^Route:/)).not.toBeInTheDocument()
  })

  it('renders tool activity for a run that used a tool', async () => {
    getRunMock.mockResolvedValue(DIRECT_AGENT_RUN)
    renderAt('/runs/req-direct-1')
    await waitFor(() => expect(screen.getByText('fetch')).toBeInTheDocument())
  })

  it('shows "Not reported" (never a fake zero) for unavailable tokens and cost', async () => {
    getRunMock.mockResolvedValue(DIRECT_AGENT_RUN)
    renderAt('/runs/req-direct-1')
    await waitFor(() => expect(screen.getByText('Logical', { selector: 'span' })).toBeInTheDocument())
    expect(screen.getAllByText('Not reported').length).toBeGreaterThanOrEqual(2)
  })

  it('renders a failure banner with the safe error type for a failed run', async () => {
    getRunMock.mockResolvedValue(FAILED_RUN)
    renderAt('/runs/req-failed-1')
    await waitFor(() => expect(screen.getByText('Execution failed')).toBeInTheDocument())
    expect(screen.getByText('RuntimeError')).toBeInTheDocument()
    expect(screen.getAllByText('Failed').length).toBeGreaterThan(0)
  })

  it('shows a polished not-found state for a 404, with navigation back to Runs', async () => {
    getRunMock.mockRejectedValue(new NexusApiError(404, { code: 'RUN_NOT_FOUND', message: 'No run with this request_id is available.' }))
    renderAt('/runs/req-does-not-exist')
    await waitFor(() => expect(screen.getByText('Run not found')).toBeInTheDocument())
    expect(screen.getByText(/expired from the bounded runtime store/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /back to runs/i })).toHaveAttribute('href', '/runs')
  })

  it('links View Session to the run\'s thread (Run -> Session navigation)', async () => {
    getRunMock.mockResolvedValue(AUTO_ROUTE_RUN)
    renderAt('/runs/req-auto-1')
    await waitFor(() => expect(screen.getByRole('link', { name: 'View Session' })).toBeInTheDocument())
    expect(screen.getByRole('link', { name: 'View Session' })).toHaveAttribute(
      'href',
      `/sessions/${AUTO_ROUTE_RUN.thread_id}`,
    )
  })

  it('links a run to its agent and retained tool activity', async () => {
    getRunMock.mockResolvedValue(DIRECT_AGENT_RUN)
    renderAt('/runs/req-direct-1')

    expect(await screen.findByRole('link', { name: 'Agent Logical' })).toHaveAttribute('href', '/agents/logical')
    expect(screen.getByRole('link', { name: 'Tool activity' })).toHaveAttribute('href', '/tools')
  })

  it('shows an error panel for a generic failure, distinct from not-found', async () => {
    getRunMock.mockRejectedValue(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    renderAt('/runs/req-auto-1')
    await waitFor(() => expect(screen.getByText(/nexus is unreachable/i)).toBeInTheDocument())
  })

  it('offers Compare and a confirmed re-run without replacing the source run', async () => {
    getRunMock.mockResolvedValue(AUTO_ROUTE_RUN)
    replayRunMock.mockResolvedValue({
      ...AUTO_ROUTE_RUN,
      request_id: 'req-replay-new',
      thread_id: 'thread-replay-new',
      replay_of: AUTO_ROUTE_RUN.request_id,
    })
    const user = userEvent.setup()
    renderAt('/runs/req-auto-1')

    expect(await screen.findByRole('link', { name: 'Compare' })).toHaveAttribute('href', '/runs/req-auto-1/compare')
    await user.click(screen.getByRole('button', { name: 'Re-run' }))
    expect(screen.getByRole('alertdialog')).toHaveTextContent(/fresh session/i)
    await user.click(screen.getByRole('button', { name: 'Confirm re-run' }))

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('req-replay-new'))
    expect(replayRunMock).toHaveBeenCalledWith(AUTO_ROUTE_RUN.request_id)
    expect(screen.getByRole('heading', { name: 'Run' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'req-replay-new' })).toHaveAttribute('href', '/runs/req-replay-new')
  })

  it('shows the replay loading state while the request is pending', async () => {
    getRunMock.mockResolvedValue(AUTO_ROUTE_RUN)
    replayRunMock.mockReturnValue(new Promise(() => {}))
    const user = userEvent.setup()
    renderAt('/runs/req-auto-1')

    await user.click(await screen.findByRole('button', { name: 'Re-run' }))
    await user.click(screen.getByRole('button', { name: 'Confirm re-run' }))
    expect(await screen.findByRole('status')).toHaveTextContent('Starting a new run')
  })

  it('shows a safe replay error', async () => {
    getRunMock.mockResolvedValue(AUTO_ROUTE_RUN)
    replayRunMock.mockRejectedValue(new NexusApiError(409, {
      code: 'RUN_NOT_REPLAYABLE',
      message: 'This run cannot be re-run because its original context is unavailable.',
    }))
    const user = userEvent.setup()
    renderAt('/runs/req-auto-1')

    await user.click(await screen.findByRole('button', { name: 'Re-run' }))
    await user.click(screen.getByRole('button', { name: 'Confirm re-run' }))
    expect(await screen.findByText(/original context is unavailable/i)).toBeInTheDocument()
  })

  it('explains why re-run is unavailable for a stateful turn', async () => {
    getRunMock.mockResolvedValue({
      ...AUTO_ROUTE_RUN,
      replayable: false,
      replay_unavailable_reason: 'thread_has_prior_state',
    })
    renderAt('/runs/req-auto-1')

    expect(await screen.findByText(/used earlier conversation state/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Re-run' })).toBeDisabled()
  })
})
