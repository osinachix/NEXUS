import { sessionRoleLabel } from '@/types/session'
import type { SessionMessage } from '@/types/api'

/**
 * Renders a session's message history for inspection, not as a second
 * chatbot surface (the Playground remains the execution surface -- see
 * the Phase 6.4 spec's "Message history" section). Content is untrusted,
 * arbitrary user/model text: rendered as plain text via React's normal
 * text-node escaping only (`{content}`), never `dangerouslySetInnerHTML`
 * and never markdown-parsed -- there is no markdown rendering anywhere in
 * this codebase to reuse, and this phase does not add one (see the spec's
 * "Content safety" section).
 */
export function SessionMessageList({ messages }: { messages: SessionMessage[] }) {
  if (messages.length === 0) {
    return <p className="text-sm text-text-muted">No messages in this session yet.</p>
  }

  return (
    <ol className="flex flex-col gap-3">
      {messages.map((message, index) => (
        // eslint-disable-next-line react/no-array-index-key
        <li key={index} className="flex flex-col gap-1 rounded-md border border-border-subtle bg-surface-2 p-3">
          <span className="text-[11px] font-medium tracking-wide text-text-muted uppercase">
            {sessionRoleLabel(message.role)}
          </span>
          <p className="text-sm leading-relaxed whitespace-pre-wrap text-text-primary">{message.content}</p>
        </li>
      ))}
    </ol>
  )
}
