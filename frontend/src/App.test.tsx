import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'

vi.mock('@/features/dashboard/DashboardPage', () => ({
  DashboardPage: () => <h1>Dashboard Home</h1>,
}))

vi.mock('@/components/RuntimeStatusIndicator', () => ({
  RuntimeStatusIndicator: () => <span>Runtime status</span>,
}))

import App from './App'

describe('App routes', () => {
  it('uses Dashboard as the home route', () => {
    render(<MemoryRouter initialEntries={['/']}><App /></MemoryRouter>)

    expect(screen.getByRole('heading', { name: 'Dashboard Home' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
  })

  it('redirects unknown paths home so navigation remains active', () => {
    render(<MemoryRouter initialEntries={['/missing-page']}><App /></MemoryRouter>)

    expect(screen.getByRole('heading', { name: 'Dashboard Home' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
  })
})
