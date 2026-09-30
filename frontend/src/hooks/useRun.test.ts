import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NexusApiError } from '@/types/api'
import { AUTO_ROUTE_RUN } from '@/test/runFixtures'

const { getRunMock } = vi.hoisted(() => ({ getRunMock: vi.fn() }))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getRun: getRunMock },
}))

const { useRun } = await import('./useRun')

describe('useRun', () => {
  beforeEach(() => {
    getRunMock.mockReset()
  })

  it('is not_found when no requestId is given, without calling the API', () => {
    const { result } = renderHook(() => useRun(undefined))
    expect(result.current.status).toBe('not_found')
    expect(getRunMock).not.toHaveBeenCalled()
  })

  it('loads and exposes the requested run', async () => {
    getRunMock.mockResolvedValue(AUTO_ROUTE_RUN)
    const { result } = renderHook(() => useRun('req-auto-1'))
    expect(result.current.status).toBe('loading')
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.run).toEqual(AUTO_ROUTE_RUN)
  })

  it('maps RUN_NOT_FOUND to a distinct not_found status', async () => {
    getRunMock.mockRejectedValue(
      new NexusApiError(404, { code: 'RUN_NOT_FOUND', message: 'No run with this request_id is available.' }),
    )
    const { result } = renderHook(() => useRun('req-does-not-exist'))
    await waitFor(() => expect(result.current.status).toBe('not_found'))
    expect(result.current.error).toBeNull()
    expect(result.current.run).toBeNull()
  })

  it('maps other failures to a generic error status', async () => {
    getRunMock.mockRejectedValue(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    const { result } = renderHook(() => useRun('req-auto-1'))
    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.error?.code).toBe('NETWORK_ERROR')
  })
})
