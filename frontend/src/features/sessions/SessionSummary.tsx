import { CopyButton } from '@/components/CopyButton'
import { formatTimestamp, truncateId } from '@/lib/formatters'
import type { SessionResponse } from '@/types/api'

function Field({ label, value, copyValue }: { label: string; value: string; copyValue?: string }) {
  return (
    <div className="flex flex-col gap-0.5">
      <span className="text-[11px] tracking-wide text-text-muted uppercase">{label}</span>
      <div className="flex items-center gap-1.5">
        <span className="font-mono text-sm text-text-primary" title={value}>
          {value}
        </span>
        {copyValue && <CopyButton value={copyValue} label={label} />}
      </div>
    </div>
  )
}

/** The session's metadata summary (Phase 6.4) -- only fields the backend
 * actually returned. There is no separate "created" timestamp: the
 * checkpointer only tracks each thread's latest state, not when it was
 * first touched -- see runtime.py's `list_sessions` docstring; showing a
 * fabricated "created" value here would misrepresent what NEXUS actually
 * persists. */
export function SessionSummary({ session }: { session: SessionResponse }) {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-1 p-4">
      <span className="text-xs font-medium tracking-wide text-text-muted uppercase">Summary</span>
      <div className="grid grid-cols-2 gap-x-4 gap-y-3 sm:grid-cols-4">
        <Field label="Messages" value={String(session.message_count)} />
        <Field label="Last Route" value={session.last_route ?? 'Not reported'} />
        <Field label="Classification" value={session.last_message_type ?? 'Not reported'} />
        <Field label="Updated" value={formatTimestamp(session.updated_at)} />
        <Field label="Thread ID" value={truncateId(session.thread_id, 16)} copyValue={session.thread_id} />
      </div>
    </div>
  )
}
