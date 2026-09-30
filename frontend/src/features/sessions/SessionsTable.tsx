import { Link } from 'react-router-dom'
import { CopyButton } from '@/components/CopyButton'
import { formatTimestamp, truncateId } from '@/lib/formatters'
import type { SessionResponse } from '@/types/api'

const HEADERS = ['Thread ID', 'Messages', 'Last Route', 'Classification', 'Updated']

function SessionRow({ session }: { session: SessionResponse }) {
  return (
    <tr className="border-b border-border-subtle last:border-0 hover:bg-surface-2">
      <td className="px-3 py-2">
        <div className="flex items-center gap-1.5">
          <Link
            to={`/sessions/${encodeURIComponent(session.thread_id)}`}
            className="font-mono text-xs text-accent hover:underline"
            title={session.thread_id}
          >
            {truncateId(session.thread_id, 12)}
          </Link>
          <CopyButton value={session.thread_id} label="thread ID" />
        </div>
      </td>
      <td className="px-3 py-2 text-text-secondary">{session.message_count}</td>
      <td className="px-3 py-2 font-mono text-xs text-text-secondary">{session.last_route ?? '--'}</td>
      <td className="px-3 py-2 font-mono text-xs text-text-secondary">{session.last_message_type ?? '--'}</td>
      <td className="px-3 py-2 whitespace-nowrap text-text-secondary">{formatTimestamp(session.updated_at)}</td>
    </tr>
  )
}

export function SessionsTable({ sessions }: { sessions: SessionResponse[] }) {
  return (
    <div className="overflow-x-auto rounded-md border border-border-subtle">
      <table className="w-full min-w-[600px] border-collapse text-left text-sm">
        <thead>
          <tr className="border-b border-border-default bg-surface-1 text-[11px] tracking-wide text-text-muted uppercase">
            {HEADERS.map((header) => (
              <th key={header} className="px-3 py-2 font-medium">
                {header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {sessions.map((session) => (
            <SessionRow key={session.thread_id} session={session} />
          ))}
        </tbody>
      </table>
    </div>
  )
}
