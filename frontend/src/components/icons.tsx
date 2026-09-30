/** Small hand-rolled icon set (stroke-based, 16px grid) so the project
 * doesn't take on an icon-library dependency for a dozen glyphs (see
 * CLAUDE.md section 26: prefer minimal dependencies). Every icon accepts
 * standard SVG props so callers can set size/color via className. */

import type { SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

const base = {
  width: 16,
  height: 16,
  viewBox: '0 0 16 16',
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round' as const,
  strokeLinejoin: 'round' as const,
}

export function CheckIcon(props: IconProps) {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="M3 8.5l3 3 7-7" />
    </svg>
  )
}

export function CrossIcon(props: IconProps) {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="M4 4l8 8M12 4l-8 8" />
    </svg>
  )
}

export function DotIcon(props: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" fill="currentColor" {...props} aria-hidden="true">
      <circle cx="8" cy="8" r="4" />
    </svg>
  )
}

export function BanIcon(props: IconProps) {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <circle cx="8" cy="8" r="6" />
      <path d="M4.4 4.4l7.2 7.2" />
    </svg>
  )
}

export function SpinnerIcon(props: IconProps) {
  return (
    <svg
      width={16}
      height={16}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      strokeLinecap="round"
      className={`animate-spin ${props.className ?? ''}`}
      {...props}
      aria-hidden="true"
    >
      <path d="M8 2a6 6 0 1 1-6 6" />
    </svg>
  )
}

export function ChevronDownIcon(props: IconProps) {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="M4 6l4 4 4-4" />
    </svg>
  )
}

export function SendIcon(props: IconProps) {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="M2 8l12-5.5L9.5 14l-2-5-5.5-1z" />
    </svg>
  )
}

export function StopIcon(props: IconProps) {
  return (
    <svg width={16} height={16} viewBox="0 0 16 16" fill="currentColor" {...props} aria-hidden="true">
      <rect x="4" y="4" width="8" height="8" rx="1.5" />
    </svg>
  )
}

export function ArrowDownIcon(props: IconProps) {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="M8 2v10M4 8l4 4 4-4" />
    </svg>
  )
}

export function ToolIcon(props: IconProps) {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <path d="M9.5 2.5a3 3 0 0 0-3.9 3.9L2 10l2 2 3.6-3.6a3 3 0 0 0 3.9-3.9l-2 2-1.5-1.5 2-2z" />
    </svg>
  )
}

export function CopyIcon(props: IconProps) {
  return (
    <svg {...base} {...props} aria-hidden="true">
      <rect x="5.5" y="5.5" width="8" height="8" rx="1" />
      <path d="M3.5 10.5h-1a1 1 0 0 1-1-1v-6a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v1" />
    </svg>
  )
}
