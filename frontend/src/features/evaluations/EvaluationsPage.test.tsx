import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, useLocation } from 'react-router-dom'
import { NexusApiError } from '@/types/api'
import { EVALUATION_A, EVALUATION_B } from '@/test/evaluationFixtures'

const { getEvaluationsMock, runEvaluationMock, compareEvaluationsMock } = vi.hoisted(() => ({
  getEvaluationsMock: vi.fn(), runEvaluationMock: vi.fn(), compareEvaluationsMock: vi.fn(),
}))
vi.mock('@/lib/apiClient', () => ({ nexusApi: { getEvaluations: getEvaluationsMock, runEvaluation: runEvaluationMock, compareEvaluations: compareEvaluationsMock } }))

const { EvaluationsPage } = await import('./EvaluationsPage')

function Location() { return <output aria-label="Current path">{useLocation().pathname}</output> }
function renderPage() {
  render(<MemoryRouter initialEntries={['/evaluations']}><Location /><EvaluationsPage /></MemoryRouter>)
}

describe('EvaluationsPage', () => {
  beforeEach(() => {
    getEvaluationsMock.mockReset()
    runEvaluationMock.mockReset()
    compareEvaluationsMock.mockReset()
  })

  it('shows a loading state without invented evaluations', () => {
    getEvaluationsMock.mockReturnValue(new Promise(() => {}))
    renderPage()
    expect(screen.getByLabelText('Loading evaluations')).toBeInTheDocument()
    expect(screen.queryByText(EVALUATION_A.evaluation_id)).not.toBeInTheDocument()
  })

  it('renders API summaries and honestly labels unavailable token and cost metrics', async () => {
    getEvaluationsMock.mockResolvedValue({ items: [EVALUATION_A], total: 1, limit: 100 })
    renderPage()
    expect(await screen.findByRole('link', { name: EVALUATION_A.evaluation_id })).toHaveAttribute('href', `/evaluations/${EVALUATION_A.evaluation_id}`)
    expect(screen.getByText('Not reported')).toBeInTheDocument()
    expect(screen.getByText('Not available')).toBeInTheDocument()
    expect(screen.getByText('Completed')).toBeInTheDocument()
  })

  it('renders a useful empty state', async () => {
    getEvaluationsMock.mockResolvedValue({ items: [], total: 0, limit: 100 })
    renderPage()
    expect(await screen.findByText('No evaluations in this runtime')).toBeInTheDocument()
  })

  it('shows API failures with a retry action', async () => {
    getEvaluationsMock.mockRejectedValueOnce(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    getEvaluationsMock.mockResolvedValueOnce({ items: [], total: 0, limit: 100 })
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findByText(/nexus is unreachable/i)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /retry/i }))
    expect(await screen.findByText('No evaluations in this runtime')).toBeInTheDocument()
  })

  it('disables duplicate execution, explains synchronous progress, and navigates to the returned evaluation', async () => {
    let finish!: (summary: typeof EVALUATION_A) => void
    runEvaluationMock.mockReturnValue(new Promise((resolve) => { finish = resolve }))
    getEvaluationsMock.mockResolvedValue({ items: [], total: 0, limit: 100 })
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('No evaluations in this runtime')
    await user.click(screen.getByRole('button', { name: 'Run Evaluation' }))
    expect(await screen.findByText(/runs synchronously/i)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /running evaluation/i })).toBeDisabled()
    finish(EVALUATION_A)
    await waitFor(() => expect(screen.getByLabelText('Current path')).toHaveTextContent('/evaluations/eval-aaa111'))
    expect(getEvaluationsMock).toHaveBeenCalledTimes(2)
  })

  it('renders comparison deltas from the API without assigning a winner', async () => {
    const comparison = {
      evaluation_id_a: EVALUATION_A.evaluation_id, evaluation_id_b: EVALUATION_B.evaluation_id,
      summary_a: EVALUATION_A, summary_b: EVALUATION_B, total_cases_a: 1, total_cases_b: 1,
      passed_cases_delta: -1, routing_accuracy_delta: null, execution_success_rate_delta: 0,
      tool_success_rate_delta: null, latency_p50_delta_ms: 0, latency_p95_delta_ms: 0, latency_p99_delta_ms: 0, total_cost_usd_delta: null,
    }
    getEvaluationsMock.mockResolvedValue({ items: [EVALUATION_A, EVALUATION_B], total: 2, limit: 100 })
    compareEvaluationsMock.mockResolvedValue(comparison)
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('table')
    await user.selectOptions(screen.getByLabelText('Evaluation A'), EVALUATION_A.evaluation_id)
    await user.selectOptions(screen.getByLabelText('Evaluation B'), EVALUATION_B.evaluation_id)
    await user.click(screen.getByRole('button', { name: 'Compare' }))
    expect(await screen.findByText('Delta')).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: 'Evaluation B' })).toBeInTheDocument()
    expect(screen.queryByText(/winner|best|improved/i)).not.toBeInTheDocument()
    expect(compareEvaluationsMock).toHaveBeenCalledWith(EVALUATION_A.evaluation_id, EVALUATION_B.evaluation_id)
  })

  it('shows a safe comparison error', async () => {
    getEvaluationsMock.mockResolvedValue({ items: [EVALUATION_A, EVALUATION_B], total: 2, limit: 100 })
    compareEvaluationsMock.mockRejectedValue(new NexusApiError(404, { code: 'EVALUATION_NOT_FOUND', message: 'Evaluation is not available.' }))
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('table')
    await user.selectOptions(screen.getByLabelText('Evaluation A'), EVALUATION_A.evaluation_id)
    await user.selectOptions(screen.getByLabelText('Evaluation B'), EVALUATION_B.evaluation_id)
    await user.click(screen.getByRole('button', { name: 'Compare' }))
    expect(await screen.findByText('Evaluation is not available.')).toBeInTheDocument()
  })
})
