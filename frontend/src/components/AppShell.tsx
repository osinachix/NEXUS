import { useState, type ReactNode } from 'react'
import { Sidebar } from './Sidebar'
import { TopBar } from './TopBar'

export function AppShell({ children }: { children: ReactNode }) {
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <TopBar />
      <div className="flex min-h-0 flex-1">
        <div className="relative flex">
          <Sidebar collapsed={collapsed} />
          <button
            type="button"
            onClick={() => setCollapsed((c) => !c)}
            aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            className="absolute top-3 -right-3 z-10 hidden h-6 w-6 items-center justify-center rounded-full border border-border-default bg-surface-2 text-text-muted transition-colors hover:text-text-primary sm:flex"
          >
            <span aria-hidden="true" className="text-xs">
              {collapsed ? '›' : '‹'}
            </span>
          </button>
        </div>
        <main className="min-w-0 flex-1 overflow-hidden">{children}</main>
      </div>
    </div>
  )
}
