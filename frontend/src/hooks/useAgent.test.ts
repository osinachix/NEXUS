import { renderHook, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { NexusApiError } from '@/types/api'
import { MOCK_AGENTS } from '@/test/agentFixtures'

const { getAgentMock } = vi.hoisted(() => ({ getAgentMock: vi.fn() }))

vi.mock('@/lib/apiClient', () => ({
  nexusApi: { getAgent: getAgentMock },
}))

const { useAgent } = await import('./useAgent')

describe('useAgent', () => {
  beforeEach(() => {
    getAgentMock.mockReset()
  })

  it('is not_found when no agentId is given, without calling the API', () => {
    const { result } = renderHook(() => useAgent(undefined))
    expect(result.current.status).toBe('not_found')
    expect(getAgentMock).not.toHaveBeenCalled()
  })

  it('loads and exposes the requested agent', async () => {
    getAgentMock.mockResolvedValue(MOCK_AGENTS[0])
    const { result } = renderHook(() => useAgent('logical'))
    expect(result.current.status).toBe('loading')
    await waitFor(() => expect(result.current.status).toBe('ready'))
    expect(result.current.agent).toEqual(MOCK_AGENTS[0])
  })

  it('maps AGENT_NOT_FOUND to a distinct not_found status', async () => {
    getAgentMock.mockRejectedValue(new NexusApiError(404, { code: 'AGENT_NOT_FOUND', message: 'No agent with this id is registered.' }))
    const { result } = renderHook(() => useAgent('ghost'))
    await waitFor(() => expect(result.current.status).toBe('not_found'))
    expect(result.current.error).toBeNull()
    expect(result.current.agent).toBeNull()
  })

  it('maps other failures to a generic error status', async () => {
    getAgentMock.mockRejectedValue(new NexusApiError(0, { code: 'NETWORK_ERROR', message: 'Could not reach the NEXUS API.' }))
    const { result } = renderHook(() => useAgent('logical'))
    await waitFor(() => expect(result.current.status).toBe('error'))
    expect(result.current.error?.code).toBe('NETWORK_ERROR')
  })

  it('re-fetches when the agentId changes', async () => {
    getAgentMock.mockResolvedValue(MOCK_AGENTS[1])
    const { result, rerender } = renderHook(({ id }) => useAgent(id), { initialProps: { id: 'math' } })
    await waitFor(() => expect(result.current.status).toBe('ready'))

    getAgentMock.mockResolvedValue(MOCK_AGENTS[2])
    rerender({ id: 'coding' })
    await waitFor(() => expect(result.current.agent?.id).toBe('coding'))
    expect(getAgentMock).toHaveBeenNthCalledWith(2, 'coding')
  })
})
