import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { NexusApiError } from '@/types/api'
import type { RunComparisonResponse } from '@/types/api'
import { AUTO_ROUTE_RUN, DIRECT_AGENT_RUN } from '@/test/runFixtures'

const { getRunMock, getRunsMock, compareRunsMock } = vi.hoisted(() => ({
  getRunMock: vi.fn(),
  getRunsMock: vi.fn(),
  compareRunsMock: vi.fn(),
}))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getRun: getRunMock, getRuns: getRunsMock, compareRuns: compareRunsMock },
}))

const { RunComparisonPage } = await import('./RunComparisonPage')

const COMPARISON: RunComparisonResponse = {
  run_a: AUTO_ROUTE_RUN,
  run_b: DIRECT_AGENT_RUN,
  deltas: {
    duration_ms: 70,
    input_tokens: null,
    output_tokens: null,
    total_tokens: null,
    cost_usd: null,
    tool_event_count: 2,
  },
}

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/runs/req-auto-1/compare']}>
      <Routes>
        <Route path="/runs/:requestId/compare" element={<RunComparisonPage />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('RunComparisonPage', () => {
  beforeEach(() => {
    getRunMock.mockReset()
    getRunsMock.mockReset()
    compareRunsMock.mockReset()
    getRunMock.mockResolvedValue(AUTO_ROUTE_RUN)
    getRunsMock.mockResolvedValue({ items: [AUTO_ROUTE_RUN, DIRECT_AGENT_RUN], total: 2, limit: 100 })
  })

  it('selects a second retained run and renders data, traces, and factual deltas', async () => {
    compareRunsMock.mockResolvedValue(COMPARISON)
    const user = userEvent.setup()
    renderPage()

    await screen.findByRole('option', { name: /req-direct-1/ })
    await user.selectOptions(screen.getByRole('combobox', { name: 'Run B' }), DIRECT_AGENT_RUN.request_id)
    await user.click(screen.getByRole('button', { name: 'Compare' }))

    await waitFor(() => expect(compareRunsMock).toHaveBeenCalledWith(AUTO_ROUTE_RUN.request_id, DIRECT_AGENT_RUN.request_id))
    expect(await screen.findByRole('table')).toBeInTheDocument()
    expect(screen.getByText('Run A · req-auto-1')).toBeInTheDocument()
    expect(screen.getByText('Run B · req-direct-1')).toBeInTheDocument()
    expect(screen.getByText('+70 ms')).toBeInTheDocument()
    expect(screen.getAllByText('Not available').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/fetch/).length).toBeGreaterThan(0)
    expect(screen.getAllByLabelText('Execution trace')).toHaveLength(2)
    expect(screen.getAllByRole('link').some((link) => link.getAttribute('href') === '/runs/req-auto-1')).toBe(true)
    expect(screen.getAllByRole('link').some((link) => link.getAttribute('href') === '/runs/req-direct-1')).toBe(true)
  })

  it('does not invent unavailable measurements', async () => {
    compareRunsMock.mockResolvedValue({
      ...COMPARISON,
      run_a: { ...AUTO_ROUTE_RUN, usage: null, cost_usd: null },
      run_b: { ...DIRECT_AGENT_RUN, usage: null, cost_usd: null },
      deltas: { ...COMPARISON.deltas, duration_ms: null, input_tokens: null, output_tokens: null, total_tokens: null, cost_usd: null },
    })
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('option', { name: /req-direct-1/ })
    await user.selectOptions(screen.getByRole('combobox', { name: 'Run B' }), DIRECT_AGENT_RUN.request_id)
    await user.click(screen.getByRole('button', { name: 'Compare' }))

    await waitFor(() => expect(screen.getAllByText('Not reported').length).toBeGreaterThanOrEqual(4))
    expect(screen.getAllByText('Not available').length).toBeGreaterThanOrEqual(4)
  })

  it('shows a safe comparison error', async () => {
    compareRunsMock.mockRejectedValue(new NexusApiError(404, {
      code: 'RUN_NOT_FOUND',
      message: 'A run is not available.',
    }))
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('option', { name: /req-direct-1/ })
    await user.selectOptions(screen.getByRole('combobox', { name: 'Run B' }), DIRECT_AGENT_RUN.request_id)
    await user.click(screen.getByRole('button', { name: 'Compare' }))

    expect(await screen.findByText('A run is not available.')).toBeInTheDocument()
  })
})
