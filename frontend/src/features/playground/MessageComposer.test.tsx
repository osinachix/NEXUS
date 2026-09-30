import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { MessageComposer } from './MessageComposer'

describe('MessageComposer', () => {
  it('renders a textarea and a send button', () => {
    render(<MessageComposer onSubmit={() => {}} onCancel={() => {}} isRunning={false} disabled={false} />)
    expect(screen.getByLabelText(/message to nexus/i)).toBeInTheDocument()
    expect(screen.getByLabelText(/send message/i)).toBeInTheDocument()
  })

  it('the send button is disabled while the input is empty', () => {
    render(<MessageComposer onSubmit={() => {}} onCancel={() => {}} isRunning={false} disabled={false} />)
    expect(screen.getByLabelText(/send message/i)).toBeDisabled()
  })

  it('typing enables the send button, and clicking it submits the trimmed message', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<MessageComposer onSubmit={onSubmit} onCancel={() => {}} isRunning={false} disabled={false} />)

    await user.type(screen.getByLabelText(/message to nexus/i), '  hello nexus  ')
    const button = screen.getByLabelText(/send message/i)
    expect(button).toBeEnabled()
    await user.click(button)

    expect(onSubmit).toHaveBeenCalledWith('hello nexus')
  })

  it('Enter submits the message', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<MessageComposer onSubmit={onSubmit} onCancel={() => {}} isRunning={false} disabled={false} />)

    await user.type(screen.getByLabelText(/message to nexus/i), 'hello{Enter}')
    expect(onSubmit).toHaveBeenCalledWith('hello')
  })

  it('Shift+Enter inserts a newline instead of submitting', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<MessageComposer onSubmit={onSubmit} onCancel={() => {}} isRunning={false} disabled={false} />)

    const textarea = screen.getByLabelText(/message to nexus/i)
    await user.type(textarea, 'line one{Shift>}{Enter}{/Shift}line two')

    expect(onSubmit).not.toHaveBeenCalled()
    expect(textarea).toHaveValue('line one\nline two')
  })

  it('does not submit whitespace-only input', async () => {
    const onSubmit = vi.fn()
    const user = userEvent.setup()
    render(<MessageComposer onSubmit={onSubmit} onCancel={() => {}} isRunning={false} disabled={false} />)

    await user.type(screen.getByLabelText(/message to nexus/i), '   {Enter}')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('shows a cancel button and calls onCancel while running, instead of send', async () => {
    const onCancel = vi.fn()
    const user = userEvent.setup()
    render(<MessageComposer onSubmit={() => {}} onCancel={onCancel} isRunning={true} disabled={false} />)

    expect(screen.queryByLabelText(/send message/i)).not.toBeInTheDocument()
    const cancelButton = screen.getByLabelText(/cancel execution/i)
    await user.click(cancelButton)
    expect(onCancel).toHaveBeenCalled()
  })

  it('disables the textarea and shows the disabled reason when disabled', () => {
    render(
      <MessageComposer onSubmit={() => {}} onCancel={() => {}} isRunning={false} disabled={true} disabledReason="Creating session..." />,
    )
    const textarea = screen.getByLabelText(/message to nexus/i)
    expect(textarea).toBeDisabled()
    expect(textarea).toHaveAttribute('placeholder', 'Creating session...')
  })
})
