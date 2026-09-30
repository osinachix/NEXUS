import type { RunCompletedInfo } from '@/types/trace'

/**
 * The real reply from run_completed, rendered separately from the
 * execution trace (see the Phase 6.1 spec's "Final response" section) --
 * never fabricated client-side. A plain readable text block rather than a
 * chat bubble, consistent with the developer-console presentation used
 * throughout.
 */
export function FinalResponse({ runCompleted }: { runCompleted: RunCompletedInfo }) {
  return (
    <div className="flex flex-col gap-2 rounded-md border border-border-subtle bg-surface-1 p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-medium tracking-wide text-text-muted uppercase">Agent Response</span>
        {!runCompleted.success && (
          <span className="rounded border border-status-danger px-1.5 py-0.5 text-[10px] text-status-danger uppercase">
            Fallback reply
          </span>
        )}
      </div>
      <p className="text-sm leading-relaxed whitespace-pre-wrap text-text-primary">{runCompleted.reply}</p>
    </div>
  )
}
