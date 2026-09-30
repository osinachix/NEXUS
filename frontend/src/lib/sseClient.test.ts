import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { NexusEvent } from '@/types/events'
import { NexusApiClient } from './apiClient'
import { NexusSseClient } from './sseClient'

function sseStreamResponse(chunks: string[], status = 200): Response {
  const encoder = new TextEncoder()
  const stream = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    },
  })
  return new Response(stream, { status, headers: { 'Content-Type': 'text/event-stream' } })
}

function block(eventType: string, data: Record<string, unknown>): string {
  return `event: ${eventType}\ndata: ${JSON.stringify(data)}\n\n`
}

function waitForClose(errors: unknown[], closes: string[]): Promise<void> {
  return new Promise((resolve) => {
    const check = () => {
      if (closes.length > 0 || errors.length > 0) {
        resolve()
      } else {
        setTimeout(check, 5)
      }
    }
    check()
  })
}

describe('NexusSseClient', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  let api: NexusApiClient
  let client: NexusSseClient

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    api = new NexusApiClient({ apiBaseUrl: 'http://api.test', apiToken: null })
    client = new NexusSseClient(api)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('dispatches each event in order as it arrives, ending on workflow_completed/run_completed', async () => {
    fetchMock.mockResolvedValueOnce(
      sseStreamResponse([
        block('workflow_started', { request_id: 'r1', thread_id: 't1', timestamp: 'a' }),
        block('classifier_started', { request_id: 'r1', thread_id: 't1', timestamp: 'a', node: 'classifier' }),
        block('classifier_completed', { request_id: 'r1', thread_id: 't1', timestamp: 'a', success: true }),
        block('route_selected', { request_id: 'r1', thread_id: 't1', timestamp: 'a', route: 'math' }),
        block('agent_started', { request_id: 'r1', thread_id: 't1', timestamp: 'a', node: 'math' }),
        block('tool_started', { request_id: 'r1', thread_id: 't1', timestamp: 'a', tool: 'fetch' }),
        block('tool_completed', { request_id: 'r1', thread_id: 't1', timestamp: 'a', tool: 'fetch', success: true }),
        block('agent_completed', { request_id: 'r1', thread_id: 't1', timestamp: 'a', node: 'math', success: true }),
        block('workflow_completed', { request_id: 'r1', thread_id: 't1', timestamp: 'a', success: true }),
        block('run_completed', { request_id: 'r1', thread_id: 't1', timestamp: 'a', status: 'completed', success: true, reply: 'answer' }),
      ]),
    )

    const events: NexusEvent[] = []
    const closes: string[] = []
    client.stream('t1', { message: 'hi' }, { onEvent: (e) => events.push(e), onError: () => {}, onClose: (r) => closes.push(r) })

    await waitForClose([], closes)

    expect(events.map((e) => e.event_type)).toEqual([
      'workflow_started',
      'classifier_started',
      'classifier_completed',
      'route_selected',
      'agent_started',
      'tool_started',
      'tool_completed',
      'agent_completed',
      'workflow_completed',
      'run_completed',
    ])
    expect(closes).toEqual(['completed'])
  })

  it('delivers workflow_failed and tool_failed events without stopping the stream early', async () => {
    fetchMock.mockResolvedValueOnce(
      sseStreamResponse([
        block('workflow_started', { request_id: 'r1', thread_id: 't1', timestamp: 'a' }),
        block('tool_started', { request_id: 'r1', thread_id: 't1', timestamp: 'a', tool: 'fetch' }),
        block('tool_failed', { request_id: 'r1', thread_id: 't1', timestamp: 'a', tool: 'fetch', error_type: 'ConnectError' }),
        block('workflow_failed', { request_id: 'r1', thread_id: 't1', timestamp: 'a', error_type: 'RuntimeError' }),
      ]),
    )

    const events: NexusEvent[] = []
    const closes: string[] = []
    client.stream('t1', { message: 'hi' }, { onEvent: (e) => events.push(e), onError: () => {}, onClose: (r) => closes.push(r) })

    await waitForClose([], closes)

    expect(events.map((e) => e.event_type)).toContain('tool_failed')
    expect(events.at(-1)?.event_type).toBe('workflow_failed')
  })

  it('skips a malformed block but keeps delivering subsequent valid events', async () => {
    fetchMock.mockResolvedValueOnce(
      sseStreamResponse([
        block('workflow_started', { request_id: 'r1', thread_id: 't1', timestamp: 'a' }),
        'event: broken\ndata: {not valid json}\n\n',
        block('workflow_completed', { request_id: 'r1', thread_id: 't1', timestamp: 'a', success: true }),
      ]),
    )

    const events: NexusEvent[] = []
    const closes: string[] = []
    client.stream('t1', { message: 'hi' }, { onEvent: (e) => events.push(e), onError: () => {}, onClose: (r) => closes.push(r) })

    await waitForClose([], closes)

    expect(events.map((e) => e.event_type)).toEqual(['workflow_started', 'workflow_completed'])
  })

  it('reassembles an event split across multiple stream chunks', async () => {
    fetchMock.mockResolvedValueOnce(
      sseStreamResponse(['event: workflow_st', 'arted\ndata: {"request_id":"r1","thread_id":"t1","timestamp":"a"}\n\n']),
    )

    const events: NexusEvent[] = []
    const closes: string[] = []
    client.stream('t1', { message: 'hi' }, { onEvent: (e) => events.push(e), onError: () => {}, onClose: (r) => closes.push(r) })

    await waitForClose([], closes)
    expect(events).toHaveLength(1)
    expect(events[0].event_type).toBe('workflow_started')
  })

  it('calls onError with a NexusApiError when the initial connection fails', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))

    const errors: unknown[] = []
    client.stream('t1', { message: 'hi' }, { onEvent: () => {}, onError: (e) => errors.push(e), onClose: () => {} })

    await waitForClose(errors, [])
    expect(errors).toHaveLength(1)
    expect((errors[0] as { code: string }).code).toBe('NETWORK_ERROR')
  })

  it('calls onError with the safe error body when the server responds with a non-2xx status', async () => {
    fetchMock.mockResolvedValueOnce(
      new Response(JSON.stringify({ error: { code: 'THREAD_ACCESS_DENIED', message: 'The requested session cannot be accessed.' } }), {
        status: 403,
        headers: { 'Content-Type': 'application/json' },
      }),
    )

    const errors: unknown[] = []
    client.stream('t1', { message: 'hi' }, { onEvent: () => {}, onError: (e) => errors.push(e), onClose: () => {} })

    await waitForClose(errors, [])
    expect((errors[0] as { code: string; status: number }).code).toBe('THREAD_ACCESS_DENIED')
    expect((errors[0] as { code: string; status: number }).status).toBe(403)
  })

  it('cancel() aborts the connection and reports closure as cancelled, not an error', async () => {
    // The first read() resolves with one real chunk (from `start`); the
    // second read() is left pending until aborted (via `pull`, faithfully
    // reproducing how a real in-flight fetch stream read rejects when its
    // AbortController fires), letting the test cancel mid-stream instead
    // of after it has already finished.
    let rejectPendingRead: ((reason: unknown) => void) | undefined
    const stream = new ReadableStream<Uint8Array>({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(block('workflow_started', { request_id: 'r1', thread_id: 't1', timestamp: 'a' })))
      },
      pull() {
        return new Promise((_resolve, reject) => {
          rejectPendingRead = reject
        })
      },
    })

    fetchMock.mockImplementationOnce((_url: string, init: RequestInit) => {
      init.signal?.addEventListener('abort', () => {
        rejectPendingRead?.(new DOMException('aborted', 'AbortError'))
      })
      return Promise.resolve(new Response(stream, { status: 200 }))
    })

    const events: NexusEvent[] = []
    const errors: unknown[] = []
    const closes: string[] = []
    const handle = client.stream(
      't1',
      { message: 'hi' },
      { onEvent: (e) => events.push(e), onError: (e) => errors.push(e), onClose: (r) => closes.push(r) },
    )

    // Let the first event be consumed, then cancel while the second read
    // is pending.
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(events).toHaveLength(1)
    handle.cancel()

    await waitForClose(errors, closes)
    expect(closes).toEqual(['cancelled'])
    expect(errors).toHaveLength(0)
  })
})
