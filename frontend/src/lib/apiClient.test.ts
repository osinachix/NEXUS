import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { NexusApiError } from '@/types/api'
import { NexusApiClient } from './apiClient'

function jsonResponse(status: number, body: unknown, headers: Record<string, string> = {}) {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json', ...headers } })
}

describe('NexusApiClient', () => {
  let fetchMock: ReturnType<typeof vi.fn>
  let client: NexusApiClient

  beforeEach(() => {
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
    client = new NexusApiClient({ apiBaseUrl: 'http://api.test', apiToken: null })
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('health() calls GET /health and returns the parsed body', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { status: 'ok', service: 'nexus-api' }))
    const result = await client.health()
    expect(result).toEqual({ status: 'ok', service: 'nexus-api' })
    expect(fetchMock).toHaveBeenCalledWith('http://api.test/health', expect.objectContaining({}))
  })

  it('createSession() POSTs and returns the thread_id', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(201, { thread_id: 'thread-abc' }))
    const result = await client.createSession()
    expect(result.thread_id).toBe('thread-abc')
    const [, init] = fetchMock.mock.calls[0]
    expect(init.method).toBe('POST')
  })

  it('getSession() URL-encodes the thread id', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { thread_id: 'a b', status: 'active', message_count: 0, last_message_type: null, last_route: null, updated_at: null }))
    await client.getSession('a b')
    expect(fetchMock).toHaveBeenCalledWith('http://api.test/v1/sessions/a%20b', expect.anything())
  })

  it('getRun() returns the full RunResponse', async () => {
    const body = {
      request_id: 'req-1',
      thread_id: 'thread-1',
      status: 'completed',
      route: 'math',
      duration_ms: 10,
      success: true,
      created_at: 't',
      message_type: 'math',
      started_at: 't',
      completed_at: 't',
      events: [],
      tool_events: [],
      usage: null,
      cost_usd: null,
      error_type: null,
    }
    fetchMock.mockResolvedValueOnce(jsonResponse(200, body))
    const result = await client.getRun('req-1')
    expect(result).toEqual(body)
  })

  it('loads lightweight run summaries with a bounded limit', async () => {
    const body = { items: [], total: 0, limit: 8 }
    fetchMock.mockResolvedValueOnce(jsonResponse(200, body))
    expect(await client.getRunSummaries(8)).toEqual(body)
    expect(fetchMock).toHaveBeenCalledWith('http://api.test/v1/runs/summary?limit=8', expect.anything())
  })

  it('loads registered tools from the tools endpoint', async () => {
    const body = [{
      id: 'fetch', name: 'fetch', description: 'Fetch a URL.', status: 'active',
      execution_type: 'native', allowed_agents: ['logical'], controls: [],
    }]
    fetchMock.mockResolvedValueOnce(jsonResponse(200, body))
    expect(await client.getTools()).toEqual(body)
    expect(fetchMock).toHaveBeenCalledWith('http://api.test/v1/tools', expect.anything())
  })

  it('loads bounded tool activity using the requested limit', async () => {
    const body = { items: [], total: 0, limit: 20 }
    fetchMock.mockResolvedValueOnce(jsonResponse(200, body))
    expect(await client.getToolActivity(20)).toEqual(body)
    expect(fetchMock).toHaveBeenCalledWith('http://api.test/v1/tools/activity?limit=20', expect.anything())
  })

  it('lists evaluations with a bounded limit query', async () => {
    const body = { items: [], total: 0, limit: 25 }
    fetchMock.mockResolvedValueOnce(jsonResponse(200, body))
    expect(await client.getEvaluations(25)).toEqual(body)
    expect(fetchMock).toHaveBeenCalledWith('http://api.test/v1/evaluations?limit=25', expect.anything())
  })

  it('starts an evaluation through the existing POST endpoint', async () => {
    const body = { evaluation_id: 'eval-1' }
    fetchMock.mockResolvedValueOnce(jsonResponse(201, body))
    await client.runEvaluation()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('http://api.test/v1/evaluations')
    expect(init.method).toBe('POST')
  })

  it('URL-encodes evaluation IDs for detail, results, metrics, and comparison endpoints', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(jsonResponse(200, {})))
    await client.getEvaluation('a b')
    await client.getEvaluationResults('a b')
    await client.getEvaluationMetrics('a b')
    await client.compareEvaluations('a b', 'x/y')
    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual([
      'http://api.test/v1/evaluations/a%20b',
      'http://api.test/v1/evaluations/a%20b/results',
      'http://api.test/v1/evaluations/a%20b/metrics',
      'http://api.test/v1/evaluations/compare/a%20b/x%2Fy',
    ])
  })

  it('URL-encodes run IDs for comparison and posts replay through the run API', async () => {
    fetchMock.mockImplementation(() => Promise.resolve(jsonResponse(200, {})))
    await client.compareRuns('run a', 'run/b')
    await client.replayRun('run a')

    expect(fetchMock.mock.calls.map(([url, init]) => [url, init.method])).toEqual([
      ['http://api.test/v1/runs/compare/run%20a/run%2Fb', undefined],
      ['http://api.test/v1/runs/run%20a/replay', 'POST'],
    ])
  })

  it('attaches an Authorization header when a token is configured', async () => {
    const authedClient = new NexusApiClient({ apiBaseUrl: 'http://api.test', apiToken: 'secret-token' })
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { status: 'ok', service: 'nexus-api' }))
    await authedClient.health()
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers.Authorization).toBe('Bearer secret-token')
  })

  it('sends no Authorization header when no token is configured', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(200, { status: 'ok', service: 'nexus-api' }))
    await client.health()
    const [, init] = fetchMock.mock.calls[0]
    expect(init.headers.Authorization).toBeUndefined()
  })

  it('throws NexusApiError with the safe error body on a 401', async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse(401, { error: { code: 'UNAUTHENTICATED', message: 'Missing Authorization header.' } }))
    await expect(client.createSession()).rejects.toMatchObject({
      status: 401,
      code: 'UNAUTHENTICATED',
      message: 'Missing Authorization header.',
    })
  })

  it('parses Retry-After on a 429', async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse(429, { error: { code: 'RATE_LIMITED', message: 'Rate limit exceeded.' } }, { 'Retry-After': '42' }),
    )
    try {
      await client.createSession()
      expect.unreachable()
    } catch (err) {
      expect(err).toBeInstanceOf(NexusApiError)
      expect((err as NexusApiError).retryAfterSeconds).toBe(42)
    }
  })

  it('falls back to a generic safe message when the error body is not JSON', async () => {
    fetchMock.mockResolvedValueOnce(new Response('<html>Bad Gateway</html>', { status: 502 }))
    await expect(client.createSession()).rejects.toMatchObject({ status: 502, code: 'UNKNOWN_ERROR' })
  })

  it('wraps a network failure as a NETWORK_ERROR NexusApiError', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await expect(client.health()).rejects.toMatchObject({ code: 'NETWORK_ERROR', status: 0 })
  })
})
