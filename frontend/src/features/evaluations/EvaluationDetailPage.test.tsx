import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { NexusApiError } from '@/types/api'
import { EVALUATION_A, EVALUATION_RESULT } from '@/test/evaluationFixtures'

const { getEvaluationMock, getEvaluationResultsMock, getEvaluationMetricsMock } = vi.hoisted(() => ({
  getEvaluationMock: vi.fn(), getEvaluationResultsMock: vi.fn(), getEvaluationMetricsMock: vi.fn(),
}))
vi.mock('@/lib/apiClient', () => ({ nexusApi: {
  getEvaluation: getEvaluationMock, getEvaluationResults: getEvaluationResultsMock, getEvaluationMetrics: getEvaluationMetricsMock,
} }))

const { EvaluationDetailPage } = await import('./EvaluationDetailPage')

function renderPage() {
  render(<MemoryRouter initialEntries={['/evaluations/eval-aaa111']}><Routes>
    <Route path="/evaluations/:evaluationId" element={<EvaluationDetailPage />} />
  </Routes></MemoryRouter>)
}

describe('EvaluationDetailPage', () => {
  beforeEach(() => {
    getEvaluationMock.mockReset().mockResolvedValue(EVALUATION_A)
    getEvaluationResultsMock.mockReset().mockResolvedValue([EVALUATION_RESULT])
    getEvaluationMetricsMock.mockReset().mockResolvedValue(EVALUATION_A.metrics)
  })

  it('loads summary, metrics, actual case output and links to the related run', async () => {
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Evaluation' })).toBeInTheDocument()
    expect(screen.getByText('Basic arithmetic')).toBeInTheDocument()
    expect(screen.getByText('The answer is 42.')).toBeInTheDocument()
    expect(screen.getAllByText('Passed').length).toBeGreaterThan(0)
    expect(screen.getByRole('link', { name: /view related run/i })).toHaveAttribute('href', '/runs/req-eval-1')
    expect(getEvaluationMock).toHaveBeenCalledWith(EVALUATION_A.evaluation_id)
    expect(getEvaluationResultsMock).toHaveBeenCalledWith(EVALUATION_A.evaluation_id)
    expect(getEvaluationMetricsMock).toHaveBeenCalledWith(EVALUATION_A.evaluation_id)
  })

  it('shows unavailable metrics without rendering fabricated zeroes', async () => {
    renderPage()
    expect(await screen.findByText('Latency p50')).toBeInTheDocument()
    expect(screen.getAllByText('Not reported').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Not available').length).toBeGreaterThan(0)
    expect(screen.queryByText('$0.00')).not.toBeInTheDocument()
  })

  it('shows safe API errors and supports retry', async () => {
    getEvaluationMock.mockRejectedValueOnce(new NexusApiError(404, { code: 'EVALUATION_NOT_FOUND', message: 'Evaluation is not available.' }))
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findByText('Evaluation is not available.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /retry/i }))
    expect(await screen.findByText('Basic arithmetic')).toBeInTheDocument()
  })
})
