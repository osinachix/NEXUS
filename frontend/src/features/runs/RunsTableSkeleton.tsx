/** Skeleton rows, not fake runs -- see the Phase 6.3 spec's Loading State
 * section: the loading state must not visually imply that data exists. */
export function RunsTableSkeleton() {
  return (
    <div className="overflow-hidden rounded-md border border-border-subtle" aria-hidden="true">
      <div className="border-b border-border-default bg-surface-1 px-3 py-2">
        <div className="h-3 w-24 animate-pulse rounded bg-surface-3" />
      </div>
      <div className="flex flex-col divide-y divide-border-subtle">
        {Array.from({ length: 6 }).map((_, i) => (
          // eslint-disable-next-line react/no-array-index-key
          <div key={i} className="flex items-center gap-4 px-3 py-3">
            <div className="h-3 w-16 animate-pulse rounded bg-surface-3" />
            <div className="h-3 w-20 animate-pulse rounded bg-surface-3" />
            <div className="h-3 w-16 animate-pulse rounded bg-surface-3" />
            <div className="h-3 flex-1 animate-pulse rounded bg-surface-3" />
            <div className="h-3 w-14 animate-pulse rounded bg-surface-3" />
          </div>
        ))}
      </div>
    </div>
  )
}
