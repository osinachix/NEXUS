import { useState, type KeyboardEvent } from 'react'
import { SendIcon, StopIcon } from '@/components/icons'

interface Props {
  onSubmit: (message: string) => void
  onCancel: () => void
  isRunning: boolean
  disabled: boolean
  disabledReason?: string
}

const MAX_LENGTH = 10_000

/**
 * A deliberately engineering-tool composer, not a consumer chat widget:
 * Enter submits (the common terminal/IDE-prompt convention), Shift+Enter
 * inserts a newline, and the behavior is stated explicitly in the UI
 * rather than left for the user to guess.
 */
export function MessageComposer({ onSubmit, onCancel, isRunning, disabled, disabledReason }: Props) {
  const [value, setValue] = useState('')

  const trimmed = value.trim()
  const canSubmit = !disabled && !isRunning && trimmed.length > 0

  const submit = () => {
    if (!canSubmit) return
    onSubmit(trimmed)
    setValue('')
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      submit()
    }
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-end gap-2 rounded-lg border border-border-default bg-surface-2 p-2 transition-colors focus-within:border-accent">
        <textarea
          aria-label="Message to NEXUS"
          value={value}
          onChange={(event) => setValue(event.target.value.slice(0, MAX_LENGTH))}
          onKeyDown={handleKeyDown}
          disabled={disabled}
          placeholder={disabled ? (disabledReason ?? 'Unavailable') : 'Ask NEXUS something. Enter to send, Shift+Enter for a new line.'}
          rows={3}
          className="min-h-16 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-text-primary placeholder:text-text-muted focus:outline-none disabled:cursor-not-allowed"
        />
        {isRunning ? (
          <button
            type="button"
            onClick={onCancel}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md border border-border-default bg-surface-3 text-text-secondary transition-colors hover:border-status-danger hover:text-status-danger"
            aria-label="Cancel execution"
            title="Cancel execution"
          >
            <StopIcon />
          </button>
        ) : (
          <button
            type="button"
            onClick={submit}
            disabled={!canSubmit}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-accent text-surface-0 transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:bg-surface-3 disabled:text-text-muted"
            aria-label="Send message"
            title="Send (Enter)"
          >
            <SendIcon />
          </button>
        )}
      </div>
      <div className="flex justify-between text-[11px] text-text-muted">
        <span>Enter to send &middot; Shift+Enter for a new line</span>
        <span className={value.length > MAX_LENGTH - 200 ? 'text-status-warning' : undefined}>
          {value.length} / {MAX_LENGTH}
        </span>
      </div>
    </div>
  )
}
