import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { MOCK_AGENTS } from '@/test/agentFixtures'
import { EVALUATION_A } from '@/test/evaluationFixtures'
import { NexusApiError } from '@/types/api'
import { DashboardPage } from './DashboardPage'

const {
  getAgentsMock,
  getEvaluationsMock,
  getRunSummariesMock,
  getToolActivityMock,
  getToolsMock,
} = vi.hoisted(() => ({
  getAgentsMock: vi.fn(),
  getEvaluationsMock: vi.fn(),
  getRunSummariesMock: vi.fn(),
  getToolActivityMock: vi.fn(),
  getToolsMock: vi.fn(),
}))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: {
    getAgents: getAgentsMock,
    getEvaluations: getEvaluationsMock,
    getRunSummaries: getRunSummariesMock,
    getToolActivity: getToolActivityMock,
    getTools: getToolsMock,
  },
}))

const runSummary = {
  request_id: 'req-dashboard-1', status: 'completed', route: 'logical', agent: 'logical',
  duration_ms: 320, success: true, created_at: '2026-09-30T10:00:00Z',
  started_at: '2026-09-30T09:59:59Z', completed_at: '2026-09-30T10:00:00Z',
  usage: { input_tokens: 100, output_tokens: 25, total_tokens: 125 }, cost_usd: 0.002,
}

const tool = {
  id: 'fetch', name: 'fetch', description: 'Fetch public web content.', status: 'active' as const,
  execution_type: 'native' as const, allowed_agents: ['logical'], controls: ['HTTPS by default'],
}

const toolActivity = {
  request_id: 'req-dashboard-1', tool: 'fetch', event_type: 'tool_completed' as const,
  agent: 'logical', timestamp: '2026-09-30T10:00:00Z', duration_ms: 42,
  success: true, reason: null, error_type: null,
}

function renderPage() {
  return render(<MemoryRouter><DashboardPage /></MemoryRouter>)
}

describe('DashboardPage', () => {
  beforeEach(() => {
    getAgentsMock.mockResolvedValue(MOCK_AGENTS)
    getEvaluationsMock.mockResolvedValue({ items: [EVALUATION_A], total: 1, limit: 5 })
    getRunSummariesMock.mockResolvedValue({ items: [runSummary], total: 1, limit: 8 })
    getToolActivityMock.mockResolvedValue({ items: [toolActivity], total: 1, limit: 5 })
    getToolsMock.mockResolvedValue([tool])
  })

  afterEach(() => vi.clearAllMocks())

  it('renders real recent runs, evaluations, tools, agents, and cross-links', async () => {
    renderPage()

    expect(await screen.findByRole('link', { name: 'req-dashboard-1' })).toHaveAttribute('href', '/runs/req-dashboard-1')
    expect(screen.getByRole('link', { name: /baseline eval-aaa111/i })).toHaveAttribute('href', '/evaluations/eval-aaa111')
    expect(screen.getAllByRole('link', { name: 'Logical' }).every((link) => link.getAttribute('href') === '/agents/logical')).toBe(true)
    expect(screen.getByRole('link', { name: /fetch/i })).toHaveAttribute('href', '/tools')
    expect(screen.getByRole('link', { name: /run req-dashbo/i })).toHaveAttribute('href', '/runs/req-dashboard-1')
    expect(screen.getByRole('link', { name: 'Open Playground' })).toHaveAttribute('href', '/playground')
    expect(getRunSummariesMock).toHaveBeenCalledWith(8)
    expect(getEvaluationsMock).toHaveBeenCalledWith(5)
    expect(getToolActivityMock).toHaveBeenCalledWith(5)
  })

  it('shows honest unavailable token and cost values instead of zeroes', async () => {
    getRunSummariesMock.mockResolvedValue({
      items: [{ ...runSummary, usage: null, cost_usd: null }], total: 1, limit: 8,
    })
    renderPage()

    await waitFor(() => expect(screen.getAllByText('Not reported', { selector: 'p' }).length).toBe(2))
    expect(screen.getAllByText(/not reported/i).length).toBeGreaterThanOrEqual(2)
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument()
  })

  it('labels token and cost subtotals when only some recent runs reported them', async () => {
    getRunSummariesMock.mockResolvedValue({
      items: [runSummary, { ...runSummary, request_id: 'req-dashboard-2', usage: null, cost_usd: null }],
      total: 2,
      limit: 8,
    })
    renderPage()

    expect(await screen.findByText('125', { selector: 'p' })).toBeInTheDocument()
    expect(screen.getAllByText('Reported for 1 of 2 recent runs')).toHaveLength(2)
    expect(screen.getAllByText('$0.002000')).toHaveLength(2)
  })

  it('keeps each section independent when one API source fails', async () => {
    getRunSummariesMock.mockRejectedValueOnce(new NexusApiError(0, {
      code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.',
    }))
    renderPage()

    expect(await screen.findByText(/nexus is unreachable/i)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /baseline eval-aaa111/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /fetch/i })).toBeInTheDocument()
  })

  it('shows an explicit loading state while recent summaries are pending', async () => {
    getRunSummariesMock.mockReturnValueOnce(new Promise(() => {}))
    renderPage()

    await screen.findByRole('link', { name: /fetch/i })
    expect(screen.getByRole('status', { name: 'Loading recent runs' })).toBeInTheDocument()
  })

  it('shows honest empty states and retains responsive single-column layouts', async () => {
    getAgentsMock.mockResolvedValue([])
    getEvaluationsMock.mockResolvedValue({ items: [], total: 0, limit: 5 })
    getRunSummariesMock.mockResolvedValue({ items: [], total: 0, limit: 8 })
    getToolActivityMock.mockResolvedValue({ items: [], total: 0, limit: 5 })
    getToolsMock.mockResolvedValue([])
    renderPage()

    expect(await screen.findByText(/no retained runs in this api process/i)).toBeInTheDocument()
    expect(screen.getByText(/no retained evaluations/i)).toBeInTheDocument()
    expect(screen.getByText(/no retained tool activity/i)).toBeInTheDocument()
    expect(screen.getByText(/no agents are registered/i)).toBeInTheDocument()
    expect(screen.getByText(/no tools are registered/i)).toBeInTheDocument()
    expect(screen.getByRole('region', { name: 'Runtime metrics' })).toHaveClass('grid-cols-1', 'sm:grid-cols-2')
  })

  it('offers retry after a dashboard source recovers', async () => {
    getRunSummariesMock.mockRejectedValueOnce(new NexusApiError(0, {
      code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.',
    }))
    renderPage()
    await screen.findByText(/nexus is unreachable/i)
    getRunSummariesMock.mockResolvedValueOnce({ items: [runSummary], total: 1, limit: 8 })

    const user = userEvent.setup()
    const retry = screen.getByRole('button', { name: 'Retry' })
    await user.click(retry)
    await waitFor(() => expect(getRunSummariesMock).toHaveBeenCalledTimes(2))
    expect(await screen.findAllByRole('link', { name: /req-dashboard-1/i })).toHaveLength(2)
  })
})
