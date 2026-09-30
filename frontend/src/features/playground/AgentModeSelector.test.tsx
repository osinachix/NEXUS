import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MOCK_AGENTS } from '@/test/agentFixtures'
import type { Agent } from '@/types/agent'
import { AgentModeSelector } from './AgentModeSelector'

describe('AgentModeSelector', () => {
  it('lists Auto Route plus all four reference agents', () => {
    render(<AgentModeSelector mode={{ kind: 'auto' }} onChange={() => {}} agents={MOCK_AGENTS} />)
    expect(screen.getByRole('option', { name: 'Auto Route' })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Direct Agent: Logical/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Direct Agent: Math/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Direct Agent: Coding/ })).toBeInTheDocument()
    expect(screen.getByRole('option', { name: /Direct Agent: Counselor/ })).toBeInTheDocument()
  })

  it('reflects the current mode as the selected value', () => {
    render(<AgentModeSelector mode={{ kind: 'direct', agent: 'math' }} onChange={() => {}} agents={MOCK_AGENTS} />)
    expect(screen.getByLabelText(/execution mode/i)).toHaveValue('math')
  })

  it('calls onChange with {kind: "auto"} when Auto Route is selected', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<AgentModeSelector mode={{ kind: 'direct', agent: 'math' }} onChange={onChange} agents={MOCK_AGENTS} />)

    await user.selectOptions(screen.getByLabelText(/execution mode/i), 'Auto Route')
    expect(onChange).toHaveBeenCalledWith({ kind: 'auto' })
  })

  it('calls onChange with the direct agent when a specific agent is selected', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<AgentModeSelector mode={{ kind: 'auto' }} onChange={onChange} agents={MOCK_AGENTS} />)

    await user.selectOptions(screen.getByLabelText(/execution mode/i), 'logical')
    expect(onChange).toHaveBeenCalledWith({ kind: 'direct', agent: 'logical' })
  })

  it('is disabled while a run is in progress', () => {
    render(<AgentModeSelector mode={{ kind: 'auto' }} onChange={() => {}} agents={MOCK_AGENTS} disabled />)
    expect(screen.getByLabelText(/execution mode/i)).toBeDisabled()
  })

  it('explains that the classifier does not run in direct-agent mode', () => {
    render(<AgentModeSelector mode={{ kind: 'direct', agent: 'coding' }} onChange={() => {}} agents={MOCK_AGENTS} />)
    expect(screen.getByText(/classifier does not run/i)).toBeInTheDocument()
  })

  it('only offers agents that are active and support direct execution', () => {
    const agents: Agent[] = [
      ...MOCK_AGENTS,
      {
        id: 'retired',
        name: 'Retired',
        description: 'No longer available.',
        status: 'unavailable',
        execution_mode: ['auto_route', 'direct'],
        tools: [],
        capabilities: [],
        tags: ['reference'],
        version: '1.0.0',
      },
      {
        id: 'auto-only',
        name: 'AutoOnly',
        description: 'Only reachable via the classifier.',
        status: 'active',
        execution_mode: ['auto_route'],
        tools: [],
        capabilities: [],
        tags: ['reference'],
        version: '1.0.0',
      },
    ]
    render(<AgentModeSelector mode={{ kind: 'auto' }} onChange={() => {}} agents={agents} />)
    expect(screen.queryByRole('option', { name: /Direct Agent: Retired/ })).not.toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /Direct Agent: AutoOnly/ })).not.toBeInTheDocument()
  })
})
