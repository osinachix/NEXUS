# NEXUS

**AI Agent Runtime & Orchestration Platform**
*Connect. Orchestrate. Execute. Observe.*

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

NEXUS is a LangGraph-based agent runtime that classifies each message you send, routes it to one
of four specialist agents, persists conversation state per thread/session, enforces a
deterministic security policy around tool execution, and emits structured observability events
for every step. It's domain-agnostic - nothing here assumes a particular business or industry.

> **Status: not production-ready - a production-oriented foundation.** This is an incrementally-built
> learning/interview project, with **Phase 6.8 implemented; browser verification is blocked by the local renderer** (see
> [Roadmap](#roadmap) below). It has
> real error handling, bounded retries/timeouts, durable thread-scoped state, structured
> observability, a deterministic tool/network security boundary, a thin FastAPI layer over the
> runtime, a deterministic evaluation framework, real (if minimal) bearer-token authentication,
> authorization enforced against the authenticated caller, a bounded per-principal rate limiter,
> SSE execution streaming, an optional PostgreSQL backend for durable, cross-process checkpoint
> and thread-ownership state, and a growing Console (Agent Playground + live execution trace, an
> API-backed Agent Registry, a Runs/Run Detail history view, a Sessions/state explorer, Evaluations
> history/detail/comparison, and a read-only Tools/governance view backed by the API. It has no
> deterministic replay, long-term/semantic memory, distributed rate limiting, or
> OAuth/SSO/RBAC.
> Development mode (no
> `NEXUS_API_TOKEN` configured) still runs fully unauthenticated by design - don't expose that mode
> to untrusted users or networks. See [Known limitations](#known-limitations).

For a deeper architectural writeup (component diagram, execution identity, persistence model,
observability model), see **[ARCHITECTURE.md](ARCHITECTURE.md)**. For the full security threat
model and every control's implementation/test status, see **[SECURITY.md](SECURITY.md)**.

## Table of contents

- [Roadmap](#roadmap)
- [Overview](#overview)
- [How it works](#how-it-works)
- [MCP as an architectural pattern, and why `fetch` is implemented natively](#mcp-as-an-architectural-pattern-and-why-fetch-is-implemented-natively)
- [Security and tool governance](#security-and-tool-governance)
- [Runtime, threads, and requests](#runtime-threads-and-requests)
- [The NEXUS API](#the-nexus-api)
- [Authentication](#authentication)
- [Authorization](#authorization)
- [Rate limiting](#rate-limiting)
- [Streaming (SSE)](#streaming-sse)
- [Database: SQLite vs. PostgreSQL](#database-sqlite-vs-postgresql)
- [NEXUS Console](#nexus-console)
- [Evaluation](#evaluation)
- [History semantics](#history-semantics)
- [Observability](#observability)
- [Configuration](#configuration)
- [Known limitations](#known-limitations)
- [Prerequisites](#prerequisites)
- [Dependencies](#dependencies)
- [Setup](#setup)
- [Running the project](#running-the-project)
- [Running the API server](#running-the-api-server)
- [Running with PostgreSQL](#running-with-postgresql)
- [Running with Docker](#running-with-docker)
- [Running the Console](#running-the-console)
- [Running an evaluation](#running-an-evaluation)
- [Running the tests](#running-the-tests)
- [Project layout](#project-layout)
- [Troubleshooting](#troubleshooting)
- [Recommended next steps](#recommended-next-steps)
- [License](#license)

## Roadmap

| Phase | Focus | Status |
|---|---|---|
| 0 | Correctness & Hardening | **COMPLETE** |
| 1 | Runtime & Observability | **COMPLETE** |
| 2 | Security & Tool Governance | **COMPLETE** |
| 3 | API Layer | **COMPLETE** |
| 4 | Evaluation & Advanced Observability | **COMPLETE** |
| 5 | Production Runtime & Security | **COMPLETE** |
| 6.1 | NEXUS Console: Agent Playground + Live Execution Trace | **COMPLETE** |
| 6.2 | NEXUS Console: Agent Registry + Test Agent | **COMPLETE** |
| 6.3 | NEXUS Console: Runs + Run Detail | **COMPLETE** |
| 6.4 | NEXUS Console: Sessions + State Explorer | **COMPLETE** |
| 6.5 | NEXUS Console: Evaluations | **COMPLETE** |
| 6.6 | NEXUS Console: Tools / Governance | **IMPLEMENTED; BROWSER VERIFICATION BLOCKED BY LOCAL RENDERER** |
| 6.7 | NEXUS Console: Run Comparison + Re-run | **IMPLEMENTED; AUTOMATED VERIFICATION COMPLETE** |
| 6.8 | NEXUS Console: Dashboard + Console Polish | **IMPLEMENTED; AUTOMATED VERIFICATION COMPLETE** |
| 7 | Production Packaging | **IMPLEMENTED; NOT YET LIVE-VERIFIED (NO DOCKER/POSTGRESQL IN THIS DEV ENVIRONMENT; CI AUTHORED TO VALIDATE BOTH, NOT YET OBSERVED RUNNING)** |

- **Phase 0 - Correctness & Hardening (complete)** - typed state, pinned model, bounded
  retries/timeouts, error handling with safe fallbacks, initial test suite.
- **Phase 1 - Runtime & Observability (complete)** - durable thread-scoped state via a LangGraph
  SQLite checkpointer, a runtime execution model (`runtime.py`) with `request_id`/`thread_id`
  identity, and structured JSON observability across the classifier/router/agents/tools.
- **Phase 2 - Security & Tool Governance (complete)** - a deterministic tool/network
  security boundary: SSRF protection, URL/scheme/credential validation, domain allowlisting,
  streaming response-size limits, per-redirect-hop policy revalidation, tool authorization,
  untrusted-content handling, and a minimal thread-ownership boundary. Full detail in
  [SECURITY.md](SECURITY.md).
- **Phase 3 - API Layer (complete)** - a thin FastAPI service (`api.py`) over
  `NexusRuntime`: session/message/run endpoints, health/readiness, OpenAPI docs, all reusing
  Phase 1/2's execution model and access boundary unchanged. See
  [The NEXUS API](#the-nexus-api).
- **Phase 4 - Evaluation & Advanced Observability (complete)** - a deterministic
  evaluation framework (`evals/`): typed cases/datasets, a runner operating only against
  `NexusRuntime`, routing/execution/tool/response/latency checks, token usage and configurable
  cost tracking, run/evaluation comparison, and a richer `GET /v1/runs/{request_id}`. See
  [Evaluation](#evaluation).
- **Phase 5 - Production Runtime & Security (complete, this revision)** - the architectural
  foundations for real deployment: bearer-token authentication (`auth.py`), authorization checked
  against the authenticated caller for sessions/runs/evaluations (`access.py`), a bounded
  per-principal rate limiter (`rate_limit.py`), Server-Sent Events execution streaming
  (`POST /v1/sessions/{thread_id}/messages/stream`), an optional PostgreSQL backend for durable,
  cross-process checkpoint and thread-ownership state (`runtime.py`, `access.PostgresAccessStore`),
  and DNS-rebinding-resistant `fetch` connections (IP-pinned via a custom httpcore network
  backend). See [Authentication](#authentication), [Authorization](#authorization),
  [Rate limiting](#rate-limiting), [Streaming (SSE)](#streaming-sse),
  [Database: SQLite vs. PostgreSQL](#database-sqlite-vs-postgresql).
- **Phase 6.1 - NEXUS Console: Agent Playground + Live Execution Trace (complete, this revision)** -
  a real TypeScript/React frontend (`frontend/`) that is a pure client of the existing API: a
  runtime status indicator backed by real `/health` polling, Auto Route vs. direct-agent execution
  mode, a message composer, a live execution trace driven entirely by real SSE events, the real
  final response, and real run metadata. Adds one small, justified backend change (direct-agent
  execution + CORS) - see [NEXUS Console](#nexus-console).
- **Phase 6.2 - NEXUS Console: Agent Registry + Test Agent (complete, this revision)** - a backend
  Agent Registry (`agents.py`) exposing each reference agent's public metadata via
  `GET /v1/agents` / `GET /v1/agents/{agent_id}`, now the authoritative allowlist for direct-agent
  execution; a Console Agents page and agent detail view backed entirely by that registry; and a
  "Test Agent" flow that reuses the existing Playground (no second execution surface) with the
  agent preselected via `/playground?agent=<id>`. See [NEXUS Console](#nexus-console).
- **Phase 6.3 - NEXUS Console: Runs + Run Detail (complete, this revision)** - a Runs page and
  Run Detail view built on `GET /v1/runs` (new) and `GET /v1/runs/{request_id}` (extended), showing
  execution history from the same bounded, process-local `RunStore` used since Phase 4. The Run
  Detail execution trace reuses the exact same `ExecutionTrace`/`traceReducer.ts` the Playground's
  live SSE trace already uses - see [NEXUS Console](#nexus-console).
- **Phase 6.4 - NEXUS Console: Sessions + State Explorer (complete, this revision)** - a Sessions
  page and Session Detail view built on a new `GET /v1/sessions` (discovered directly from
  LangGraph checkpoint state via the checkpointer's own `alist`, not a second session database) and
  an extended `GET /v1/sessions/{thread_id}` (now including full message history). Makes the
  RUN (execution history) vs. SESSION (persistent thread/workflow state) distinction explicit
  throughout - see [NEXUS Console](#nexus-console).
- **Phase 6.5 - NEXUS Console: Evaluations (complete, this revision)** - an ownership-filtered
  evaluation history endpoint and Console history, synchronous baseline run, detail, aggregate
  metrics, actual case results, and factual comparison views. History remains bounded and
  process-local; execution uses the existing API and runtime. See [NEXUS Console](#nexus-console).
- **Phase 6.6 - NEXUS Console: Tools / Governance (implemented, this revision)** - a read-only tool
  registry backed by the actual native tool definition and existing agent authorization policy,
  plus ownership-filtered recent activity projected from retained runs. Activity is bounded,
  process-local, and is not a durable or system-wide audit history. Automated tests and production
  build pass; browser verification remains blocked by the local renderer. See
  [NEXUS Console](#nexus-console).
- **Phase 6.7 - NEXUS Console: Run Comparison + Re-run (implemented, this revision)** - factual
  run-to-run B-minus-A comparison plus a guarded re-run of eligible first-turn inputs through
  `NexusRuntime` in a new owned session. The source input stays private in bounded process memory;
  this is not deterministic replay. See [NEXUS Console](#nexus-console).
- **Phase 6.8 - NEXUS Console: Dashboard + Console Polish (implemented, this revision)** - home
  overview assembled from bounded, caller-owned APIs, including a lightweight run-summary endpoint
  that omits full traces and replies. Existing pages gain consistent top-level navigation and
  cross-links. No aggregate analytics service or new persistence was added. See [NEXUS Console](#nexus-console).
- **Remaining Console work** - broader metrics and final visual polish as needed; see
  [Recommended next steps](#recommended-next-steps).
- **Phase 7 - Production Packaging (implemented; not yet live-verified)** - a backend Dockerfile,
  a frontend Dockerfile, a local Compose stack (PostgreSQL + API + Console), and a GitHub Actions
  CI workflow. This development environment has neither Docker nor a local PostgreSQL installation,
  so the image builds, the Compose stack, and live PostgreSQL behavior were authored and statically
  reviewed but not executed or observed here - the CI workflow is written to validate all of it on
  the next push/PR. See [Running with Docker](#running-with-docker) and
  [Known limitations](#known-limitations).

## Overview

NEXUS is a **multi-agent router** built with [LangGraph](https://langchain-ai.github.io/langgraph/):
a graph of nodes where a message flows in, gets classified, and is handed off to whichever
specialist node is best suited to answer it. It demonstrates several ideas together:

1. **Routing**: using an LLM's structured output as a switch to pick the next step in a graph,
   instead of hard-coding logic or asking the user to choose a mode.
2. **A deterministic tool security boundary**: the model may propose a tool call, but a separate,
   testable policy layer - not a prompt - decides whether it actually executes. See
   [Security and tool governance](#security-and-tool-governance).
3. **Durable, thread-scoped execution**: conversation state persists per thread via a LangGraph
   checkpointer, and every execution is identified and traceable end to end.
4. **A thin API over a real runtime, not the other way around**: `api.py` translates HTTP requests
   into calls on the exact same `NexusRuntime` the CLI uses - it never reaches into the LangGraph
   graph directly. See [The NEXUS API](#the-nexus-api).
5. **Evaluation as a first-class citizen, not an afterthought**: the same structured run data the
   API exposes (`run_store.RunRecord`) is what the evaluation framework checks against - routing,
   execution, tool usage, response content, latency, tokens, and cost, all deterministic and
   runnable without a live LLM provider. See [Evaluation](#evaluation).

## How it works

```
START → classifier → router ─┬─ emotional → counselor ─┐
                              ├─ logical   → logical    ├─→ END
                              ├─ math      → math       │
                              └─ coding    → coding    ─┘
```

1. **classifier**: sends the latest user message to Claude with structured output, labeling it
   as `emotional`, `logical`, `math`, or `coding`. This is the only place classification happens.
   If the classifier call fails, it falls back to `message_type = None` rather than raising.
2. **router**: plain Python (no LLM call), maps that label to a `route` - a typed state field
   (`counselor` / `logical` / `math` / `coding`), defaulting to `logical` when `message_type` is
   `None` or unrecognized.
3. One of four specialist agents replies, each with its own system prompt:
   - **counselor**: empathetic, validates feelings, asks reflective questions
   - **logical**: direct, fact-based, no emotional framing; can fetch live web pages via the
     `fetch` tool (see below) when that would make its answer more accurate - the only agent with
     any tool access at all
   - **math**: solves problems step by step and states the final answer
   - **coding**: writes, explains, debugs, or reviews code
4. Every reply ends the graph run (`END`) for that turn. The graph is compiled with a checkpointer
   (see [Runtime, threads, and requests](#runtime-threads-and-requests)), so the *next* turn on the
   same thread resumes from persisted state rather than starting over.

![graph](graph.png)

## MCP as an architectural pattern, and why `fetch` is implemented natively

[MCP (Model Context Protocol)](https://modelcontextprotocol.io/) is an open standard that lets an
LLM application connect to external tools and data sources through a common protocol, instead of
writing a bespoke integration for every tool. NEXUS's agent framework (LangChain's tool-calling
and `create_agent`) is fully compatible with MCP-provided tools, and Phase 0/1 demonstrated this
by connecting to the third-party `mcp-server-fetch` MCP server over stdio. **MCP remains a valid
architectural/tool-integration capability for NEXUS** - a future tool that doesn't need the level
of network control described below could reasonably be MCP-mediated.

**The current `fetch` tool, however, is not MCP-mediated - do not assume it still runs through the
Phase 0/1 MCP server.** As of Phase 2, `fetch` is implemented natively in `tool_policy.py` on top
of `httpx` directly. This was a deliberate choice, not an accident: Phase 2 needed to enforce a
deterministic security policy - SSRF/DNS-IP validation, domain allowlisting, a response-size limit
enforced *while streaming*, and revalidation of *every redirect hop*, not just the initial URL -
and that requires NEXUS to originate and fully control the HTTP request itself. Inspecting
`mcp-server-fetch`'s implementation showed its internal HTTP client follows redirects
automatically with no hook NEXUS could intercept, and downloads the full response body before
NEXUS ever sees it, both inside an opaque subprocess NEXUS doesn't control - wrapping that
subprocess could validate only the initial URL, and could only reject an oversized response after
its bytes were already transferred. Since those are exactly the controls Phase 2 requires to be
real and tested rather than aspirational, `fetch`'s network calls are NEXUS's own, under NEXUS's
own policy. See [SECURITY.md §8](SECURITY.md#8-redirect-handling---implemented) and
[ARCHITECTURE.md](ARCHITECTURE.md) for the full rationale and test coverage.

How the native `fetch` tool is wired, concretely:

- `main.fetch` is a LangChain tool (`@tool`-decorated) whose body calls
  `tool_policy.secure_fetch`, NEXUS's own `httpx`-based fetch implementation.
- Before `fetch` (or any tool) executes, `main._instrument_tool` runs two independent,
  deterministic gates: `tool_policy.check_tool_authorized` (is this agent allowed to use this tool
  at all?) and, inside `secure_fetch`, `tool_policy.check_url` (is this URL - and every redirect
  target it leads to - allowed?). The model proposes a call; it never decides whether it executes.
- Every call, whether allowed, denied, or failed, emits a structured observability event
  (`tool_started` / `tool_completed` / `tool_denied` / `tool_failed`) - see
  [Observability](#observability).
- Fetched content is always returned as structurally-marked untrusted data
  (`{"source": ..., "content": ..., "trust": "untrusted"}`) - see
  [Security and tool governance](#security-and-tool-governance).

The other three agents (counselor, math, coding) have no tool access at all - unchanged since
Phase 0/1.

## Security and tool governance

Phase 2 added a deterministic security boundary around tool execution. Full detail, every
control's IMPLEMENTED/PLANNED status, and its test coverage live in **[SECURITY.md](SECURITY.md)**;
this section states the claims that actually hold, in plain terms:

- **Tool authorization is deterministic.** Which agent may use which tool is a static Python
  mapping (`tool_policy.AGENT_TOOL_POLICY`, currently `{"logical": {"fetch"}}`), checked before a
  tool ever runs. A model proposing a call is never sufficient for it to execute - there is no
  prompt instruction that grants a tool permission it doesn't have in this mapping.
- **URL/network policy is deterministic.** Scheme restrictions, embedded-credential rejection,
  malformed-URL handling, domain allowlisting, and SSRF checks (DNS resolution + IP-range
  validation) are plain Python logic - not something an LLM is asked to self-police. The same
  checks apply to every redirect hop, not just the initial URL.
- **Fetched content is always treated as untrusted.** The `fetch` tool's result is structurally
  marked `"trust": "untrusted"`, and the logical agent's system prompt instructs treating it as
  data to read, never as instructions to follow, regardless of what it claims or asks.
- **Prompt injection is mitigated, not solved.** Structural untrusted-content marking, and the
  fact that policy functions never read tool output (so fetched text cannot alter a policy
  decision), are both implemented and tested. A sufficiently adversarial page influencing the
  model's own reasoning or final answer is a different, harder, unsolved problem NEXUS does not
  claim to have closed - see
  [SECURITY.md §9](SECURITY.md#9-prompt-injection-limitations---partially-mitigated-not-solved).
- **`ThreadAccessRegistry`/`PostgresAccessStore` are ownership bookkeeping, not authentication.**
  `thread_id` is an identifier; *authentication* (verifying a credential) is a separate concern
  handled once, at the API boundary, by `auth.py` - see [Authentication](#authentication).
  `access.py`'s stores track which `principal_id` first touched a thread and reject a different one
  from reusing it, now checked against a real authenticated principal rather than one hardcoded
  constant - see [Authorization](#authorization).
- **DNS-rebinding hardening (Phase 5).** `fetch`'s real network connections are pinned to the exact
  IP address `tool_policy.check_url` already validated, closing the resolve-then-connect TOCTOU
  window Phase 2 documented but didn't fix - see
  [SECURITY.md §3](SECURITY.md#3-ssrf-protection---implemented).

## Runtime, threads, and requests

`runtime.py` defines `NexusRuntime`, an agent-agnostic wrapper around a checkpointer-backed
compiled graph. It owns:

- **`thread_id`** - a conversation/session id. The same thread's LangGraph state (accumulated
  messages, last classification/route) persists across turns *and* across process restarts, via a
  SQLite-backed LangGraph checkpointer (`AsyncSqliteSaver`). Different threads never share state.
- **`request_id`** - generated fresh for every `NexusRuntime.execute()` call (one user turn).
  Nodes never generate their own - they only read it (from `config["configurable"]`) to tag their
  observability events, so every event from one turn is correlatable by this one id.
- **`principal_id`** - who is calling. Defaults to `access.LOCAL_CLI_PRINCIPAL` for the CLI; for the
  API, it's the `principal_id` of the `auth.Principal` that authenticated the request (see
  [Authentication](#authentication)) - a real per-token identity when `NEXUS_API_TOKEN` is
  configured, or the fixed `access.LOCAL_API_PRINCIPAL` in development mode otherwise. Checked
  against an `access.AccessStore` (in-memory or Postgres-backed - see
  [Database: SQLite vs. PostgreSQL](#database-sqlite-vs-postgresql)) before a thread is touched -
  see [Authorization](#authorization).

```python
result = await session.execute(thread_id, "what's 15% of 340?")
# result.request_id, result.thread_id, result.reply, result.duration_ms, result.success
```

The CLI (`main.py: run_chatbot`) and API (`api.py`) are its external callers; the evaluation runner
is an internal caller. Each uses the same `NexusRuntime.execute()` path. The Console remains a
client of the API, not a direct runtime caller - see [The NEXUS API](#the-nexus-api).

See **[ARCHITECTURE.md](ARCHITECTURE.md)** for the full component diagram and execution model.

## The NEXUS API

`api.py` is a thin FastAPI service layer over `NexusRuntime` - it translates HTTP requests into
`execute()`/`get_state()` calls and their results back into HTTP responses. It contains no agent
logic of its own:

```
Client → Authentication → Authorization → Rate limiting → NEXUS API → NexusRuntime → LangGraph → Agents
                                                                     └─ (or) SSE event stream
```

| Method | Path | Auth required | Purpose |
|---|---|---|---|
| POST | `/v1/sessions` | Yes | Create a new session; returns `thread_id`, owned by the calling principal |
| GET | `/v1/sessions` | Yes | List this principal's sessions (Phase 6.4), most recently updated first, discovered directly from checkpoint state - no full message content in list items |
| GET | `/v1/sessions/{thread_id}` | Yes | Session metadata (message count, last route/classification, updated_at) plus the full message history (Phase 6.4: role/content only) |
| POST | `/v1/sessions/{thread_id}/messages` | Yes | Send a message; runs one turn via `NexusRuntime.execute()`. Optional `agent` field (Phase 6.1) runs that specific agent directly, bypassing the classifier/router |
| POST | `/v1/sessions/{thread_id}/messages/stream` | Yes | Same turn (and same optional `agent` field) as above, streamed live via Server-Sent Events - see [Streaming (SSE)](#streaming-sse) |
| GET | `/v1/agents` | Yes | The agent registry (Phase 6.2): all registered agents' public metadata - id, name, description, status, execution modes, tools, capabilities, tags - see [NEXUS Console](#nexus-console) |
| GET | `/v1/agents/{agent_id}` | Yes | A single agent's metadata; 404 `AGENT_NOT_FOUND` if `agent_id` isn't registered at all (distinct from a registered-but-unavailable agent) |
| GET | `/v1/tools` | Yes | Read-only metadata for currently bound tools, including status, native execution type, allowed public agents, and concise enforced controls (Phase 6.6) |
| GET | `/v1/tools/activity` | Yes | Bounded recent completed, denied, and failed tool events from retained runs owned by this principal; process-local, not a durable audit history (Phase 6.6) |
| GET | `/v1/runs` | Yes | List recent executions (Phase 6.3), most recent first, from the same bounded run store - optional `limit`/`status`/`agent`/`route`/`thread_id` (Phase 6.4) filters; only ever returns runs this principal owns |
| GET | `/v1/runs/summary` | Yes | Bounded caller-owned run summaries for overview pages; omits full replies, events, tool details, and thread IDs (Phase 6.8) |
| GET | `/v1/runs/{request_id}` | Yes | Look up a previously-executed turn - status, route, agent (Phase 6.3), classification, timestamps, the final response, structured events, tool activity, token usage, and cost when available (see [Evaluation](#evaluation) and the limitation below) |
| GET | `/v1/runs/compare/{request_id_a}/{request_id_b}` | Yes | Compare two caller-owned runs with factual B-minus-A deltas; unavailable metrics stay unavailable (Phase 6.7) |
| POST | `/v1/runs/{request_id}/replay` | Yes | Re-run an eligible first-turn input through the runtime in a new owned session; never modifies the source thread (Phase 6.7) |
| POST | `/v1/evaluations` | Yes | Synchronously run the checked-in baseline evaluation dataset; returns the summary |
| GET | `/v1/evaluations` | Yes | List lightweight summaries of this principal's recent evaluations (Phase 6.5), newest first, with bounded `limit`; no per-case results |
| GET | `/v1/evaluations/{evaluation_id}` | Yes | An evaluation's summary (pass/fail counts, rates, metrics) - only its owning principal may retrieve it |
| GET | `/v1/evaluations/{evaluation_id}/results` | Yes | An evaluation's full per-case results - ownership-checked |
| GET | `/v1/evaluations/{evaluation_id}/metrics` | Yes | An evaluation's aggregate latency/token/cost metrics - ownership-checked |
| GET | `/v1/evaluations/compare/{evaluation_id_a}/{evaluation_id_b}` | Yes | Measurable deltas between two evaluation runs - both must be owned by the caller |
| GET | `/health` | No | Process liveness - no LLM or checkpointer call |
| GET | `/ready` | No | Checkpointer responsiveness via a cheap probe - no LLM call |

"Auth required" means the endpoint depends on `auth.Principal` resolution (see
[Authentication](#authentication)) and is subject to [rate limiting](#rate-limiting) - in
development mode (no `NEXUS_API_TOKEN` configured) every such request is still auto-authenticated
as a fixed principal, exactly as in Phase 3/4, so nothing here breaks existing unauthenticated
usage by default.

All error responses share one shape: `{"error": {"code": "...", "message": "..."}}` - stable
machine-readable codes (`UNAUTHENTICATED`, `THREAD_ACCESS_DENIED`, `RATE_LIMITED`,
`SESSION_NOT_FOUND`, `RUN_NOT_FOUND`, `EVALUATION_NOT_FOUND`, `DATASET_ERROR`, `INVALID_REQUEST`,
`INTERNAL_ERROR`), never a stack trace, exception text, or secret. Interactive docs are
auto-generated by FastAPI at `/docs` (Swagger UI) and `/openapi.json`.

A message call always returns HTTP 200 with a safe reply - it does not turn a provider/tool
failure into an HTTP-level error, because `NexusRuntime.execute()` already resolves those into a
safe fallback reply (Phase 0 behavior, unchanged). The response's `status` field distinguishes
`"completed"` (a real answer, or a node-level failure already absorbed into a fallback reply) from
`"failed"` (rarer: a failure outside any node's own handling). See
[ARCHITECTURE.md "API layer (Phase 3)"](ARCHITECTURE.md#api-layer-phase-3) for the full
request/response contract, the run registry's bounded-in-process-only limitation, and how HTTP
requests are correlated with NEXUS's existing observability events (not a second logging system).

**Authenticated, authorized access (Phase 5)**: every non-health request resolves a real
`auth.Principal` first - see [Authentication](#authentication) and
[Authorization](#authorization) below.

**Concurrency/persistence**: the API can serve concurrent requests, and different threads stay
isolated exactly as under the CLI. With the SQLite/development backend, the access store and rate
limiter are in-memory/per-process - this is a single-instance local-dev deployment. With the
PostgreSQL backend (`NEXUS_DATABASE_URL` configured), checkpoint state *and* thread ownership are
durable and safe across multiple API instances sharing one database - the rate limiter remains
process-local either way. See [Database: SQLite vs. PostgreSQL](#database-sqlite-vs-postgresql) and
[Known limitations](#known-limitations).

## Authentication

`auth.py` resolves an HTTP `Authorization` header to a `Principal` at the API boundary, before any
route handler runs. `NexusRuntime` and everything below it never see a header or a `Principal`
object - only the resulting plain `principal_id: str`, exactly as in Phase 2-4:

```
HTTP request → auth.authenticate(header, configured_token=...) → Principal
             → NexusRuntime.execute(..., principal_id=principal.principal_id)
```

Two modes, controlled entirely by whether `NEXUS_API_TOKEN` is configured:

- **Token mode** (`NEXUS_API_TOKEN` set): every protected request must send
  `Authorization: Bearer <token>` matching exactly. Missing header, wrong scheme, malformed value,
  or wrong token → `401 UNAUTHENTICATED`. A valid token always resolves to the same
  `principal_id` (a short one-way hash of the token, e.g. `token-a1b2c3...`) - the token itself is
  never logged, never echoed in an error, and never appears in the derived `principal_id`.
- **Development mode** (`NEXUS_API_TOKEN` unset): every request is auto-authenticated as a single,
  fixed principal (`access.LOCAL_API_PRINCIPAL`) - exactly the "no auth" behavior Phase 3/4 already
  had. This is what keeps the existing test suite, the CLI, and any script written against the
  Phase 3/4 API working unchanged with no token configured. It is explicit, not silent: the API
  logs a warning at startup ("authentication DISABLED - running in development mode") whenever this
  mode is active. `config.py` refuses to start at all with `NEXUS_ENVIRONMENT=production` and no
  token configured - production is never silently treated as authenticated.

`/health`, `/ready`, `/docs`, and `/openapi.json` never require authentication (standard for
liveness/readiness probes and API documentation).

## Authorization

Authorization ("is this principal allowed to touch this resource?") is a separate question from
authentication ("who is this principal?"), enforced by `access.py` exactly as in Phase 2-4, now
checked against a real authenticated `principal_id` instead of one hardcoded constant per caller
type:

- A principal can only access **sessions**/**thread state** it created or first touched.
- A principal can only retrieve **runs** (`GET /v1/runs/{request_id}`) belonging to a thread it
  owns - knowing or guessing a `request_id` string is not sufficient.
- A principal can only retrieve **evaluations** (and their results/metrics) it triggered -
  `evals.models.EvaluationRun.owner_principal_id`, set by `api.py`'s `create_evaluation`, is
  checked on every read; a mismatch returns `404` (not `403`), so a caller can't distinguish "not
  yours" from "doesn't exist."

`ThreadAccessRegistry`/`PostgresAccessStore` remain first-touch ownership **bookkeeping**, not a
second authentication system - they never verify a credential themselves; see
[Database: SQLite vs. PostgreSQL](#database-sqlite-vs-postgresql) for which one backs a given
deployment.

## Rate limiting

`rate_limit.py`'s `RateLimiter` is a bounded, in-process, fixed-window request counter keyed by
**authenticated `principal_id`** (not IP address - the caller's identity is already known by the
time this check runs). Configurable via `NEXUS_RATE_LIMIT_REQUESTS` (default 60) and
`NEXUS_RATE_LIMIT_WINDOW_SECONDS` (default 60) - see [Configuration](#configuration). Exceeding the
limit returns `429 RATE_LIMITED` with a `Retry-After` header (seconds until the current window
resets). Tracks at most `NEXUS_RATE_LIMIT_MAX_PRINCIPALS` (default 10000) distinct principals at
once, oldest-touched evicted first, so it cannot grow without bound.

**This is a process-local limiter, not yet a distributed/production one.** A second API instance
(or a restart of this one) has its own independent counters - two instances behind a load balancer
each separately enforce the configured limit per principal, not a shared total. A real
multi-instance deployment would need a shared counter (e.g. Redis- or Postgres-backed), which this
phase deliberately does not add - see [Known limitations](#known-limitations).

## Streaming (SSE)

`POST /v1/sessions/{thread_id}/messages/stream` runs the exact same `NexusRuntime.execute()` turn
as the synchronous `POST /v1/sessions/{thread_id}/messages` endpoint, but streams NEXUS's existing
structured lifecycle events live via [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
as the turn progresses, instead of returning one JSON body at the end:

```
event: workflow_started
data: {"timestamp": "...", "request_id": "req-...", "thread_id": "thread-...", "event_type": "workflow_started"}

event: classifier_started
data: {...}

event: route_selected
data: {"...", "route": "logical", "message_type": "logical"}

event: agent_started
data: {...}

event: tool_started
data: {"...", "tool": "fetch"}

event: tool_completed
data: {"...", "tool": "fetch", "duration_ms": 412.3, "success": true}

event: agent_completed
data: {...}

event: workflow_completed
data: {"...", "duration_ms": 891.2, "success": true}

event: run_completed
data: {"request_id": "req-...", "thread_id": "thread-...", "status": "completed", "success": true, "route": "logical", "reply": "...", "duration_ms": 891.2, "timestamp": "..."}
```

This reuses the exact same event vocabulary described in [Observability](#observability) - not a
second event system - via `observability.stream_events()`, a live-push sibling of
`capture_events()` filtered by `request_id` from the moment the turn starts. The one addition is
the final `run_completed` event, which carries the actual reply (observability events themselves
deliberately never carry message content - this is the same reply text the synchronous endpoint
already returns in its JSON body, not a new content-exposure surface). Every event carries
`request_id`/`thread_id`/`event_type`/`timestamp` for correlation, and the completed run is
recorded into the same bounded `RunStore` the synchronous endpoint uses, so
`GET /v1/runs/{request_id}` works identically for a streamed or non-streamed turn.

**Lifecycle**: normal completion, a node-level failure absorbed into a safe fallback reply, and a
workflow-level failure all surface via the `workflow_completed`/`workflow_failed` event NEXUS
already emits (exactly one of these always occurs). A client disconnecting mid-stream cancels the
still-running execution task server-side - nothing is left running in the background (verified;
see [Tests](#running-the-tests)). The synchronous endpoint is completely independent and continues
to work whether or not streaming is used.

```bash
curl -N -X POST http://127.0.0.1:8000/v1/sessions/thread-.../messages/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $NEXUS_API_TOKEN" \
  -d '{"message":"what is 15% of 480?"}'
```

## Database: SQLite vs. PostgreSQL

Two checkpointer/ownership backends, chosen by whether `NEXUS_DATABASE_URL` is configured:

| | SQLite (default) | PostgreSQL (`NEXUS_DATABASE_URL` set) |
|---|---|---|
| LangGraph checkpoint state | Durable (survives restart), **not** safe across multiple processes | Durable **and** safe across multiple processes sharing one database |
| Thread ownership (`access.py`) | In-memory, process-local (`ThreadAccessRegistry`) | Durable, cross-process (`PostgresAccessStore`) - a small `nexus_thread_owners(thread_id, principal_id, created_at)` table, first-touch claimed atomically via `INSERT ... ON CONFLICT` |
| Intended use | Local development (the default; nothing extra to install or run) | "Production-like" - the backend this project is built to support, not itself a claim of full production readiness |

Both backends implement the exact same `NexusRuntime` interface - `runtime.create_runtime()`
is the only place that changes; no agent logic, API route, or evaluation code is aware of which
backend is active. See [Running with PostgreSQL](#running-with-postgresql) for setup, and
[Known limitations](#known-limitations) for what Postgres does *not* by itself make multi-instance
safe (`RunStore`, `EvaluationStore`, and the rate limiter all remain process-local regardless of
which checkpointer backend is configured).

## NEXUS Console

The **NEXUS Console** is a TypeScript/React frontend (`frontend/`) and a pure client of the API
described above. Its current surfaces are Dashboard, Playground, Agents, Runs, Sessions,
Evaluations, and Tools:

```
NEXUS Console -> NEXUS API -> NexusRuntime -> LangGraph -> Agents / Tools
```

The Console never imports Python, calls LangGraph, or duplicates runtime logic. Its typed HTTP and
SSE clients call the API for health, agents, sessions, runs, evaluations, and tools, including the
existing synchronous evaluation and comparison endpoints. See
[ARCHITECTURE.md](ARCHITECTURE.md#nexus-console-phase-61) for the frontend architecture.

**Pages at a glance** (a plain-language tour before the phase-by-phase detail below):

| Page | Route | What it shows |
|---|---|---|
| Dashboard | `/` | Home overview: recent runs, outcomes, mean duration, token/cost coverage, evaluation summaries, and agent/tool status, all assembled from the bounded APIs below - not a separate analytics service |
| Playground | `/playground` | Send a message to NEXUS interactively - Auto Route (classifier picks the agent) or Direct Agent (pick one of the four yourself) - and watch the live execution trace as it happens over SSE |
| Agents | `/agents` | The agent registry: each of the four reference agents' description, live status, tools, and capabilities, with a "Test Agent" link into the Playground |
| Runs | `/runs` | Searchable/filterable history of completed executions (status, agent, route, timing, tokens, cost); Run Detail replays the full execution trace and supports factual comparison and a guarded fresh re-run |
| Sessions | `/sessions` | Persisted conversation/thread state (distinct from Runs - see [History semantics](#history-semantics)), with the full message history per thread |
| Evaluations | `/evaluations` | Trigger the checked-in deterministic evaluation dataset, then inspect pass/fail rates, per-case results, and factual comparisons between two evaluation runs |
| Tools | `/tools` | Read-only registry of tools bound to agents (currently `fetch`), the controls enforced on them, and recent completed/denied/failed tool activity |

Every page reads real data from the running API - there are no mocked or placeholder values in the
UI; an unavailable metric renders as "Not reported," never a fabricated number.

**What Phase 6.1 delivers - the Agent Playground:**

- **Real runtime status.** A top-bar indicator polls the actual `GET /health` endpoint (checking /
  online / offline / error) - never a hardcoded "Online."
- **Auto Route or a direct agent.** A mode selector chooses either automatic classification-based
  routing (unchanged backend behavior) or one of the four reference agents directly
  (`counselor` / `logical` / `math` / `coding`), bypassing the classifier and router entirely. This
  required one small, tested backend addition - see below.
- **A real session.** `POST /v1/sessions` is called once per Playground load; every message in
  that session reuses the same `thread_id`, exactly like a real integration.
- **A live execution trace.** `POST .../messages/stream` (SSE) is consumed via a dedicated
  streaming client (`frontend/src/lib/sseClient.ts`) and reduced into human-readable trace steps
  (`frontend/src/lib/traceReducer.ts`) as events actually arrive - not rendered after the fact from
  the final response.
- **The real final response and run metadata.** The reply shown is exactly what `run_completed`
  carries; token usage and cost are fetched via `GET /v1/runs/{request_id}` and shown as "Not
  reported" (never invented) when the backend didn't return them.
- **Polished, safe error states** for backend-unreachable, rate-limited, and workflow-failure cases,
  built entirely from the API's existing `{"error": {"code", "message"}}` shape - never a raw stack
  trace.

**The one backend change this phase required** (both found and justified during Phase 6.1's own
"audit before modifying" step, not invented speculatively):

- **Direct-agent execution.** The graph previously had no way to run a specific agent without going
  through the classifier first. `main.py` now also compiles four minimal `START -> agent -> END`
  graphs (`DIRECT_AGENT_GRAPH_BUILDERS`), reusing the exact same node functions as the main graph -
  no agent logic is duplicated. `NexusRuntime.execute(..., agent=...)` and
  `MessageRequest.agent` (both endpoints) are new, additive, optional parameters; omitting `agent`
  is byte-for-byte the same behavior as before. A state field was deliberately *not* used for this
  (see `main.py`'s module docstring on `DIRECT_AGENT_GRAPH_BUILDERS`): since `message_type`/`route`
  are persisted per-thread, using either as a "skip the classifier" signal would leak across turns
  on the same thread.
- **CORS.** A browser (unlike `curl`/`httpx`, which is all the existing test suite ever used)
  enforces cross-origin restrictions - this was a real defect found only by running the actual
  Console against the actual API in an actual browser during Phase 6.1's live verification, not by
  any unit or integration test. `api.py` now allows `http://localhost:5173`/`http://127.0.0.1:5173`
  (the Vite defaults) by default, configurable via `NEXUS_CONSOLE_ORIGINS` - see
  [Configuration](#configuration).

**What Phase 6.2 adds - the Agent Registry:**

```
Agent Registry (agents.py) -> NEXUS API -> NEXUS Console -> Playground -> NexusRuntime
```

Agents are now first-class, API-discoverable platform resources instead of a list hardcoded into
the frontend:

- **`agents.py`** turns the four reference agents NEXUS already implements into a typed
  `AgentDefinition` (id, name, description, status, execution modes, tools, capabilities, tags,
  version) exposed via `GET /v1/agents` / `GET /v1/agents/{agent_id}` - both authenticated and
  rate-limited exactly like every other endpoint. Deliberately excluded: system prompts,
  model/provider configuration, API keys, and any other internal implementation detail (see
  [SECURITY.md](SECURITY.md)). `status` reflects real backend state - `logical` is `"active"` only
  once `main.logical_react_agent` is actually constructed - never hardcoded.
- **The registry is the authoritative allowlist for direct-agent execution.** `MessageRequest.agent`
  is validated against `agents.is_executable()` before a turn ever reaches graph construction, so an
  unknown or unavailable agent id is rejected with `400 INVALID_REQUEST` - it can never reach
  `NexusRuntime.execute()`.
- **An Agents page (`/agents`)** in the Console lists the real registry as cards - name,
  description, live status, tools - and an agent detail view (`/agents/:agentId`) shows
  capabilities, tools, and supported execution modes.
- **A "Test Agent" flow**, not a second execution surface: clicking "Test Agent" navigates to the
  *existing* Playground with the agent preselected (`/playground?agent=<id>`). The Playground's
  execution-mode selector is now populated from `GET /v1/agents` instead of a hardcoded list, and an
  unknown/unavailable `?agent=` id falls back to Auto Route with a clear, visible notice rather than
  a silent failure or a fabricated agent.

No agent database, no dynamic agent installation, no marketplace, and no user-created agents - the
registry is static, hand-authored metadata describing agents that already exist in `main.py`.

**What Phase 6.3 adds - Runs + Run Detail:**

```
Execute -> Observe live -> Complete -> Browse historical run -> Inspect full execution trace
```

Completed executions are now first-class observability objects in the Console, built entirely from
data the backend already recorded - no second execution system, no new database:

- **`GET /v1/runs`** (new) lists runs from the same bounded, in-process `RunStore` the Playground's
  run metadata panel already reads, most recent first, with optional `limit`/`status`/`agent`/`route`
  filters. Every run is ownership-checked before being included - a caller can never discover
  another principal's runs, including their existence, through this endpoint. See
  `NexusRuntime.owner_of()`, a read-only lookup added specifically so this check never has
  `verify_access`'s first-touch claiming side effect.
- **`GET /v1/runs/{request_id}`** gained two additive fields: `response` (the run's final reply -
  previously only returned by the synchronous message endpoint) and `agent` (which specialist
  actually ran, populated for both Auto Route and Direct Agent turns, unlike `route`, which stays
  null for a direct-agent run).
- **A Runs page (`/runs`)** renders this as a dense, scannable table - status, agent, route, request
  ID (copyable), time, duration, tokens, cost - with status/agent filtering, a client-side search
  over request/thread ID, and a newest/oldest sort toggle. Unavailable values (`route`, tokens, cost)
  render as `--`, never a fake zero.
- **A Run Detail page (`/runs/:requestId`)** shows the full record: a metadata summary, and the
  execution trace. The trace is rendered by the exact same `ExecutionTrace`/`traceReducer.ts` the
  Playground's live SSE trace already uses - `lib/runToTrace.ts` only reshapes a stored
  `RunResponse`'s events into the same `NexusEvent[]` shape SSE produces (plus one synthesized
  `run_completed` event, mirroring what `api.py`'s SSE endpoint already does), then folds them
  through the same reducer. A historical Direct Agent run's trace correctly shows no
  classifier/route step, exactly like the live one, because those events were never recorded for it.
  An unknown or evicted `request_id` shows a polished "Run not found" state, not a blank page.

**The bounded, process-local `RunStore` remains exactly what it was in Phase 4** - this phase adds a
list view and richer detail on top of it, not a database. A backend restart clears run history; the
Runs page reflects that honestly rather than implying durable history. See
[Known limitations](#known-limitations).

**What Phase 6.4 adds - Sessions + State Explorer:**

A **RUN** is what happened during one execution (Phase 6.3's Runs page). A **SESSION** is the
persistent conversational/workflow state associated with a thread - state, not memory (see
CLAUDE.md's "State vs Memory" distinction: state is what the active workflow needs, memory is
information deliberately retained for future interactions). This phase does not blur that line,
and does not add any form of long-term/semantic memory - it only exposes state NEXUS already
durably persists via the LangGraph checkpointer.

- **`GET /v1/sessions`** (new) lists this principal's sessions, most recently updated first,
  discovered directly from the checkpointer's own native listing (`alist`) - not a second
  persistence layer, not a duplicated index. One user turn writes several checkpoints (one per
  graph step, not one per turn), so discovering distinct sessions means scanning a bounded window
  of raw checkpoint entries (`NEXUS_SESSION_SCAN_LIMIT`, default 2000) and keeping each thread's
  first (= newest) entry; a session outside that window simply won't appear - the same honest,
  bounded-store framing as `RunStore`. List items never include full message content.
- **`GET /v1/sessions/{thread_id}`** gained an additive `messages` field: the full message history
  (role/content only, oldest first) for that thread. Previously this endpoint reported only a
  message *count*; the underlying data was already persisted, just not exposed.
- **Ownership works exactly like Runs**: sessions are discovered via the checkpointer, then
  filtered through the same read-only `NexusRuntime.owner_of()` Phase 6.3 added - a session whose
  thread isn't owned by the caller is simply excluded from the list, never surfaced as a 403 or any
  other signal that it exists. Direct access (`GET /v1/sessions/{thread_id}`) keeps its existing,
  pre-Phase-6.4 403 behavior unchanged.
- **A Sessions page (`/sessions`)** renders a dense table (thread ID, message count, last route,
  classification, updated) with client-side search (thread ID/route/classification, never message
  content) and a newest/oldest sort. **A Session Detail page (`/sessions/:threadId`)** shows a
  metadata summary and the message history, rendered as plain text - never HTML-interpreted, never
  markdown-parsed (there is no markdown renderer anywhere in this codebase, and this phase does not
  add one).
- **Cross-navigation, without duplicating anything**: Run Detail links "View Session" to its
  thread's Session Detail; Session Detail links "View Runs" to `/runs?thread_id=<id>` (a new,
  simple server-side filter added to the existing `GET /v1/runs`); the Playground links "View
  Session" once a turn has actually completed (not merely once a session exists, since session
  creation alone writes no checkpoint yet). None of these introduce a second execution surface -
  the Playground remains the only place a turn is actually sent.

**What Phase 6.5 adds - Evaluations:**

- **Ownership-filtered evaluation history.** `GET /v1/evaluations?limit=50` returns bounded,
  newest-first summary data for evaluations owned by the authenticated principal. It does not
  include per-case results. The endpoint uses the existing process-local `EvaluationStore`, capped
  by `NEXUS_EVALUATION_STORE_SIZE` (default 100), and history clears on API restart or eviction.
- **Synchronous baseline execution.** The Console's Run Evaluation action calls the existing
  `POST /v1/evaluations`. It stays disabled while the request runs, explains that the request is
  synchronous, and navigates to the returned evaluation after completion. The API does not stream
  per-case progress.
- **Evaluation detail.** `/evaluations/:evaluationId` reads the existing summary, results, and
  metrics endpoints. It presents the actual returned case responses and dimension pass/fail checks,
  and links each result to its `request_id` in Run Detail.
- **Factual comparison.** The history page compares two stored evaluations through the existing
  compare API and displays the returned deltas without ranking or selecting a winner.
- **Unavailable metrics stay unavailable.** Missing token or cost data is displayed as not
  reported/not available; the Console does not estimate usage or cost. The visible response is the
  actual returned evaluation result, rendered as escaped plain text.

**What Phase 6.6 adds - Tools / Governance:**

- `GET /v1/tools` exposes safe metadata for tools bound to agent graphs. The current `fetch` tool
  identity comes from its actual definition, allowed agents come from `tool_policy.AGENT_TOOL_POLICY`,
  and its status means registered and callable through a supported agent graph.
- `GET /v1/tools/activity` returns completed, denied, and failed tool events from retained runs
  owned by the caller. Events are associated with the parent run's agent and include the run ID for
  navigation, without exposing arguments, results, responses, or thread IDs.
- `/tools` is a read-only operational view with links to Agent Detail and Run Detail. It describes
  enforced fetch controls but does not edit policy or execute tools.
- Activity is bounded and process-local. It resets on API restart and is not a durable, complete,
  or system-wide audit history. The Console does not provide RBAC, policy editing, or dynamic tool
  registration.

**What Phase 6.8 adds - Dashboard + Console Polish:**

- `/` is the top-level Dashboard and the unknown-route fallback. The sidebar presents Dashboard,
  Playground, Agents, Runs, Sessions, Evaluations, and Tools as the available Console surfaces.
- The Dashboard combines bounded summaries from the existing Runs, Evaluations, Agents, Tools,
  and tool-activity APIs. Each section loads, errors, and empties independently. The overview shows
  retained runs, recent outcomes, observed mean duration, reported token/cost coverage, evaluations,
  active agents/tools, recent records, and safe tool activity.
- `GET /v1/runs/summary` provides the Dashboard's bounded run list without final replies, traces,
  tool event details, or thread IDs. It uses the existing authentication, rate-limit, and run-owner
  checks. Run history remains process-local and bounded.
- Metric values are derived only from returned records. Missing token/cost measurements stay
  unavailable; partial totals state how many recent runs reported a value. No durable analytics,
  new database, or background pipeline was added.
- The navigation rail collapses to an accessible compact form on narrow screens. Dashboard cards
  and activity rows stack on mobile; detailed Run Comparison retains its existing horizontal table
  scrolling where its full columns need more width.
- Verification: backend **427 passed, 4 skipped**; frontend **202 passed across 30 test files**;
  production frontend build succeeded; configured lint exited successfully with existing warnings
  outside new Phase 6.8 files. Browser verification was attempted once after implementation and
  remains blocked by the local renderer environment.

See [Running the Console](#running-the-console) to run it locally.

## Evaluation

```
Evaluation Dataset -> Evaluation Runner -> NexusRuntime -> Agent Execution
-> Structured Run Data -> Evaluators -> Evaluation Result -> Metrics / Comparison
```

`evals/` is a deterministic evaluation framework, kept separate from LangGraph nodes, API routing,
CLI presentation, and provider-specific code. It operates only against `NexusRuntime`'s public
interface (`execute`/`get_state`) - the same one the CLI and API already use - via
`run_store.execute_and_record`, so an evaluation run is not a special code path.

**Datasets and cases** (`evals/models.py`, `evals/dataset.py`): a dataset is a small, checked-in
JSON file (`evals/datasets/baseline.json`) with a name, version, description, and a list of cases.
A case only requires `id`, `name`, and `input` - every check is optional, so a case can validate
routing alone, or routing plus tool usage plus response content:

```json
{"id": "math-basic-001", "name": "Basic arithmetic", "input": "What is 17 * 23?", "expected_route": "math"}
```

Available checks: `expected_route`, `expected_tools`, `forbidden_tools`, `response_contains`,
`response_not_contains`, `max_latency_ms`. For the counselor/emotional agent specifically, the
baseline dataset only checks routing and successful execution - no unrealistic content assertions
on an emotionally-supportive reply.

**Evaluation dimensions** (`evals/cases.py`), each producing a pass/fail `DimensionResult`:

- **Routing** - did `route_selected` match `expected_route`? Opt-in per case.
- **Execution** - did the workflow complete successfully (`NexusRuntime`'s own outcome, not a
  guess)?
- **Tools** - were `expected_tools` invoked and `forbidden_tools` avoided? Checked against real
  `tool_started`/`tool_completed`/`tool_denied`/`tool_failed` observability events (`run.tool_events`)
  - **never inferred from what the response text claims it did.**
- **Response** - simple, deterministic `response_contains`/`response_not_contains` substring
  checks. Intentionally basic - **no LLM-as-judge in this phase.**
- **Latency** - did the turn finish within `max_latency_ms`, if set?

A case passes when every dimension it opted into passes (AND semantics) - dimensions a case didn't
request don't count against it.

**Isolation**: every case runs on its own thread, `eval-{evaluation_id}-{case_id}` (never the
`thread-*` ids normal sessions use), so evaluation traffic is visually distinguishable and never
contaminates a real CLI/API conversation. A fresh, random `evaluation_id` is generated per
evaluation run by default, so two separate evaluation runs (even of the identical dataset) never
share threads either.

**Token usage and cost**: aggregated from real provider `usage_metadata` across a run's LLM calls
(`run_store.py`) - `None`/absent whenever the provider didn't return it, never estimated. Cost is
calculated only when both usage **and** pricing are available; pricing is entirely operator-supplied
via `NEXUS_PRICING_FILE` (a small JSON file of `{"model-name": {"input_cost_per_1m_tokens": ...,
"output_cost_per_1m_tokens": ...}}` - see `pricing.py`). No price list ships with NEXUS; an
unconfigured system always reports cost as unavailable, never a wrong number presented as real.

**Metrics and comparison** (`evals/metrics.py`): latency min/max/mean/p50/p95/p99 (linear
interpolation, the same method NumPy's default `percentile` uses), and token/cost totals.
`evals.metrics.compare(summary_a, summary_b)` reports **measurable deltas only** - routing
accuracy, execution success rate, tool success rate, p50/p95/p99 latency, total cost - never
subjective labels like "better" or "worse."

**Deterministic vs. live evaluation** - this distinction matters:

- The **pytest suite** (`tests/test_eval_*.py`, `tests/test_run_store.py`, `tests/test_evaluator.py`)
  always mocks the LLM (and the logical agent's tool-calling path), exactly like the rest of the
  test suite. It never requires `ANTHROPIC_API_KEY` or network access, and never imports
  `evals/run.py`.
- **`python -m evals.run`** (or `python -m evals`) runs the same framework against a REAL
  `NexusRuntime` - a real LLM call (and potentially a real `fetch`, subject to Phase 2's full
  policy) per case. This is explicit, human-invoked, and requires a working `ANTHROPIC_API_KEY`;
  it is never run automatically by tests or CI.
- **`POST /v1/evaluations`** also runs against the API's live runtime - synchronously, which is
  fine for the small baseline dataset but would block the request for a much larger one. A future
  production implementation of large-scale evaluation should use a background job/queue instead -
  not implemented here.

**Run vs. re-run vs. replay** (see `evals/evaluator.py`): a **run** is one execution. Calling
`run_evaluation` again is a **re-run** - the same cases executed again as fresh, independent
executions (a new `evaluation_id` by default means fresh threads too). This is explicitly **not
deterministic replay**: NEXUS does not record or substitute the exact model/tool inputs and
outputs, so a re-run can produce a different result and, against a live runtime, costs real calls
again. Phase 6.7 adds an explicit user-triggered re-run for eligible first-turn runs, preserving the
original input privately in bounded process memory. It starts a new owned session and executes via
`NexusRuntime`; runs with prior thread state cannot be re-run because their full execution context
is not captured. Tool calls and provider costs may occur again. This is not deterministic replay.

**Run/trace storage**: `run_store.RunStore` and `evals/store.py`'s `EvaluationStore` are bounded,
in-process, oldest-evicted caches - the same pattern `api.py`'s run registry has used since Phase 3,
now shared by both the API and the evaluation framework. **Not a database, not durable across
restarts.** Both stores' public shapes (`RunRecord`, `EvaluationRun`) are stable Pydantic models
specifically so a future persistent backend could replace them without changing what `api.py` or
`evals/` read.

## History semantics

Persisting state and sending unlimited history to the LLM are two different decisions - NEXUS
makes the first without (yet) doing the second:

1. **Persisted state** - the full `messages` list for a thread, durably stored by the checkpointer.
2. **Latest user turn** - what actually goes into today's LLM call (`main._latest_user_text`).
3. **Working context** - the small set of fields a given node assembles into a prompt (right now,
   just the latest turn).
4. **Future memory/context mechanisms** - summarization, retrieval, sliding windows - are **not
   implemented**. This is a deliberate scope boundary, not an oversight.

A follow-up like "what about its derivative?" is still classified and answered with no awareness
of the prior turn, exactly as in Phase 0 - persistence changed *where* history lives, not *how
much of it* any node reads.

## Observability

Every execution emits structured JSON log records (`observability.log_event`), each carrying
`timestamp`, `request_id`, `thread_id`, `event_type`, and context fields such as `node`, `route`,
`tool`, `duration_ms`, `success`, and `error_type`:

```json
{
  "timestamp": "2026-09-29T18:03:11.482+00:00",
  "request_id": "req-4f2a1c9d3b7e",
  "thread_id": "thread-8a1c0e2f9d4b",
  "event_type": "route_selected",
  "node": "router",
  "route": "logical",
  "message_type": "logical"
}
```

Lifecycle events: `workflow_started`, `classifier_started`, `classifier_completed`,
`route_selected`, `agent_started`, `agent_completed`, `tool_started`, `tool_completed`,
`tool_failed`, `tool_denied`, `thread_access_denied`, `workflow_completed`, `workflow_failed`.
The last three (`tool_denied`, `thread_access_denied`) are new in Phase 2 and carry a stable,
machine-readable `reason` code (e.g. `PRIVATE_ADDRESS`, `HOST_NOT_ALLOWED`, `TOOL_NOT_AUTHORIZED`
- full list in [SECURITY.md §12](SECURITY.md#12-error-responses---implemented)) - never a raw
exception or traceback.

Rules enforced throughout (see `observability.py`):

- **Metadata, not content** - never message text, prompts, tool arguments, or tool results (for
  `fetch`, never the raw URL or fetched page content).
- **Never fabricated** - provider token usage is only included when the response actually carries
  it; otherwise it's simply absent.
- **Never fatal** - a logging failure is caught and reported at `warning` level, never propagated;
  an observability bug must not take down an agent execution.
- **Defense in depth** - `log_event` also strips any field whose name looks like it could carry a
  secret (`api_key`, `authorization`, `password`, `content`, …), even though every call site is
  written to pass only metadata in the first place.

## Configuration

All of the following are optional environment variables (read via `os.getenv`, loadable from
`.env`); none are secrets and all have secure-by-default working defaults.

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_MODEL` | `anthropic:claude-3-5-sonnet-20241022` | Chat model used for classification and every specialist reply. Pinned to a dated snapshot instead of a floating `-latest` alias - see below. |
| `LLM_TIMEOUT_SECONDS` | `30` | Per-request timeout for a single LLM call. |
| `AGENT_TIMEOUT_SECONDS` | `60` | Timeout for the logical agent's whole tool-calling turn (it may make several LLM + `fetch` round trips). |
| `LLM_MAX_ATTEMPTS` | `3` | Bounded retry budget for transient provider errors (connection errors, timeouts, rate limits, 5xx/overloaded) - not for validation or auth errors, which are never retried. |
| `NEXUS_CHECKPOINT_DB` | `nexus_checkpoints.sqlite` | Path to the SQLite file backing durable thread state. Gitignored; created automatically on first run. |
| `NEXUS_THREAD_ID` | *(generated)* | Resume a specific thread on CLI startup instead of starting a new one. Overridden by a CLI argument (`python main.py <thread_id>`) if given. |
| `ALLOWED_FETCH_SCHEMES` | `https` | Comma-separated list of URL schemes the `fetch` tool may use. HTTP is a documented, explicit opt-in for local development (`ALLOWED_FETCH_SCHEMES=https,http`) - never enabled implicitly. |
| `ALLOWED_FETCH_DOMAINS` | *(empty = no domain restriction)* | Comma-separated exact-host allowlist for `fetch` (e.g. `example.com,docs.example.com`). Exact-match only - subdomains are **not** included automatically, and suffix tricks like `evil-example.com` or `example.com.evil.com` never match `example.com`. SSRF/scheme/credential checks apply regardless of whether this is set. |
| `MAX_FETCH_RESPONSE_BYTES` | `1048576` (1 MiB) | Maximum response size the `fetch` tool will accept, enforced while streaming (the connection is aborted once exceeded, not after downloading everything). |
| `FETCH_TIMEOUT_SECONDS` | `10` | Timeout for the whole `fetch` operation (including any redirects followed), enforced independent of transport details. |
| `MAX_REDIRECTS` | `5` | Maximum redirects `fetch` will follow; every redirect target is revalidated against the same URL/SSRF/domain policy before being followed. |
| `NEXUS_RUN_REGISTRY_SIZE` | `500` | Max entries in the bounded, in-process run store backing `GET /v1/runs/{request_id}` (oldest evicted first). Not a database - see [Evaluation](#evaluation). |
| `NEXUS_SESSION_SCAN_LIMIT` | `2000` | Max raw checkpoint entries `GET /v1/sessions` (Phase 6.4) scans while discovering distinct sessions - see `runtime.NexusRuntime.list_sessions`. A session outside this scan window won't appear in the list (it's still fully readable directly via `GET /v1/sessions/{thread_id}`). |
| `NEXUS_EVALUATION_STORE_SIZE` | `100` | Max entries in the bounded, in-process evaluation store backing `GET /v1/evaluations`, `GET /v1/evaluations/{evaluation_id}`, and related endpoints. |
| `NEXUS_PRICING_FILE` | *(unset = no pricing configured)* | Path to a JSON file of per-model `{"input_cost_per_1m_tokens": ..., "output_cost_per_1m_tokens": ...}`. Unset means cost is always reported as unavailable, never estimated - see [Evaluation](#evaluation). |
| `NEXUS_ENVIRONMENT` | `development` | One of `development` / `test` / `production`. `production` requires `NEXUS_API_TOKEN` to be set - the app refuses to start otherwise. See [Authentication](#authentication). |
| `NEXUS_API_TOKEN` | *(unset = development/no-auth mode)* | Bearer token required on every protected request when set (`Authorization: Bearer <token>`). Never logged. See [Authentication](#authentication). |
| `NEXUS_DATABASE_URL` | *(unset = SQLite backend)* | PostgreSQL connection string (e.g. `postgresql://user:pass@host:5432/nexus`). When set, both the checkpointer and thread ownership become durable and cross-process-safe. See [Database: SQLite vs. PostgreSQL](#database-sqlite-vs-postgresql). Never logged. |
| `NEXUS_RATE_LIMIT_REQUESTS` | `60` | Max requests per principal per window before `429 RATE_LIMITED`. See [Rate limiting](#rate-limiting). |
| `NEXUS_RATE_LIMIT_WINDOW_SECONDS` | `60` | Length of the fixed rate-limit window, in seconds. |
| `NEXUS_RATE_LIMIT_MAX_PRINCIPALS` | `10000` | Max distinct principals the rate limiter tracks at once (oldest-touched evicted first) - a structural bound, not expected to be hit under the current single-token-or-dev-principal auth model. |
| `NEXUS_TEST_DATABASE_URL` | *(unset = Postgres integration tests skipped)* | Test-only: a real, reachable PostgreSQL connection string to run the Postgres integration tests (`tests/test_postgres_backend.py`) against. Never used by application code. |
| `NEXUS_CONSOLE_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | Comma-separated exact-origin allowlist (Phase 6.1) for CORS - which browser origins may call this API directly. The default covers Vite's standard local dev ports; set this for any other Console deployment origin. Read once at process startup (see api.py's CORS comment for why). |

Phase 7 introduces no new application environment variables - the container image and Compose
stack read exactly this same set at container start (see
[Running with Docker](#running-with-docker)); `.env.docker.example` documents which of them a
Compose deployment needs to supply.

**Why pin the model instead of using `-latest`?** A floating alias like
`anthropic:claude-3-5-sonnet-latest` is repointed by Anthropic without notice, so identical code
can silently start calling a different model. That breaks reproducibility (two runs of "the same"
app aren't actually the same) and makes before/after evaluation meaningless once the alias moves
out from under you. Set `ANTHROPIC_MODEL` to deliberately opt into a newer snapshot when you want
one.

## Known limitations

This project is intentionally incremental. As of Phase 6.1, the following are known, unaddressed
gaps - not oversights, but explicitly out of scope so far:

- **No advanced/semantic memory**: see [History semantics](#history-semantics). Each turn is
  classified and answered using only the latest message, even though full history is now persisted.
- **Authentication is real but minimal**: a single configured bearer token (`NEXUS_API_TOKEN`)
  authenticates every request as one principal - there is no per-user account system, no OAuth/SSO,
  no token issuance/rotation/expiry, and no RBAC. Development mode (no token configured) runs fully
  unauthenticated by design; never expose it to untrusted networks. See
  [Authentication](#authentication).
- **Rate limiting is process-local, not distributed**: `rate_limit.RateLimiter` is in-memory per
  API process. A second instance, or a restart, has independent counters - this is not yet a
  production-grade shared limiter (would need e.g. Redis or Postgres). See
  [Rate limiting](#rate-limiting).
- **PostgreSQL makes checkpoint state and thread ownership multi-instance-safe - nothing else.**
  `RunStore`, `EvaluationStore`, and the rate limiter remain bounded, in-process, and
  process-local regardless of which checkpointer backend is configured; see
  [Database: SQLite vs. PostgreSQL](#database-sqlite-vs-postgresql) and
  [ARCHITECTURE.md's multi-instance analysis](ARCHITECTURE.md#multi-instance-analysis-phase-5).
- **DNS-rebinding hardening is scoped to one `fetch` call's own resolve-then-connect race** -
  Phase 5 closes the specific TOCTOU window Phase 2 documented (IP-pinning the real connection to
  the address `check_url` validated), not a general claim about DNS security. See
  [SECURITY.md §3](SECURITY.md#3-ssrf-protection---implemented).
- **Prompt injection is mitigated, not solved**: see
  [Security and tool governance](#security-and-tool-governance). Structural untrusted-content
  marking and policy-isolation-from-content are implemented and tested; general defenses against a
  page manipulating the model's own reasoning are not.
- **The Console is a growing set of vertical slices, not the full GUI**: Phase 6.1 delivered the
  Agent Playground and live execution trace; Phase 6.2 added the Agent Registry, an Agents page, and
  the Test Agent flow; Phase 6.3 added Runs + Run Detail; Phase 6.4 added Sessions + a state
  explorer; Phase 6.5 added Evaluations history, detail, metrics, and comparison; Phase 6.6 added
  a read-only Tools/governance view; Phase 6.7 added run comparison and guarded re-run; Phase 6.8
  added the Dashboard and integrated navigation. Remaining
  Console scopes are listed in
  [Recommended next steps](#recommended-next-steps). The Console also has no authentication
  management UI by design; see [NEXUS Console](#nexus-console).
- **The Agent Registry is static, hand-authored metadata, not a database**: agents are not
  installable, editable, or user-created at runtime - `agents.py` describes the four reference
  agents `main.py` already implements. Adding a new agent still requires a code change.
- **The Runs page shows history, not a live dashboard**: `GET /v1/runs` reflects only the bounded,
  process-local `RunStore` - runs recorded before this API process last started are gone, and a
  run is only visible once it completes (or fails); there is no concept of an in-progress run in the
  list. See [Known limitations](#known-limitations) below on `RunStore`'s bound generally, and
  [NEXUS Console](#nexus-console) for the Phase 6.3 detail.
- **The Sessions page is a bounded discovery window, not an index**: `GET /v1/sessions` finds
  sessions by scanning up to `NEXUS_SESSION_SCAN_LIMIT` raw checkpoint entries (default 2000, most
  recent first) - a session outside that window won't appear in the list, though it remains fully
  readable directly via `GET /v1/sessions/{thread_id}` if its exact `thread_id` is known. There is
  no separate "created at" timestamp: the checkpointer only tracks each thread's latest state, not
  when it was first touched, so Session Detail shows "Updated," never a fabricated "Created."
- **Sessions are state, not memory**: the message history `GET /v1/sessions/{thread_id}` exposes is
  exactly what the LangGraph checkpointer already persists for the active workflow - there is no
  long-term, semantic, or cross-session memory system, and this phase does not add one.
- **The frontend's CORS allowlist is a simple exact-origin list, not a full origin-management
  system**: `NEXUS_CONSOLE_ORIGINS` is read once at process startup (see api.py's CORS comment for
  why); there's no per-request or dynamic origin logic.
- **`GET /v1/runs`/`GET /v1/runs/{request_id}` and the evaluation store are bounded in-process caches, not a
  database**: capped at `NEXUS_RUN_REGISTRY_SIZE` (default 500) / `NEXUS_EVALUATION_STORE_SIZE`
  (default 100) entries, reset on every API restart. Full event history remains in the structured
  logs, not these endpoints.
- **No deterministic replay**: `evals`'s "re-run" capability executes a case's input again as a
  fresh, independent call - it does not record or substitute the exact model/tool inputs and
  outputs from a prior run, so results can differ and, against a live runtime, cost real calls
  again. The Phase 6.7 Runs action is also a fresh execution, not deterministic replay; it only
  supports first-turn runs whose input was privately retained in the current process. Later turns
  and runs absent from the bounded store cannot be re-run.
- **No LLM-as-judge**: response checks are deterministic substring matching
  (`response_contains`/`response_not_contains`) only, by design for this phase.
- **Evaluation cost is only ever as good as operator-supplied pricing**: with no
  `NEXUS_PRICING_FILE` configured (the default), cost is always reported as unavailable, never
  estimated - see [Evaluation](#evaluation).
- **`POST /v1/evaluations` is synchronous**: fine for the small checked-in baseline dataset; a
  much larger evaluation would block the request for its full duration. A background job/queue
  for large evaluations is future work.
- **No network-level egress control**: SSRF checks are application-level (NEXUS resolving and
  validating before connecting); there is no host firewall or egress proxy layer.
- **Phase 7 containerization/CI is a deployment foundation, not a production deployment**: a
  backend Dockerfile, a frontend Dockerfile, a local Compose stack (API + PostgreSQL + Console),
  and a GitHub Actions CI workflow exist (see [Running with Docker](#running-with-docker)), but
  there is no TLS termination, reverse proxy, secrets manager, autoscaling, or real cloud deployment
  target. "Production packaging" describes what ships in the image/Compose file, not a claim that
  the resulting deployment is hardened for real production traffic.
- **The PostgreSQL backend, the backend/frontend container images, and the Compose stack were not
  live-verified in this development environment** - it has neither Docker nor a local PostgreSQL
  installation available. This is an environment limitation, not a design limitation: the CI
  workflow (`.github/workflows/ci.yml`) builds both images, runs a Compose health/readiness/
  authentication smoke test, and runs the existing `tests/test_postgres_backend.py` integration
  suite (LLM calls stubbed) against a real, disposable PostgreSQL service container, un-skipping the
  4 tests skipped locally - but that workflow had not yet been observed running as of this writing
  (see [Running with Docker](#running-with-docker)). On Windows specifically, `psycopg`'s async mode
  requires a `SelectorEventLoop` (Python's default on Windows is `ProactorEventLoop`) - set
  `asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())` before starting the app
  if running the Postgres backend directly on native Windows (outside Docker); this does not affect
  the Docker/Compose path, since containers always run Linux, or Linux/macOS deployments generally.
- **Browser verification for Console Phases 6.6-6.8 remains blocked by the local browser renderer
  environment** - unrelated to Phase 7, carried forward from earlier phases; see
  [NEXUS Console](#nexus-console).

These are planned for later phases, not fixed here. Full detail (including which controls are
already IMPLEMENTED vs. still PLANNED) is in [SECURITY.md](SECURITY.md).

## Prerequisites

- Python **3.13** or newer
- An [Anthropic API key](https://console.anthropic.com/) with available credits
- Internet access at runtime (the `fetch` tool makes outbound HTTPS requests, and Claude calls go
  over the network too)
- [Node.js](https://nodejs.org/) 20+ - only needed to run the Console (`frontend/`); the backend
  (API/CLI/evaluation) has no Node.js dependency at all

## Dependencies

Listed in [requirements.txt](requirements.txt) and [pyproject.toml](pyproject.toml):

| Package | Version | Why it's needed |
|---|---|---|
| `langchain[anthropic]` | >=0.3.24 | provides `init_chat_model` and `create_agent`, used to call Claude and build the tool-calling logical agent |
| `langgraph` | >=0.3.34 | the state-graph framework that defines and runs the classifier → router → agent flow |
| `langgraph-checkpoint-sqlite` | >=3.0.0 | the official LangGraph-maintained SQLite checkpointer (`AsyncSqliteSaver`) used for durable thread state; pulls in `aiosqlite` |
| `httpx` | >=0.27.0 | NEXUS's own HTTP client for the policy-enforced `fetch` tool (`tool_policy.secure_fetch`) - see [MCP as an architectural pattern...](#mcp-as-an-architectural-pattern-and-why-fetch-is-implemented-natively) |
| `python-dotenv` | >=1.1.0 | loads `ANTHROPIC_API_KEY` (and the optional config in [Configuration](#configuration)) from a local `.env` file into the environment |
| `tenacity` | >=9.0.0 | bounded retry with exponential backoff + jitter for transient provider errors |
| `fastapi` | >=0.115.0 | the Phase 3 API layer (`api.py`) - routing, Pydantic request/response validation, OpenAPI generation |
| `uvicorn` | >=0.30.0 | ASGI server used to run the API locally (`uvicorn api:app`) |
| `ipykernel` | >=6.29.5 | lets this project be explored in a Jupyter/IPython notebook, if desired |

**Optional** (`pyproject.toml`'s `postgres` extra - `pip install -e ".[postgres]"` - only needed when
`NEXUS_DATABASE_URL` is configured; see [Database: SQLite vs. PostgreSQL](#database-sqlite-vs-postgresql)):

| Package | Version | Why it's needed |
|---|---|---|
| `langgraph-checkpoint-postgres` | >=2.0.0 | the official LangGraph-maintained Postgres checkpointer (`AsyncPostgresSaver`) |
| `psycopg[binary,pool]` | >=3.1.0 | the async Postgres driver and ownership-store connection pool; the checkpointer manages its own pool |

As of Phase 2, `langchain-mcp-adapters` and `mcp-server-fetch` are **no longer dependencies** -
the live `fetch` tool is native (see above); MCP remains an architectural pattern NEXUS's agent
framework supports, not a package currently in use.

Test-only dependencies (`pytest`, `pytest-asyncio`) are listed separately in
[requirements-dev.txt](requirements-dev.txt) - see [Running the tests](#running-the-tests).

**Frontend** (`frontend/package.json`, Node.js only, entirely separate from the Python
dependencies above): React 19, Vite, Tailwind CSS, and TypeScript for the app itself; Vitest and
React Testing Library for tests. No UI component or icon library - see
[ARCHITECTURE.md](ARCHITECTURE.md#nexus-console-phase-61) for why.

## Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/osinachix/LangGraph-Multi-Agent-Router.git
cd LangGraph-Multi-Agent-Router

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Anthropic API key:

```
ANTHROPIC_API_KEY=your-key-here
```

`.env` is listed in [.gitignore](.gitignore) and will never be committed.

All [configuration](#configuration) (model, timeouts, retry budget, checkpoint DB path, fetch
security policy) is optional - the app runs with secure defaults if you skip it.

## Running the project

```bash
python main.py                  # start a new thread
python main.py demo-session-001 # resume (or start) a specific thread
```

On startup, `main.py` builds the logical agent (with its policy-gated `fetch` tool) and opens (or
creates) the SQLite checkpointer database before printing the current `thread_id` and opening the
prompt.

Example session:

```
NEXUS runtime ready. thread_id=thread-8a1c0e2f9d4b
Type 'new' to start a fresh thread, 'exit' to quit.
[thread-8a1c0e2f9d4b] Message: I'm feeling really overwhelmed with work lately
[req-4f2a1c9d3b7e] Assistant: That sounds really difficult...

[thread-8a1c0e2f9d4b] Message: what's 15% of 340?
[req-9b3e7a1f2c5d] Assistant: 15% of 340 = 51...

[thread-8a1c0e2f9d4b] Message: new
Started new thread. thread_id=thread-1f6d9c4a8b3e
[thread-1f6d9c4a8b3e] Message: exit
Bye
```

- Type `exit` at any prompt to quit (case-insensitive, surrounding whitespace is ignored). Blank
  input is silently ignored rather than sent to the model.
- Type `new` to start a fresh thread mid-session - the old thread's state stays persisted, it's
  just no longer the active one.
- Re-running `python main.py thread-8a1c0e2f9d4b` on a later run resumes that thread's persisted
  conversation state from the SQLite checkpointer.

If the AI provider has a transient failure, the app retries a bounded number of times with backoff
before giving up; if it still fails, you'll see a plain `Assistant: Sorry, I couldn't complete
that request...` reply instead of a crash. If the logical agent's `fetch` tool is blocked by
security policy (an unauthorized scheme, a private address, a domain not on the allowlist, an
oversized response, or a redirect to somewhere disallowed), the agent is told so directly and can
relay that to you - see [Observability](#observability) for how both cases are also logged as
structured events.

## Running the API server

```bash
uvicorn api:app --reload
```

By default (no `NEXUS_API_TOKEN` set) the API runs in **development mode** - every request is
auto-authenticated, exactly as in Phase 3/4:

```bash
curl -X POST http://127.0.0.1:8000/v1/sessions
# {"thread_id":"thread-..."}

curl -X POST http://127.0.0.1:8000/v1/sessions/thread-.../messages \
  -H "Content-Type: application/json" \
  -d '{"message":"what is 15% of 480?"}'
# {"thread_id":"thread-...","request_id":"req-...","response":"...","route":"math","status":"completed","duration_ms":...}

curl http://127.0.0.1:8000/v1/sessions/thread-...
curl http://127.0.0.1:8000/v1/runs/req-...
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/ready
```

To require authentication, set `NEXUS_API_TOKEN` before starting the server, and send it as a
bearer token on every protected request:

```bash
NEXUS_API_TOKEN=my-local-dev-token uvicorn api:app --reload
```

```bash
curl -X POST http://127.0.0.1:8000/v1/sessions
# {"error":{"code":"UNAUTHENTICATED","message":"Missing Authorization header."}}

curl -X POST http://127.0.0.1:8000/v1/sessions \
  -H "Authorization: Bearer my-local-dev-token"
# {"thread_id":"thread-..."}
```

See [Streaming (SSE)](#streaming-sse) for the streaming endpoint's usage.

Interactive API docs: open `http://127.0.0.1:8000/docs` (Swagger UI) or fetch
`http://127.0.0.1:8000/openapi.json` directly.

The runtime (and its checkpointer connection) is created once at startup via FastAPI's `lifespan`
and closed once at shutdown - not per request. `NEXUS_CHECKPOINT_DB` (see
[Configuration](#configuration)) controls which SQLite file the API uses when no
`NEXUS_DATABASE_URL` is configured, same as the CLI; run them against different files if you don't
want the CLI and the API sharing thread state.

## Running with PostgreSQL

Install the optional extra, start (or point at) a PostgreSQL instance, and set
`NEXUS_DATABASE_URL`:

```bash
pip install -e ".[postgres]"
# or: pip install langgraph-checkpoint-postgres psycopg[binary,pool]

NEXUS_DATABASE_URL=postgresql://user:pass@localhost:5432/nexus uvicorn api:app --reload
```

`runtime.create_runtime` detects `NEXUS_DATABASE_URL` and switches both the LangGraph checkpointer
(`AsyncPostgresSaver`) and the thread-ownership store (`access.PostgresAccessStore`, a small
`nexus_thread_owners` table) to Postgres - the SQLite path (`NEXUS_CHECKPOINT_DB`) is untouched and
still the default when `NEXUS_DATABASE_URL` is unset. No agent logic, API route, or evaluation code
changes based on which backend is active. See
[Database: SQLite vs. PostgreSQL](#database-sqlite-vs-postgresql).

**Windows note**: `psycopg`'s async mode requires a `SelectorEventLoop`; Python's default event
loop on Windows is `ProactorEventLoop`. If you see an error mentioning `ProactorEventLoop` when
using the Postgres backend on Windows, set the event loop policy before starting the app:

```python
import asyncio
asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
```

This restriction is specific to Windows; Linux/macOS deployments are unaffected. **It does not apply
to the Docker path below**: container images always run Linux (`python:3.13-slim`), so
`ProactorEventLoop` never enters the picture even when Docker Desktop's host is Windows.

## Running with Docker

Phase 7 adds a production-oriented container image and a local, production-like Compose stack -
this is a **deployment foundation, not a claim of "production-ready"**; see
[Known limitations](#known-limitations) below and ARCHITECTURE.md's Phase 7 section for exactly
what is and isn't covered.

**Backend image** (`Dockerfile`, root of the repo): a two-stage build producing a minimal image
that runs `uvicorn api:app` as a non-root user. Dependencies come from `requirements-docker.txt` -
the same runtime dependencies as `requirements.txt`/`pyproject.toml` plus the `postgres` extra
(so one image supports both backends, selected at runtime by `NEXUS_DATABASE_URL`, exactly as
[Running with PostgreSQL](#running-with-postgresql) above), minus `ipykernel` (a notebook-only
dependency never imported by the API). Nothing is baked into the image: every environment variable
in [Configuration](#configuration) is supplied at container start, never at build time, and no
secret is ever copied into a layer.

```bash
docker build -t nexus-api .
docker run --rm -p 8000:8000 \
  -e NEXUS_API_TOKEN=your-token \
  -e ANTHROPIC_API_KEY=your-key \
  nexus-api
```

The image's `HEALTHCHECK` polls the existing `GET /ready` endpoint (a real checkpointer round
trip, no LLM call) - not a separate mechanism invented for Docker.

**Frontend image** (`frontend/Dockerfile`): builds the existing Vite production bundle
(`npm run build`, unchanged) and serves the static output with nginx. `VITE_NEXUS_API_BASE_URL` is
a Vite **build-time** value baked into the compiled JS (see `frontend/src/lib/config.ts`), passed
as a Docker build argument:

```bash
docker build -t nexus-console --build-arg VITE_NEXUS_API_BASE_URL=http://localhost:8000 ./frontend
docker run --rm -p 5173:80 nexus-console
```

`VITE_NEXUS_API_TOKEN` is deliberately not accepted as a build argument here - per
[NEXUS Console](#nexus-console) and CLAUDE.md, that value is not a secret but is only appropriate
for a trusted local/demo browser, never baked into a shared or distributed image.

**Compose stack** (`docker-compose.yml`): brings up PostgreSQL, the API (configured with
`NEXUS_DATABASE_URL` pointing at it), and the Console together, exercising the exact same
`AsyncPostgresSaver`/`access.PostgresAccessStore` code path as the non-Docker
[Running with PostgreSQL](#running-with-postgresql) section - not a second persistence
implementation.

```bash
cp .env.docker.example .env.docker   # then fill in real values - never commit .env.docker
docker compose --env-file .env.docker up --build
```

PostgreSQL is bound to `127.0.0.1:5432` only (not `0.0.0.0`), matching the "don't expose PostgreSQL
unnecessarily" principle - see SECURITY.md's Phase 7 section.

**What has and hasn't been live-verified**: this environment has neither Docker nor a local
PostgreSQL installation available, so the image build, the Compose stack, and live PostgreSQL
behavior (checkpoint/ownership persistence across a real restart) have not been executed or
observed in this development environment. They have not been fabricated either - see
[Known limitations](#known-limitations). The CI workflow (`.github/workflows/ci.yml`) builds both
images and runs a Compose health/readiness/authentication smoke test, and separately runs the
existing `tests/test_postgres_backend.py` integration suite against a real, disposable PostgreSQL
service container - un-skipping the 4 tests that are skipped in this local environment. That
workflow is written to real, documented GitHub Actions/Docker Compose semantics, but has not yet
been observed running (no push/PR has triggered it as of this writing) - do not treat this section
as proof it has run successfully until an actual CI run has been reviewed.

## Running the Console

Requires [Node.js](https://nodejs.org/) 20+ and the API server already running (see
[Running the API server](#running-the-api-server)).

```bash
cd frontend
npm install
npm run dev
```

Open the printed local URL (Vite's default is `http://localhost:5173`). The Console talks to
`http://127.0.0.1:8000` by default; if your API is running elsewhere, or requires
`NEXUS_API_TOKEN`, copy `frontend/.env.example` to `frontend/.env.local` (gitignored) and set
`VITE_NEXUS_API_BASE_URL`/`VITE_NEXUS_API_TOKEN` - see `frontend/src/lib/config.ts`. Vite embeds
`VITE_*` values into the browser bundle, so the API token is not secret and is only suitable for a
trusted local/demo browser. Do not use a real shared or production credential here.

If the Console reports "Runtime Offline" with a browser console error mentioning CORS, the API's
`NEXUS_CONSOLE_ORIGINS` allowlist doesn't include the Console's origin - see
[Configuration](#configuration).

Frontend tests: `cd frontend && npm test` (Vitest + React Testing Library; no real backend
required - see [NEXUS Console](#nexus-console)).

## Running an evaluation

Two ways, both against a REAL LLM provider (requires a working `ANTHROPIC_API_KEY`) - the
deterministic pytest suite covering this same framework never needs one; see
[Evaluation](#evaluation).

**Via the CLI**, against an isolated in-memory checkpoint by default (never touches your normal
`NEXUS_CHECKPOINT_DB`):

```bash
python -m evals.run
# Running LIVE NEXUS evaluation. This calls the configured LLM provider for every case.
# Loaded dataset 'baseline' v1.0.0 (5 cases) from evals/datasets/baseline.json
#
# Evaluation <id>  (dataset: baseline v1.0.0)
#   cases:              5
#   passed:             5
#   ...
```

**Via the API** (with `uvicorn api:app --reload` already running):

```bash
curl -X POST http://127.0.0.1:8000/v1/evaluations
# {"evaluation_id": "...", "total_cases": 5, "passed_cases": ..., "routing_accuracy": ..., ...}

curl http://127.0.0.1:8000/v1/evaluations/<evaluation_id>/results
curl http://127.0.0.1:8000/v1/evaluations/<evaluation_id>/metrics
curl http://127.0.0.1:8000/v1/evaluations/compare/<evaluation_id_a>/<evaluation_id_b>
```

## Running the tests

Tests mock the LLM (and use `httpx.MockTransport`/fake DNS for `fetch` policy tests), so no
Anthropic API key or external network access is required.

```bash
pip install -r requirements-dev.txt
pytest
```

The PostgreSQL integration tests (`tests/test_postgres_backend.py`) are the one exception: they are
explicitly **skipped**, not faked, unless `NEXUS_TEST_DATABASE_URL` is set to a real, reachable
PostgreSQL connection string (see [Configuration](#configuration)):

```bash
NEXUS_TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/nexus_test pytest tests/test_postgres_backend.py
```

A handful of deterministic, no-database-required tests in that same file always run regardless
(confirming `create_runtime` actually dispatches to the Postgres code path when configured, and
that `access.PostgresAccessStore` issues the expected SQL) - see that file's module docstring.

**Frontend tests** are separate (Node.js/Vitest, not pytest) - see
[Running the Console](#running-the-console).

## Project layout

- `main.py`: the router graph (classifier/router/specialist nodes), the native `fetch` tool and
  its instrumentation/authorization wrapper, `build_logical_agent()` (shared by the CLI and the
  API), the CLI entrypoint, and (Phase 6.1) `DIRECT_AGENT_GRAPH_BUILDERS` - four minimal
  classifier-free graphs reusing the same node functions, for the Console's direct-agent mode
- `api.py`: the FastAPI service layer - sessions/messages/runs/evaluations/health/readiness
  endpoints, Pydantic request/response models, error handling, and (Phase 6.1) CORS middleware for
  the Console. Calls `NexusRuntime` (and `evals/`) only; contains no agent logic of its own.
- `agents.py` (Phase 6.2): the Agent Registry - `AgentDefinition`, `list_agents()`/`get_agent()`
  backing `GET /v1/agents[/{agent_id}]`, and `is_executable()`, the authoritative allowlist
  `api.py`'s `MessageRequest.agent` validator calls before any direct-agent execution. Metadata
  only - no agent logic, no execution.
- `runtime.py`: `NexusRuntime` - execution identity (request/thread ids), checkpointer lifecycle
  (SQLite or, as of Phase 5, PostgreSQL - see `create_runtime`), thread-access-boundary checks
  (`verify_access`, `new_session`, and (Phase 6.3) the read-only `owner_of` used by the run-list
  endpoint), workflow-level observability, and (Phase 6.4) `list_sessions()` - discovers this
  principal's sessions directly from the checkpointer's own `alist`, no second persistence layer.
  Agent-agnostic; used by the CLI, the API, and the evaluation framework.
- `run_store.py`: `RunRecord`/`RunStore`, `execute_and_record`, and (Phase 5) `build_run_record` -
  captures structured per-execution data (events, tool activity, token usage, cost, and (Phase 6.3)
  which agent actually ran) from the same observability stream, via
  `observability.capture_events()`/`stream_events()`. `RunStore.list_recent()` (Phase 6.3) returns
  the bounded store's contents most-recent-first; filtering/ownership/limits are the API layer's
  job. Shared by `api.py` (both the synchronous and SSE endpoints) and `evals/`.
- `pricing.py`: configurable, operator-supplied model pricing for cost calculation - no built-in
  price list; cost is `None` unless both usage and pricing are available.
- `evals/`: the Phase 4 evaluation framework - `models.py` (typed case/result/summary models,
  including Phase 5's `owner_principal_id`), `dataset.py` (load/validate), `cases.py`
  (per-dimension evaluators), `metrics.py` (latency percentiles, token/cost aggregation,
  comparison), `evaluator.py` (the runner, isolated eval-\* threads), `store.py` (bounded
  evaluation store), `run.py`/`__main__.py` (the live `python -m evals.run` CLI entrypoint),
  `datasets/baseline.json` (the checked-in dataset).
- `tool_policy.py`: the deterministic tool/network security policy - URL scheme/credential/SSRF/
  domain checks, tool authorization, the native `secure_fetch` HTTP implementation, and (Phase 5)
  DNS-rebinding-resistant connection pinning (`_PinnedNetworkBackend`, `_build_pinned_transport`)
- `tool_registry.py` (Phase 6.6): safe tool metadata derived from the definitions actually bound to
  agent graphs and the existing `AGENT_TOOL_POLICY`; it is not a second authorization allowlist
- `access.py`: `ThreadAccessRegistry` (in-memory, default) and `PostgresAccessStore` (Phase 5,
  durable/cross-process), plus the CLI/API/eval development principals - ownership bookkeeping, not
  authentication (see `auth.py` for that)
- `auth.py` (Phase 5): `Principal`, `authenticate()` - HTTP-boundary bearer-token authentication;
  the runtime never sees an HTTP header or this module's types, only a plain `principal_id`
- `rate_limit.py` (Phase 5): `RateLimiter` - bounded, in-process, per-principal fixed-window request
  counter backing the API's `429 RATE_LIMITED` responses
- `config.py` (Phase 5): `load_config()` - centralized, validated startup configuration (auth mode,
  database backend, rate limits); raises `ConfigError` for anything invalid enough that starting
  the app anyway would be misleading (e.g. production with no way to authenticate a caller)
- `observability.py`: structured JSON event logging, secret-safe field filtering, token-usage
  extraction, `capture_events()` for per-execution event capture, and (Phase 5) `stream_events()`
  for the SSE endpoint's live event forwarding
- `simple.py`: a minimal single-node LangGraph example with no routing or tools, kept as a
  standalone reference for the smallest possible LangGraph app
- `tests/`: unit, policy, API, and evaluation-framework tests for routing, classification, config
  resolution, CLI input parsing, error/retry behavior, thread persistence/isolation, request ids,
  observability events, URL/domain/SSRF/redirect/response-size/timeout/DNS-rebinding security, tool
  authorization, prompt-injection handling, thread access boundaries, log security, dataset
  loading/validation, evaluation dimensions, metrics/comparison, the run store, authentication,
  authorization, rate limiting, SSE streaming, PostgreSQL (environment-dependent), runtime
  lifecycle, and the full FastAPI HTTP contract (including OpenAPI) - all with the LLM and network
  mocked
- `ARCHITECTURE.md`: component diagram, execution identity, persistence/observability model, the
  API layer, the evaluation architecture, and (Phase 5) the auth/authz/rate-limit/SSE/database
  architecture and multi-instance analysis
- `SECURITY.md`: threat model, every security control's IMPLEMENTED/PLANNED status, and known
  limitations
- `graph.png`: rendered diagram of the graph in `main.py`
- `requirements.txt`: pip dependency list for running the app
- `requirements-dev.txt`: adds test-only dependencies (`pytest`, `pytest-asyncio`)
- `pyproject.toml`: project metadata, dependencies (including the optional `postgres` extra), and
  pytest configuration
- `Dockerfile` (Phase 7): production-oriented backend image - two-stage build, non-root user, runs
  `uvicorn api:app`; see [Running with Docker](#running-with-docker)
- `requirements-docker.txt` (Phase 7): the backend image's dependency list - mirrors
  `requirements.txt` plus the `postgres` extra, minus the notebook-only `ipykernel`
- `.dockerignore` (Phase 7): backend image build-context exclusions (secrets, `.venv`, `tests/`,
  `frontend/`, caches)
- `docker-compose.yml` (Phase 7): local, production-like stack - PostgreSQL, the API (configured
  with `NEXUS_DATABASE_URL`), and the Console; see [Running with Docker](#running-with-docker)
- `.env.docker.example` (Phase 7): checked-in placeholder template for `docker-compose.yml`'s
  required variables - copy to `.env.docker` (gitignored) and fill in real values
- `.github/workflows/ci.yml` (Phase 7): GitHub Actions CI - backend pytest, frontend
  tests/lint/build, a live-PostgreSQL integration job (disposable service container, LLM calls
  stubbed), a repository-hygiene job (credential/em-dash/merge-conflict scans), and a job that
  builds both container images and smoke-tests the Compose stack
- `frontend/` (Phase 6.1-6.6): the NEXUS Console.
  - `Dockerfile`/`nginx.conf`/`.dockerignore` (Phase 7): production static build (the existing
    `npm run build`) served by nginx - no Node.js runtime in the final image; see
    [Running with Docker](#running-with-docker)
  - `src/lib/`: `apiClient.ts` (typed HTTP client for agents, tools, runs, sessions, evaluations, and
    comparison), `sseClient.ts` + `sseParser.ts` (the dedicated
    SSE streaming client - hand-rolled since browser `EventSource` can't do POST+auth headers),
    `traceReducer.ts` (pure, unit-tested translation of raw events into human-readable trace steps -
    shared by the live Playground trace and, via `runToTrace.ts`, the historical Run Detail trace),
    `runToTrace.ts` (Phase 6.3: reshapes a stored `RunResponse` into the same event shape SSE
    produces, then folds it through the same reducer - no second trace implementation),
    `formatters.ts`, `config.ts` (local dev config, no hardcoded tokens)
  - `src/types/`: `api.ts`/`events.ts`/`trace.ts`/`agent.ts`/`tool.ts`/`session.ts` - domain types mirroring
    the backend contract; `agent.ts` is backend-driven (no static agent list); `api.ts` gained
    `RunListResponse`/`RunListParams` and `RunResponse.agent`/`.response` (Phase 6.3), and
    `SessionMessage`/`SessionListResponse`/`SessionListParams` and `SessionResponse.messages`
    (Phase 6.4); evaluation summary/result/comparison types were added in Phase 6.5; `session.ts` (Phase 6.4) holds only a presentational role-label mapping - it
    implements no memory system, matching CLAUDE.md's State vs Memory distinction
  - `src/hooks/`: `useAgentRegistry.ts`/`useAgent.ts` (Phase 6.2), `useRuns.ts`/`useRun.ts`
    (Phase 6.3), `useSessions.ts`/`useSession.ts` (Phase 6.4), `useEvaluations.ts` (Phase 6.5),
    and `useTools.ts` (Phase 6.6), all following the same
    loading/ready/error(/not_found) pattern
  - `src/components/`: shared, presentational UI (icons, status indicators, app shell, sidebar, top
    bar, and (Phase 6.3) `CopyButton.tsx` for request/thread IDs)
  - `src/features/playground/`: the Agent Playground feature - mode selector, composer, execution
    trace, route/agent visualization, final response, run metadata, error panel,
    `usePlaygroundExecution.ts` (the feature's state/orchestration hook, also owning the agent
    registry and an optional preselected agent), and `PlaygroundPage.tsx` (reads the `?agent=` URL
    param for the Test Agent flow)
  - `src/features/agents/`: the Agent Registry feature - `AgentsPage.tsx` (card grid),
    `AgentCard.tsx`/`AgentCardSkeleton.tsx`/`AgentStatusBadge.tsx`, and `AgentDetailPage.tsx`
    (capabilities/tools/execution modes plus a Test Agent link into the Playground)
  - `src/features/runs/`: the Runs feature - `RunsPage.tsx` (filterable/sortable table,
    `RunsTable.tsx`/`RunsTableSkeleton.tsx`, and (Phase 6.4) reads an optional `?thread_id=` filter),
    and `RunDetailPage.tsx` (header with a Phase 6.4 "View Session" link, `RunSummary.tsx`, and the
    reused `ExecutionTrace`/`FinalResponse` from `features/playground/`)
  - `src/features/sessions/` (Phase 6.4): the Sessions feature - `SessionsPage.tsx`
    (`SessionsTable.tsx`/`SessionsTableSkeleton.tsx`), `SessionDetailPage.tsx` (summary, a "View
    Runs" link into `/runs?thread_id=<id>`, a Refresh action), `SessionSummary.tsx`, and
    `SessionMessageList.tsx` (plain-text rendering only - no markdown, no HTML interpretation)
  - `src/features/evaluations/` (Phase 6.5): evaluation history, synchronous baseline action,
    summary metrics, per-case results with links to Run Detail, and neutral comparison
  - `src/features/tools/` (Phase 6.6): read-only tool registry and retained activity with links to
    existing Agent Detail and Run Detail pages
  - `src/App.tsx`: route definitions (`react-router-dom`) for `/playground`, `/agents`,
    `/agents/:agentId`, `/runs`, `/runs/:requestId`, `/sessions`, `/sessions/:threadId`,
    `/evaluations`, `/evaluations/:evaluationId`, and `/tools`, inside
    the app shell
  - `*.test.ts`/`*.test.tsx` next to the modules they test (Vitest + React Testing Library);
    `src/test/agentFixtures.ts`/`runFixtures.ts`/`sessionFixtures.ts` hold shared mock
    registry/run/session data
  - `.env.example`: documents the two optional local-dev env vars; real values go in
    `.env.local` (gitignored)

## Troubleshooting

- **`ModuleNotFoundError`**: the virtual environment isn't activated, or
  `pip install -r requirements.txt` wasn't run inside it.
- **Authentication / API errors** (`anthropic.AuthenticationError`, 401): check that `.env` exists
  in the project root and `ANTHROPIC_API_KEY` is set to a valid key with available credits. This
  no longer crashes the process - after exhausting its retry budget the app prints a fallback error
  reply and keeps the prompt loop running, so you can fix `.env` and try again without restarting.
- **Wrong Python version**: this project requires Python 3.13+; check with `python --version`.
- **The logical agent says a fetch was "blocked by NEXUS security policy"**: expected behavior,
  not a bug - the URL failed one of the checks in [Configuration](#configuration) (scheme, domain
  allowlist, private/loopback address, response size, or redirect target). Check the logged
  `tool_denied` event's `reason` code for which one, and [SECURITY.md](SECURITY.md) for what each
  code means.
- **Logical agent answers seem to ignore a URL you gave it**: the `fetch` tool is only called when
  Claude decides it's needed; try being explicit, e.g. "fetch https://example.com and summarize
  it."
- **Responses seem to ignore something you said earlier in the conversation**: expected for now -
  see [History semantics](#history-semantics).
- **A `nexus_checkpoints.sqlite` (or `-wal`/`-shm`) file appears in the project root**: that's the
  local dev checkpointer database; it's gitignored. Delete it to reset all persisted thread state.
- **`GET /v1/runs/{request_id}` returns `RUN_NOT_FOUND` for a run you just made**: the run registry
  is bounded and in-process (see [Configuration](#configuration)'s `NEXUS_RUN_REGISTRY_SIZE`) - a
  server restart or eviction after many runs will lose older entries. This is documented, not a bug.
- **`GET /v1/sessions/{thread_id}` returns 403 unexpectedly**: another principal already owns that
  `thread_id` in this API process's access registry (see
  [Security and tool governance](#security-and-tool-governance)). In normal single-principal API
  use this shouldn't happen; if you're running both the CLI and the API against the same
  `NEXUS_CHECKPOINT_DB`, they use different principals (`LOCAL_CLI_PRINCIPAL` vs.
  `LOCAL_API_PRINCIPAL`) and separate in-process registries, so this is a same-process-only
  boundary - see [Known limitations](#known-limitations).
- **`uvicorn: address already in use`**: another process (maybe a previous `uvicorn api:app` run)
  is still bound to the port; stop it, or run with `--port` set to something else.
- **An evaluation case reports `cost_usd: null`**: expected unless `NEXUS_PRICING_FILE` is
  configured for the exact model name in use - see [Evaluation](#evaluation) and
  [Configuration](#configuration). This is never a bug; it's the documented default.
- **`python -m evals.run` fails with an authentication error**: it calls a real LLM provider, so it
  needs the same working `ANTHROPIC_API_KEY` the CLI/API do - see [Setup](#setup). The pytest suite
  covering the same framework never needs this.
- **`401 UNAUTHENTICATED` from every API call**: `NEXUS_API_TOKEN` is configured on the server -
  send `Authorization: Bearer <token>` on every protected request, or unset the variable to run in
  development mode. See [Authentication](#authentication).
- **The app refuses to start with a `ConfigError` mentioning `NEXUS_API_TOKEN`**:
  `NEXUS_ENVIRONMENT=production` was set without `NEXUS_API_TOKEN` - this is intentional (NEXUS
  never silently runs an unauthenticated production deployment); set a token or use
  `NEXUS_ENVIRONMENT=development`.
- **`429 RATE_LIMITED`**: the calling principal exceeded `NEXUS_RATE_LIMIT_REQUESTS` within
  `NEXUS_RATE_LIMIT_WINDOW_SECONDS` (defaults: 60 requests / 60 seconds) - see the `Retry-After`
  response header, or [Rate limiting](#rate-limiting) / [Configuration](#configuration) to adjust
  the limits for local development.
- **The SSE stream (`.../messages/stream`) seems to hang or buffer**: some HTTP clients/proxies
  buffer streaming responses by default - use `curl -N` (no-buffer) as shown in
  [Streaming (SSE)](#streaming-sse), or check that nothing between the client and server (e.g. a
  reverse proxy) is buffering `text/event-stream` responses.
- **Using `NEXUS_DATABASE_URL` fails with an error mentioning `ProactorEventLoop`**: a Windows-only
  limitation of `psycopg`'s async mode - see the note at the end of
  [Running with PostgreSQL](#running-with-postgresql).
- **Postgres integration tests report "skipped"**: expected unless `NEXUS_TEST_DATABASE_URL` is set
  to a real, reachable PostgreSQL instance - see [Running the tests](#running-the-tests). This is
  not a failure; the tests are honestly reporting that no database was available.
- **The Console shows "Runtime Offline" even though the API is running**: almost always CORS - open
  the browser console; a message like "has been blocked by CORS policy" confirms it. Add the
  Console's origin to `NEXUS_CONSOLE_ORIGINS` on the API and restart it - see
  [NEXUS Console](#nexus-console) and [Configuration](#configuration). `curl`/`httpx`-based checks
  never surface this, since only browsers enforce CORS.
- **The Console's session panel is stuck on "Creating session..."**: check the browser console/network
  tab for the actual failure - most commonly CORS (see above) or the API simply not running at
  `VITE_NEXUS_API_BASE_URL`.
- **Direct-agent mode in the Console returns an unexpected 400**: the `agent` field only accepts
  `counselor`/`logical`/`math`/`coding` (see [NEXUS Console](#nexus-console)); this matches the
  Console's own selector, so this should only happen when calling the API directly with a typo.

## Recommended next steps

Phases 6.1 through 6.8 are implemented: Playground and live trace, Agent Registry, Runs,
Sessions/state explorer, Evaluations, read-only Tools/governance, run comparison, guarded fresh
re-run, and the Dashboard. Browser verification for Phases 6.6 through 6.8 remains blocked by the
local browser renderer. Remaining Console polish should use the existing APIs and runtime model. See the
[Roadmap](#roadmap).

Phase 7 (production packaging) is implemented: a backend Dockerfile, a frontend Dockerfile, a local
Compose stack (API + PostgreSQL + Console) exercising the existing Phase 5 Postgres backend, and a
GitHub Actions CI workflow that builds both images and runs the PostgreSQL integration suite against
a live, disposable database. The first actual CI run and any real Docker/PostgreSQL environment
should be used to observe and confirm what this session could only author and statically verify -
see [Running with Docker](#running-with-docker) and [Known limitations](#known-limitations).

Other future work includes deterministic replay, a distributed rate limiter, a background job/queue
for larger evaluations, persistent RunStore/EvaluationStore history, real user accounts/OAuth/SSO/RBAC,
TLS termination/reverse proxy/secrets-manager integration, and a real cloud deployment target. These
items remain outside the current scope unless explicitly requested.

## License

Licensed under the [Apache License, Version 2.0](LICENSE). You may use, modify, and distribute this
project, including commercially, provided you comply with the license's attribution and notice
terms - see the [LICENSE](LICENSE) file for the full text.
