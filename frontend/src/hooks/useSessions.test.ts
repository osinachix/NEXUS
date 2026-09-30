import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NexusApiError } from '@/types/api'
import { SESSION_SUMMARY_A, SESSION_SUMMARY_B } from '@/test/sessionFixtures'

const { getSessionsMock } = vi.hoisted(() => ({ getSessionsMock: vi.fn() }))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getSessions: getSessionsMock },
}))

const { useSessions } = await import('./useSessions')

describe('useSessions', () => {
  beforeEach(() => {
    getSessionsMock.mockReset()
  })

  it('starts loading and never exposes fake sessions while pending', () => {
    getSessionsMock.mockReturnValue(new Promise(() => {}))
    const { result } = renderHook(() => useSessions())
    expect(result.current.status).toBe('loading')
    expect(result.current.sessions).toEqual([])
  })

  it('exposes the real sessions once the fetch resolves', async () => {
    getSessionsMock.mockResolvedValue({ items: [SESSION_SUMMARY_A, SESSION_SUMMARY_B], limit: 50 })
    const { result } = renderHook(() => useSessions())
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.sessions).toEqual([SESSION_SUMMARY_A, SESSION_SUMMARY_B])
  })

  it('surfaces a NexusApiError and keeps the session list empty on failure', async () => {
    getSessionsMock.mockRejectedValue(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    const { result } = renderHook(() => useSessions())
    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.sessions).toEqual([])
    expect(result.current.error?.code).toBe('NETWORK_ERROR')
  })

  it('refetch re-runs the request and can recover from an error', async () => {
    getSessionsMock.mockRejectedValueOnce(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    getSessionsMock.mockResolvedValueOnce({ items: [SESSION_SUMMARY_A], limit: 50 })
    const { result } = renderHook(() => useSessions())
    await waitFor(() => expect(result.current.status).toBe('error'))

    result.current.refetch()

    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.sessions).toEqual([SESSION_SUMMARY_A])
  })
})
