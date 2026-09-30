import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NexusApiError } from '@/types/api'
import { MOCK_AGENTS } from '@/test/agentFixtures'

const { getAgentsMock } = vi.hoisted(() => ({ getAgentsMock: vi.fn() }))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getAgents: getAgentsMock },
}))

const { useAgentRegistry } = await import('./useAgentRegistry')

describe('useAgentRegistry', () => {
  beforeEach(() => {
    getAgentsMock.mockReset()
  })

  it('starts loading and never exposes fake agents while pending', () => {
    getAgentsMock.mockReturnValue(new Promise(() => {}))
    const { result } = renderHook(() => useAgentRegistry())
    expect(result.current.status).toBe('loading')
    expect(result.current.agents).toEqual([])
  })

  it('exposes the real registry once the fetch resolves', async () => {
    getAgentsMock.mockResolvedValue(MOCK_AGENTS)
    const { result } = renderHook(() => useAgentRegistry())
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.agents).toEqual(MOCK_AGENTS)
    expect(result.current.error).toBeNull()
  })

  it('surfaces a NexusApiError and keeps the agent list empty on failure', async () => {
    getAgentsMock.mockRejectedValue(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    const { result } = renderHook(() => useAgentRegistry())
    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.agents).toEqual([])
    expect(result.current.error?.code).toBe('NETWORK_ERROR')
  })

  it('refetch re-runs the request and can recover from an error', async () => {
    getAgentsMock.mockRejectedValueOnce(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    getAgentsMock.mockResolvedValueOnce(MOCK_AGENTS)
    const { result } = renderHook(() => useAgentRegistry())
    await waitFor(() => expect(result.current.status).toBe('error'))

    result.current.refetch()

    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.agents).toEqual(MOCK_AGENTS)
    expect(getAgentsMock).toHaveBeenCalledTimes(2)
  })
})
