import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { Sidebar } from '@/components/Sidebar'
import { NexusApiError } from '@/types/api'
import type { ToolActivityResponse, ToolDefinition } from '@/types/tool'

const { getToolsMock, getToolActivityMock } = vi.hoisted(() => ({
  getToolsMock: vi.fn(),
  getToolActivityMock: vi.fn(),
}))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getTools: getToolsMock, getToolActivity: getToolActivityMock },
}))

const { ToolsPage } = await import('./ToolsPage')

const FETCH_TOOL: ToolDefinition = {
  id: 'fetch',
  name: 'fetch',
  description: 'Fetch a URL over the network and return its content.',
  status: 'active',
  execution_type: 'native',
  allowed_agents: ['logical'],
  controls: ['Revalidates every redirect before following it.', 'Marks fetched content as untrusted data.'],
}

const EMPTY_ACTIVITY: ToolActivityResponse = { items: [], total: 0, limit: 50 }

function renderPage() {
  return render(<MemoryRouter><ToolsPage /></MemoryRouter>)
}

describe('ToolsPage', () => {
  beforeEach(() => {
    getToolsMock.mockReset()
    getToolActivityMock.mockReset()
  })

  it('renders actual tool metadata, policy controls, and activity links', async () => {
    getToolsMock.mockResolvedValue([FETCH_TOOL])
    getToolActivityMock.mockResolvedValue({
      items: [
        { request_id: 'run-complete-123456', tool: 'fetch', event_type: 'tool_completed', agent: 'logical', timestamp: '2026-09-30T10:00:00Z', duration_ms: 120, success: true, reason: null, error_type: null },
        { request_id: 'run-denied-123456', tool: 'fetch', event_type: 'tool_denied', agent: 'logical', timestamp: '2026-09-30T10:01:00Z', duration_ms: 2, success: null, reason: 'PRIVATE_ADDRESS', error_type: null },
        { request_id: 'run-failed-123456', tool: 'fetch', event_type: 'tool_failed', agent: 'logical', timestamp: '2026-09-30T10:02:00Z', duration_ms: 80, success: false, reason: null, error_type: 'TimeoutError' },
      ],
      total: 3,
      limit: 50,
    })

    renderPage()

    expect(await screen.findByRole('heading', { name: 'fetch' })).toBeInTheDocument()
    expect(screen.getByText('Native NEXUS tool')).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'logical' }).every((link) => link.getAttribute('href') === '/agents/logical')).toBe(true)
    expect(screen.getByText(/revalidates every redirect/i)).toBeInTheDocument()
    expect(screen.getByText(/marks fetched content as untrusted/i)).toBeInTheDocument()
    expect(screen.getByText('Recent activity from retained runs')).toBeInTheDocument()
    expect(screen.getByText('Completed')).toBeInTheDocument()
    expect(screen.getByText('Denied')).toBeInTheDocument()
    expect(screen.getByText('Failed')).toBeInTheDocument()
    expect(screen.getByText('PRIVATE_ADDRESS')).toBeInTheDocument()
    expect(screen.getByText('TimeoutError')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /run run-complete/i })).toHaveAttribute('href', '/runs/run-complete-123456')
    expect(screen.getByText(/not a complete audit history/i)).toBeInTheDocument()
  })

  it('shows honest empty registry and activity states', async () => {
    getToolsMock.mockResolvedValue([])
    getToolActivityMock.mockResolvedValue(EMPTY_ACTIVITY)
    renderPage()

    expect(await screen.findByText(/no tools are registered/i)).toBeInTheDocument()
    expect(screen.getByText('No retained activity.')).toBeInTheDocument()
    expect(screen.queryByText(/0 executions/i)).not.toBeInTheDocument()
  })

  it('exposes Tools as an enabled Console navigation link', () => {
    render(<MemoryRouter initialEntries={['/tools']}><Sidebar collapsed={false} /></MemoryRouter>)
    expect(screen.getByRole('link', { name: 'Tools' })).toHaveAttribute('href', '/tools')
  })

  it('shows and clears loading states', async () => {
    let resolveTools: (value: ToolDefinition[]) => void = () => {}
    let resolveActivity: (value: ToolActivityResponse) => void = () => {}
    getToolsMock.mockReturnValue(new Promise<ToolDefinition[]>((resolve) => { resolveTools = resolve }))
    getToolActivityMock.mockReturnValue(new Promise<ToolActivityResponse>((resolve) => { resolveActivity = resolve }))
    renderPage()

    expect(screen.getByLabelText('Loading tools')).toBeInTheDocument()
    expect(screen.getByLabelText('Loading tool activity')).toBeInTheDocument()
    resolveTools([FETCH_TOOL])
    resolveActivity(EMPTY_ACTIVITY)
    expect(await screen.findByRole('heading', { name: 'fetch' })).toBeInTheDocument()
    expect(screen.getByText('No retained activity.')).toBeInTheDocument()
  })

  it('offers retry when the registry API fails', async () => {
    getToolsMock
      .mockRejectedValueOnce(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
      .mockResolvedValue([FETCH_TOOL])
    getToolActivityMock.mockResolvedValue(EMPTY_ACTIVITY)
    renderPage()

    const retry = await screen.findByRole('button', { name: 'Retry' })
    fireEvent.click(retry)
    expect(await screen.findByRole('heading', { name: 'fetch' })).toBeInTheDocument()
  })

  it('can retry activity independently and show a safe API error', async () => {
    getToolsMock.mockResolvedValue([FETCH_TOOL])
    getToolActivityMock
      .mockRejectedValueOnce(new NexusApiError(503, { code: 'INTERNAL_ERROR', message: 'Activity is unavailable.' }))
      .mockResolvedValue(EMPTY_ACTIVITY)
    renderPage()

    expect(await screen.findByText('Activity is unavailable.')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }))
    await waitFor(() => expect(screen.getByText('No retained activity.')).toBeInTheDocument())
  })

  it('renders an unavailable status without inventing additional states', async () => {
    getToolsMock.mockResolvedValue([{ ...FETCH_TOOL, status: 'unavailable' }])
    getToolActivityMock.mockResolvedValue(EMPTY_ACTIVITY)
    renderPage()
    expect(await screen.findByText('Unavailable')).toBeInTheDocument()
  })
})
