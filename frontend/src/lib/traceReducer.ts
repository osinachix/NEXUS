/**
 * Translates the raw NexusEvent stream into the human-readable TraceStep
 * model the execution trace UI renders (see the Phase 6.1 spec's "Event
 * grouping" requirement: never render raw JSON events as the primary UI).
 * A pure reducer -- `TraceState, NexusEvent -> TraceState` -- kept free of
 * React so it can be unit-tested directly and reused by both the live SSE
 * path and any future replay/inspection view.
 */

import { agentDisplayName } from '@/types/agent'
import type { NexusEvent } from '@/types/events'
import { EMPTY_TRACE_STATE, type TraceState, type TraceStep, type TraceStepKind } from '@/types/trace'

function agentLabel(node: string | undefined): string {
  if (!node) return 'Agent'
  return `${agentDisplayName(node)} Agent`
}

function findLastRunningIndex(
  steps: TraceStep[],
  kind: TraceStepKind,
  predicate?: (step: TraceStep) => boolean,
): number {
  for (let i = steps.length - 1; i >= 0; i -= 1) {
    const step = steps[i]
    if (step.kind === kind && step.status === 'running' && (!predicate || predicate(step))) {
      return i
    }
  }
  return -1
}

function withUpdatedStep(steps: TraceStep[], index: number, patch: Partial<TraceStep>, event: NexusEvent): TraceStep[] {
  const next = steps.slice()
  const existing = next[index]
  next[index] = { ...existing, ...patch, raw: [...existing.raw, event] }
  return next
}

function pushStep(steps: TraceStep[], step: Omit<TraceStep, 'id' | 'raw'>, event: NexusEvent): TraceStep[] {
  const id = `${step.kind}-${steps.length}`
  return [...steps, { ...step, id, raw: [event] }]
}

export function initialTraceState(): TraceState {
  return EMPTY_TRACE_STATE
}

export function reduceTraceEvent(state: TraceState, event: NexusEvent): TraceState {
  switch (event.event_type) {
    case 'workflow_started':
      return {
        ...state,
        outcome: 'running',
        steps: pushStep(state.steps, { kind: 'workflow', label: 'Workflow', status: 'running', timestamp: event.timestamp }, event),
      }

    case 'classifier_started':
      return {
        ...state,
        steps: pushStep(state.steps, { kind: 'classifier', label: 'Classifier', status: 'running', timestamp: event.timestamp }, event),
      }

    case 'classifier_completed': {
      const index = findLastRunningIndex(state.steps, 'classifier')
      if (index === -1) return state
      return {
        ...state,
        steps: withUpdatedStep(
          state.steps,
          index,
          { status: event.success === false ? 'failed' : 'completed', durationMs: event.duration_ms, timestamp: event.timestamp },
          event,
        ),
      }
    }

    case 'route_selected':
      return {
        ...state,
        route: event.route ?? null,
        steps: pushStep(
          state.steps,
          { kind: 'route', label: `Route: ${event.route ?? 'unknown'}`, status: 'completed', timestamp: event.timestamp },
          event,
        ),
      }

    case 'agent_started':
      return {
        ...state,
        steps: pushStep(
          state.steps,
          { kind: 'agent', label: agentLabel(event.node), status: 'running', timestamp: event.timestamp },
          event,
        ),
      }

    case 'agent_completed': {
      const index = findLastRunningIndex(state.steps, 'agent')
      if (index === -1) return state
      return {
        ...state,
        steps: withUpdatedStep(
          state.steps,
          index,
          { status: event.success === false ? 'failed' : 'completed', durationMs: event.duration_ms, timestamp: event.timestamp },
          event,
        ),
      }
    }

    case 'tool_started':
      return {
        ...state,
        steps: pushStep(
          state.steps,
          { kind: 'tool', label: event.tool ?? 'Tool', status: 'running', timestamp: event.timestamp },
          event,
        ),
      }

    case 'tool_completed': {
      const index = findLastRunningIndex(state.steps, 'tool', (s) => s.label === event.tool)
      if (index === -1) return state
      return {
        ...state,
        steps: withUpdatedStep(
          state.steps,
          index,
          { status: 'completed', durationMs: event.duration_ms, timestamp: event.timestamp },
          event,
        ),
      }
    }

    case 'tool_denied': {
      const index = findLastRunningIndex(state.steps, 'tool', (s) => s.label === event.tool)
      const patch: Partial<TraceStep> = { status: 'denied', detail: event.reason, timestamp: event.timestamp }
      if (index === -1) {
        // Denied before a tool_started was ever recorded (authorization
        // gate runs before the tool_started event -- see main.py's
        // _instrument_tool) -- add the step directly instead of updating.
        return {
          ...state,
          steps: pushStep(
            state.steps,
            { kind: 'tool', label: event.tool ?? 'Tool', status: 'denied', detail: event.reason, timestamp: event.timestamp },
            event,
          ),
        }
      }
      return { ...state, steps: withUpdatedStep(state.steps, index, patch, event) }
    }

    case 'tool_failed': {
      const index = findLastRunningIndex(state.steps, 'tool', (s) => s.label === event.tool)
      if (index === -1) return state
      return {
        ...state,
        steps: withUpdatedStep(
          state.steps,
          index,
          { status: 'failed', detail: event.error_type, durationMs: event.duration_ms, timestamp: event.timestamp },
          event,
        ),
      }
    }

    case 'workflow_completed': {
      const index = findLastRunningIndex(state.steps, 'workflow')
      const steps = index === -1
        ? state.steps
        : withUpdatedStep(state.steps, index, { status: 'completed', durationMs: event.duration_ms, timestamp: event.timestamp }, event)
      return { ...state, steps, outcome: 'completed' }
    }

    case 'workflow_failed': {
      const index = findLastRunningIndex(state.steps, 'workflow')
      const steps = index === -1
        ? state.steps
        : withUpdatedStep(state.steps, index, { status: 'failed', durationMs: event.duration_ms, timestamp: event.timestamp }, event)
      return {
        ...state,
        steps,
        outcome: 'failed',
        failureReason: event.error_type
          ? `The NEXUS runtime could not complete this request (${event.error_type}).`
          : 'The NEXUS runtime could not complete this request.',
      }
    }

    case 'run_completed':
      return {
        ...state,
        runCompleted: {
          request_id: event.request_id,
          thread_id: event.thread_id,
          status: event.status ?? 'unknown',
          success: event.success ?? false,
          route: event.route ?? null,
          reply: event.reply ?? '',
          duration_ms: event.duration_ms ?? 0,
          timestamp: event.timestamp,
        },
      }

    default:
      // Unknown event type (forward-compatibility): keep it out of the
      // step list rather than guessing at a UI representation for it.
      return state
  }
}

export function reduceTraceEvents(events: NexusEvent[]): TraceState {
  return events.reduce(reduceTraceEvent, initialTraceState())
}
