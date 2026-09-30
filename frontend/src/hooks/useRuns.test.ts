import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NexusApiError } from '@/types/api'
import { AUTO_ROUTE_RUN, DIRECT_AGENT_RUN } from '@/test/runFixtures'

const { getRunsMock } = vi.hoisted(() => ({ getRunsMock: vi.fn() }))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getRuns: getRunsMock },
}))

const { useRuns } = await import('./useRuns')

describe('useRuns', () => {
  beforeEach(() => {
    getRunsMock.mockReset()
  })

  it('starts loading and never exposes fake runs while pending', () => {
    getRunsMock.mockReturnValue(new Promise(() => {}))
    const { result } = renderHook(() => useRuns())
    expect(result.current.status).toBe('loading')
    expect(result.current.runs).toEqual([])
  })

  it('exposes the real runs and total once the fetch resolves', async () => {
    getRunsMock.mockResolvedValue({ items: [AUTO_ROUTE_RUN, DIRECT_AGENT_RUN], total: 2, limit: 50 })
    const { result } = renderHook(() => useRuns())
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.runs).toEqual([AUTO_ROUTE_RUN, DIRECT_AGENT_RUN])
    expect(result.current.total).toBe(2)
  })

  it('surfaces a NexusApiError and keeps the run list empty on failure', async () => {
    getRunsMock.mockRejectedValue(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    const { result } = renderHook(() => useRuns())
    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.runs).toEqual([])
    expect(result.current.error?.code).toBe('NETWORK_ERROR')
  })

  it('passes filter params through to the API client', async () => {
    getRunsMock.mockResolvedValue({ items: [], total: 0, limit: 50 })
    renderHook(() => useRuns({ status: 'failed', agent: 'math', limit: 10 }))
    await waitFor(() => expect(getRunsMock).toHaveBeenCalledWith({ status: 'failed', agent: 'math', limit: 10 }))
  })

  it('refetch re-runs the request and can recover from an error', async () => {
    getRunsMock.mockRejectedValueOnce(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    getRunsMock.mockResolvedValueOnce({ items: [AUTO_ROUTE_RUN], total: 1, limit: 50 })
    const { result } = renderHook(() => useRuns())
    await waitFor(() => expect(result.current.status).toBe('error'))

    result.current.refetch()

    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.runs).toEqual([AUTO_ROUTE_RUN])
  })
})
