import type { SessionResponse } from '@/types/api'

/** A realistic GET /v1/sessions list item -- messages is null, matching
 * the real backend contract (list results never fetch full content). */
export const SESSION_SUMMARY_A: SessionResponse = {
  thread_id: 'thread-aaa111',
  status: 'active',
  message_count: 4,
  last_message_type: 'coding',
  last_route: 'coding',
  updated_at: '2026-01-01T00:05:00.000Z',
  messages: null,
}

export const SESSION_SUMMARY_B: SessionResponse = {
  thread_id: 'thread-bbb222',
  status: 'active',
  message_count: 2,
  last_message_type: 'math',
  last_route: 'math',
  updated_at: '2026-01-01T00:01:00.000Z',
  messages: null,
}

/** A realistic GET /v1/sessions/{thread_id} detail -- full message history. */
export const SESSION_DETAIL: SessionResponse = {
  thread_id: 'thread-aaa111',
  status: 'active',
  message_count: 4,
  last_message_type: 'coding',
  last_route: 'coding',
  updated_at: '2026-01-01T00:05:00.000Z',
  messages: [
    { role: 'human', content: 'write a function that adds two numbers' },
    { role: 'ai', content: 'def add(a, b):\n    return a + b' },
    { role: 'human', content: 'now subtract' },
    { role: 'ai', content: 'def subtract(a, b):\n    return a - b' },
  ],
}
