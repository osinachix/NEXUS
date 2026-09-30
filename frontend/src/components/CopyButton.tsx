import { useState } from 'react'
import { CheckIcon, CopyIcon } from './icons'

/** A small copy-to-clipboard action for compact identifiers (request/thread
 * ids -- see the Phase 6.3 spec's "Copy / Share" section). Shows a brief
 * confirmation instead of a toast/notification system. */
export function CopyButton({ value, label }: { value: string; label: string }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      // Clipboard access can fail (permissions, insecure context) -- not
      // worth a user-facing error for a convenience action.
    }
  }

  return (
    <button
      type="button"
      onClick={copy}
      aria-label={`Copy ${label}`}
      title={`Copy ${label}`}
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded text-text-muted transition-colors hover:bg-surface-3 hover:text-text-primary"
    >
      {copied ? <CheckIcon className="text-status-success" /> : <CopyIcon />}
    </button>
  )
}
