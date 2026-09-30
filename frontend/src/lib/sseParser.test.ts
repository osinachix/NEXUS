import { describe, expect, it } from 'vitest'
import { SseBlockSplitter, parseSseBlock } from './sseParser'

describe('parseSseBlock', () => {
  it('parses a well-formed event block', () => {
    const block = 'event: workflow_started\ndata: {"request_id":"req-1","thread_id":"thread-1","timestamp":"t"}'
    const event = parseSseBlock(block)
    expect(event).toEqual({
      event_type: 'workflow_started',
      request_id: 'req-1',
      thread_id: 'thread-1',
      timestamp: 't',
    })
  })

  it('returns null when the event line is missing', () => {
    expect(parseSseBlock('data: {"a":1}')).toBeNull()
  })

  it('returns null when the data line is missing', () => {
    expect(parseSseBlock('event: workflow_started')).toBeNull()
  })

  it('returns null for malformed JSON in the data line', () => {
    expect(parseSseBlock('event: workflow_started\ndata: {not json}')).toBeNull()
  })

  it('returns null when data parses to a non-object', () => {
    expect(parseSseBlock('event: workflow_started\ndata: 42')).toBeNull()
  })

  it('event_type from the event line always wins over any event_type in data', () => {
    const block = 'event: route_selected\ndata: {"event_type":"something_else","request_id":"r","thread_id":"t","timestamp":"t"}'
    expect(parseSseBlock(block)?.event_type).toBe('route_selected')
  })
})

describe('SseBlockSplitter', () => {
  it('returns a complete block once terminated by a blank line', () => {
    const splitter = new SseBlockSplitter()
    const blocks = splitter.push('event: workflow_started\ndata: {}\n\n')
    expect(blocks).toEqual(['event: workflow_started\ndata: {}'])
  })

  it('holds a partial block until the terminator arrives, even split across chunks', () => {
    const splitter = new SseBlockSplitter()
    expect(splitter.push('event: workflow_st')).toEqual([])
    expect(splitter.push('arted\ndata: {}')).toEqual([])
    expect(splitter.push('\n\n')).toEqual(['event: workflow_started\ndata: {}'])
  })

  it('emits multiple blocks arriving in a single chunk, in order', () => {
    const splitter = new SseBlockSplitter()
    const blocks = splitter.push('event: a\ndata: {}\n\nevent: b\ndata: {}\n\n')
    expect(blocks).toEqual(['event: a\ndata: {}', 'event: b\ndata: {}'])
  })

  it('ignores stray blank blocks', () => {
    const splitter = new SseBlockSplitter()
    expect(splitter.push('\n\nevent: a\ndata: {}\n\n')).toEqual(['event: a\ndata: {}'])
  })
})
