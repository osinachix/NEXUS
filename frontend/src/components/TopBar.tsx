import { RuntimeStatusIndicator } from './RuntimeStatusIndicator'

export function TopBar() {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border-subtle bg-surface-1 px-4">
      <div className="flex items-baseline gap-3">
        <span className="font-mono text-sm font-semibold tracking-wide text-text-primary">NEXUS</span>
        <span className="hidden text-xs text-text-muted sm:inline">
          AI Agent Runtime &amp; Orchestration Platform
        </span>
      </div>
      <RuntimeStatusIndicator />
    </header>
  )
}
