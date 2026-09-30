import { NavLink } from 'react-router-dom'

interface NavItem {
  label: string
  path?: string
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', path: '/' },
  { label: 'Playground', path: '/playground' },
  { label: 'Agents', path: '/agents' },
  { label: 'Runs', path: '/runs' },
  { label: 'Sessions', path: '/sessions' },
  { label: 'Evaluations', path: '/evaluations' },
  { label: 'Tools', path: '/tools' },
]

export function Sidebar({ collapsed }: { collapsed: boolean }) {
  return (
    <nav
      aria-label="NEXUS Console sections"
      className={`flex shrink-0 flex-col gap-0.5 border-r border-border-subtle bg-surface-1 py-3 transition-[width] duration-150 ${
        collapsed ? 'w-14 items-center px-1.5' : 'w-52 px-2 max-sm:w-14 max-sm:items-center max-sm:px-1.5'
      }`}
    >
      {NAV_ITEMS.map((item) =>
        item.path ? (
          <NavLink
            key={item.label}
            to={item.path}
            end={item.path === '/'}
            aria-label={item.label}
            className={({ isActive }) =>
              `group flex items-center justify-between rounded-md px-2.5 py-2 text-left text-sm transition-colors ${
                isActive ? 'bg-surface-3 font-medium text-text-primary' : 'text-text-secondary hover:bg-surface-2'
              } ${collapsed ? 'w-full justify-center' : 'max-sm:justify-center'}`
            }
          >
            {collapsed ? (
              <span aria-hidden="true" className="text-xs font-semibold uppercase">
                {item.label.slice(0, 2)}
              </span>
            ) : (
              <>
                <span className="max-sm:hidden">{item.label}</span>
                <span aria-hidden="true" className="hidden text-xs font-semibold uppercase max-sm:inline">{item.label.slice(0, 2)}</span>
              </>
            )}
          </NavLink>
        ) : (
          <button
            key={item.label}
            type="button"
            disabled
            aria-disabled="true"
            title={`${item.label} (coming in a later phase)`}
            className={`flex cursor-not-allowed items-center justify-between rounded-md px-2.5 py-2 text-left text-sm text-text-muted hover:bg-transparent ${
              collapsed ? 'w-full justify-center' : 'max-sm:justify-center'
            }`}
          >
            {collapsed ? (
              <span aria-hidden="true" className="text-xs font-semibold uppercase">
                {item.label.slice(0, 2)}
              </span>
            ) : (
              <>
                <span className="max-sm:hidden">{item.label}</span>
                <span aria-hidden="true" className="hidden text-xs font-semibold uppercase max-sm:inline">{item.label.slice(0, 2)}</span>
                <span className="rounded border border-border-default px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-text-muted max-sm:hidden">
                  Soon
                </span>
              </>
            )}
          </button>
        ),
      )}
    </nav>
  )
}
