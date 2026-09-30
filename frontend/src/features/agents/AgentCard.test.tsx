import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { MOCK_AGENTS } from '@/test/agentFixtures'
import { AgentCard } from './AgentCard'

function renderCard(agent = MOCK_AGENTS[0]) {
  render(
    <MemoryRouter>
      <AgentCard agent={agent} />
    </MemoryRouter>,
  )
}

describe('AgentCard', () => {
  it('shows the real name, description, status, and tools from the registry', () => {
    renderCard()
    expect(screen.getByRole('link', { name: 'Logical' })).toBeInTheDocument()
    expect(screen.getByText(/Fact-based reasoning/)).toBeInTheDocument()
    expect(screen.getByText('Active')).toBeInTheDocument()
    expect(screen.getByText('fetch')).toBeInTheDocument()
  })

  it('shows "None" for an agent with no tools', () => {
    renderCard(MOCK_AGENTS[1])
    expect(screen.getByText('None')).toBeInTheDocument()
  })

  it('links the agent name to its detail page', () => {
    renderCard()
    expect(screen.getByRole('link', { name: 'Logical' })).toHaveAttribute('href', '/agents/logical')
  })

  it('links Test Agent into the Playground with the agent preselected', () => {
    renderCard()
    expect(screen.getByRole('link', { name: 'Test Agent' })).toHaveAttribute('href', '/playground?agent=logical')
  })

  it('disables Test Agent for an unavailable agent instead of linking to the Playground', () => {
    renderCard({ ...MOCK_AGENTS[0], status: 'unavailable' })
    expect(screen.getByText('Unavailable')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Test Agent' })).not.toBeInTheDocument()
    expect(screen.getByText('Test Agent')).toHaveAttribute('title', 'This agent is currently unavailable')
  })
})
