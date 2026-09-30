import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NexusApiError } from '@/types/api'
import { SESSION_DETAIL } from '@/test/sessionFixtures'

const { getSessionMock } = vi.hoisted(() => ({ getSessionMock: vi.fn() }))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getSession: getSessionMock },
}))

const { useSession } = await import('./useSession')

describe('useSession', () => {
  beforeEach(() => {
    getSessionMock.mockReset()
  })

  it('is not_found when no threadId is given, without calling the API', () => {
    const { result } = renderHook(() => useSession(undefined))
    expect(result.current.status).toBe('not_found')
    expect(getSessionMock).not.toHaveBeenCalled()
  })

  it('loads and exposes the requested session, including message history', async () => {
    getSessionMock.mockResolvedValue(SESSION_DETAIL)
    const { result } = renderHook(() => useSession('thread-aaa111'))
    expect(result.current.status).toBe('loading')
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.session).toEqual(SESSION_DETAIL)
  })

  it('maps SESSION_NOT_FOUND to a distinct not_found status', async () => {
    getSessionMock.mockRejectedValue(
      new NexusApiError(404, { code: 'SESSION_NOT_FOUND', message: 'No session exists for this thread_id.' }),
    )
    const { result } = renderHook(() => useSession('thread-does-not-exist'))
    await waitFor(() => expect(result.current.status).toBe('not_found'))
    expect(result.current.error).toBeNull()
    expect(result.current.session).toBeNull()
  })

  it('maps other failures to a generic error status', async () => {
    getSessionMock.mockRejectedValue(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    const { result } = renderHook(() => useSession('thread-aaa111'))
    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.error?.code).toBe('NETWORK_ERROR')
  })

  it('refetch re-fetches the same session (Refresh action)', async () => {
    getSessionMock.mockResolvedValue(SESSION_DETAIL)
    const { result } = renderHook(() => useSession('thread-aaa111'))
    await waitFor(() => expect(result.current.status).toBe('ready'))

    result.current.refetch()

    await waitFor(() => expect(getSessionMock).toHaveBeenCalledTimes(2))
  })
})
