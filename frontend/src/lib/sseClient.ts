/**
 * Dedicated SSE client for the NEXUS Console (Phase 6.1). Every
 * EventSource/fetch-streaming detail lives here -- React components only
 * ever see typed NexusEvent objects via callbacks (see
 * features/playground/usePlaygroundExecution.ts), never a raw stream.
 *
 *     NexusSseClient -> NexusEvent -> React state -> Trace UI
 *
 * Browser `EventSource` cannot be used directly: it only supports GET
 * requests with no custom headers, but this endpoint requires POST (a
 * JSON message body) and, when the backend has authentication enabled, an
 * `Authorization` header (see auth.py). This client instead uses `fetch`
 * with a streamed response body and a hand-rolled parser (sseParser.ts)
 * for the same `text/event-stream` wire format -- a standard, documented
 * technique for POST-based SSE consumption.
 */

import { NexusApiError } from '@/types/api'
import type { MessageRequest } from '@/types/api'
import type { NexusEvent } from '@/types/events'
import { nexusApi, type NexusApiClient } from './apiClient'
import { SseBlockSplitter, parseSseBlock } from './sseParser'

export type SseCloseReason = 'completed' | 'cancelled'

export interface SseHandlers {
  onEvent: (event: NexusEvent) => void
  onError: (error: NexusApiError) => void
  onClose: (reason: SseCloseReason) => void
}

export interface SseHandle {
  /** Aborts the underlying connection. Stops the frontend from consuming
   * further events; does NOT guarantee the backend execution itself is
   * interrupted mid-agent-call (NexusRuntime has no cancellation signal
   * of its own -- see ARCHITECTURE.md "SSE streaming architecture"). */
  cancel: () => void
}

/** If no event arrives for this long, treat the stream as stalled. Purely
 * a frontend UX safeguard -- the backend's own LLM/agent/fetch timeouts
 * (LLM_TIMEOUT_SECONDS / AGENT_TIMEOUT_SECONDS / FETCH_TIMEOUT_SECONDS)
 * are what actually bound execution time; this is intentionally longer
 * than their sum would typically require. */
const INACTIVITY_TIMEOUT_MS = 120_000

export class NexusSseClient {
  private readonly api: NexusApiClient

  constructor(api: NexusApiClient) {
    this.api = api
  }

  stream(threadId: string, body: MessageRequest, handlers: SseHandlers): SseHandle {
    const controller = new AbortController()
    let inactivityTimer: ReturnType<typeof setTimeout> | undefined

    const resetInactivityTimer = () => {
      if (inactivityTimer) clearTimeout(inactivityTimer)
      inactivityTimer = setTimeout(() => {
        controller.abort(new DOMException('NEXUS stream timed out', 'TimeoutError'))
      }, INACTIVITY_TIMEOUT_MS)
    }

    const run = async () => {
      resetInactivityTimer()
      let response: Response
      try {
        response = await fetch(this.api.streamUrl(threadId), {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...this.api.authHeadersForStream(),
          },
          body: JSON.stringify(body),
          signal: controller.signal,
        })
      } catch {
        if (controller.signal.aborted) {
          handlers.onClose('cancelled')
          return
        }
        handlers.onError(
          new NexusApiError(0, {
            code: 'NETWORK_ERROR',
            message: 'Could not reach the NEXUS API. Is the backend running?',
          }),
        )
        return
      }

      if (!response.ok || !response.body) {
        let detail = { code: 'UNKNOWN_ERROR', message: `Stream request failed with status ${response.status}.` }
        try {
          const parsedBody = (await response.json()) as { error?: { code: string; message: string } }
          if (parsedBody.error) detail = parsedBody.error
        } catch {
          // Non-JSON error body (e.g. a proxy) -- keep the generic message.
        }
        const retryAfterHeader = response.headers.get('Retry-After')
        handlers.onError(
          new NexusApiError(
            response.status,
            detail,
            retryAfterHeader ? Number.parseInt(retryAfterHeader, 10) : null,
          ),
        )
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      const splitter = new SseBlockSplitter()

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break
          resetInactivityTimer()
          const chunkText = decoder.decode(value, { stream: true })
          for (const block of splitter.push(chunkText)) {
            const event = parseSseBlock(block)
            // A malformed block is skipped, not fatal -- see sseParser.ts.
            if (event) handlers.onEvent(event)
          }
        }
        handlers.onClose('completed')
      } catch {
        if (controller.signal.aborted) {
          handlers.onClose('cancelled')
          return
        }
        handlers.onError(
          new NexusApiError(0, {
            code: 'STREAM_ERROR',
            message: 'The connection to NEXUS was interrupted before the run finished.',
          }),
        )
      } finally {
        if (inactivityTimer) clearTimeout(inactivityTimer)
      }
    }

    void run()

    return {
      cancel: () => controller.abort(new DOMException('cancelled by user', 'AbortError')),
    }
  }
}

export const nexusSse = new NexusSseClient(nexusApi)
