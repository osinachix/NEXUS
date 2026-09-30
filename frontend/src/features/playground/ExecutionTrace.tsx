import { useEffect, useRef } from 'react'
import type { TraceState } from '@/types/trace'
import { TraceStepItem } from './TraceStepItem'

/**
 * The Phase 6.1 centerpiece: renders `trace.steps` as they are produced
 * by the reducer (lib/traceReducer.ts) in response to live SSE events --
 * never a fake trace rendered after the fact from the final response.
 * Auto-scrolls to the newest step as the run progresses.
 */
export function ExecutionTrace({ trace }: { trace: TraceState }) {
  const endRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (trace.outcome === 'running') {
      endRef.current?.scrollIntoView({ block: 'nearest', behavior: 'smooth' })
    }
  }, [trace.steps.length, trace.outcome])

  if (trace.outcome === 'idle') {
    return (
      <div className="flex flex-1 items-center justify-center rounded-md border border-dashed border-border-subtle text-sm text-text-muted">
        Send a message to see the execution trace live.
      </div>
    )
  }

  return (
    <div
      className="scrollbar-thin flex-1 overflow-y-auto rounded-md border border-border-subtle bg-surface-1 p-4"
      aria-live="polite"
      aria-label="Execution trace"
    >
      <ol className="flex flex-col">
        {trace.steps.map((step, index) => (
          <TraceStepItem key={step.id} step={step} isLast={index === trace.steps.length - 1} />
        ))}
      </ol>
      <div ref={endRef} />
    </div>
  )
}
