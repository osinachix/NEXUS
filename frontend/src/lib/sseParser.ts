import type { NexusEvent } from '@/types/events'

/**
 * Parses one `event: <type>\ndata: <json>` block (as produced by api.py's
 * `_format_sse`) into a typed NexusEvent. Returns `null` for a malformed
 * block (missing event/data lines, or data that isn't valid JSON) rather
 * than throwing -- a single bad block must not take down the stream
 * (mirrors the backend's own "never crash on a logging/formatting issue"
 * rule; see observability.py).
 */
export function parseSseBlock(rawBlock: string): NexusEvent | null {
  let eventType: string | null = null
  let dataLine: string | null = null

  for (const line of rawBlock.split('\n')) {
    if (line.startsWith('event:')) {
      eventType = line.slice('event:'.length).trim()
    } else if (line.startsWith('data:')) {
      dataLine = line.slice('data:'.length).trim()
    }
  }

  if (eventType === null || dataLine === null) {
    return null
  }

  let parsed: unknown
  try {
    parsed = JSON.parse(dataLine)
  } catch {
    return null
  }

  if (typeof parsed !== 'object' || parsed === null) {
    return null
  }

  return { ...(parsed as Record<string, unknown>), event_type: eventType } as NexusEvent
}

/**
 * Incrementally splits a raw SSE byte stream (already UTF-8 decoded to
 * text) into complete `\n\n`-delimited blocks, carrying any trailing
 * partial block forward. Kept separate from NexusSseClient so it can be
 * unit-tested against arbitrarily-chunked input without a real network
 * stream (fetch may deliver a single SSE block split across multiple
 * `ReadableStream` chunks).
 */
export class SseBlockSplitter {
  private buffer = ''

  push(chunk: string): string[] {
    this.buffer += chunk
    const blocks: string[] = []
    let boundary: number
    while ((boundary = this.buffer.indexOf('\n\n')) !== -1) {
      const block = this.buffer.slice(0, boundary)
      this.buffer = this.buffer.slice(boundary + 2)
      if (block.trim().length > 0) {
        blocks.push(block)
      }
    }
    return blocks
  }
}
