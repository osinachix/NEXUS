import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import { Sidebar } from './Sidebar'

describe('Sidebar', () => {
  it('makes Dashboard the active home route', () => {
    render(<MemoryRouter initialEntries={['/']}><Sidebar collapsed={false} /></MemoryRouter>)

    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: 'Dashboard' })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('link', { name: 'Playground' })).not.toHaveAttribute('aria-current', 'page')
  })

  it('keeps Runs active for Run Detail routes and supports a compact mobile rail', () => {
    const { container } = render(<MemoryRouter initialEntries={['/runs/request-1']}><Sidebar collapsed={false} /></MemoryRouter>)

    expect(screen.getByRole('link', { name: 'Runs' })).toHaveAttribute('aria-current', 'page')
    expect(container.querySelector('nav')).toHaveClass('max-sm:w-14', 'max-sm:px-1.5')
    expect(screen.getByRole('link', { name: 'Tools' })).toBeInTheDocument()
  })
})
