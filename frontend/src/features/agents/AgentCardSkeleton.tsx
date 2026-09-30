/** A polished loading placeholder, not fake agent data (see the Phase
 * 6.2 spec's Loading States section: "Do not show fake agent data while
 * the registry is loading"). */
export function AgentCardSkeleton() {
  return (
    <div className="flex flex-col gap-3 rounded-md border border-border-subtle bg-surface-1 p-4" aria-hidden="true">
      <div className="flex items-center justify-between">
        <div className="h-4 w-20 animate-pulse rounded bg-surface-3" />
        <div className="h-3 w-14 animate-pulse rounded bg-surface-3" />
      </div>
      <div className="flex flex-col gap-1.5">
        <div className="h-3 w-full animate-pulse rounded bg-surface-3" />
        <div className="h-3 w-2/3 animate-pulse rounded bg-surface-3" />
      </div>
      <div className="h-3 w-24 animate-pulse rounded bg-surface-3" />
      <div className="mt-1 h-9 w-full animate-pulse rounded-md bg-surface-3" />
    </div>
  )
}
