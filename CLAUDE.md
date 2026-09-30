# NEXUS - Claude Code Project Instructions

## 1. Project Identity

**Project:** NEXUS

**Full name:** AI Agent Runtime & Orchestration Platform

**Tagline:** Connect. Orchestrate. Execute. Observe.

NEXUS is a reusable, domain-agnostic platform for building, executing,
observing, evaluating, and governing AI agents and agentic workflows.

NEXUS must NOT contain company-specific branding, terminology, or
domain assumptions.

Do not introduce references to specific employers, companies, customers,
or proprietary enterprise systems unless explicitly requested.

---

# 2. Core Product Vision

NEXUS is not merely a chatbot and not merely a collection of agents.

The long-term platform model is:

    Build
      ↓
    Run
      ↓
    Observe
      ↓
    Evaluate
      ↓
    Govern

The platform should eventually provide:

- Agent runtime
- Agent orchestration
- Tool integration
- Tool governance
- Persistent state
- Observability
- Evaluation
- Execution traces
- Separate run comparison
- Human approval workflows
- Agent registry
- API/SDK
- NEXUS Console
- Production deployment capabilities

The project should remain:

- model-agnostic where practical
- framework-aware but not framework-dependent at the product boundary
- domain-agnostic
- security-conscious
- observable
- testable
- extensible

---

# 3. Current Architecture

Current high-level architecture:

    Client
      │
      ├── CLI
      │
      ├── HTTP API (any client)
      │
      └── NEXUS Console (frontend/, Phase 6.1: Playground; Phase 6.2: Agents;
             Phase 6.3: Runs; Phase 6.4: Sessions; Phase 6.5: Evaluations;
             Phase 6.6: Tools / Governance)
             │
             ▼
        NEXUS API
             │
             ▼
        NexusRuntime
             │
             ▼
          LangGraph
             │
       ┌─────┴─────┐
       │           │
   Classifier    Router
       │
       ├── emotional/counselor
       ├── logical
       ├── math
       └── coding
             │
             ▼
        Tool Policy
             │
             ▼
           Tools

Observability surrounds the runtime and records structured lifecycle
events.

Evaluation runs through the same NexusRuntime execution path.

As of Phase 5, the API boundary also enforces authentication,
authorization, and rate limiting before a request reaches NexusRuntime -
see [Section 22](#22-phase-5---status-complete).

As of Phase 6.8, the Console includes the Dashboard, Agent Playground,
Agent Registry / Agents page, Runs / Run Detail / Comparison / guarded
fresh re-run, Sessions / state explorer, Evaluations, and the read-only
Tools / Governance view:

    NEXUS Console (Dashboard + Playground + Agents + Runs + Sessions + Evaluations + Tools, Phase 6.1-6.8)
          │
          ▼
       NEXUS API
          │
          ▼
      NexusRuntime
          │
       LangGraph
          │
      Agents / Tools

The Agent Registry (`agents.py`) sits beside NexusRuntime as a metadata
and allowlist layer, not inside the execution path:

    Agent Registry (agents.py)
          │
          ▼
    GET /v1/agents[/{agent_id}]  (NEXUS API)
          │
          ▼
    NEXUS Console: Agents page → Test Agent → Playground

Completed executions are readable, not just live-streamable, via the
same bounded RunStore Phase 4 already built:

    RunStore (run_store.py)
          │
          ▼
    GET /v1/runs, GET /v1/runs/{request_id}  (NEXUS API)
          │
          ▼
    NEXUS Console: Runs page → Run Detail (reuses the Playground's
    trace reducer/components - see Section 24's Phase 6.3 update)

RUN and SESSION are deliberately distinct concepts (see Section 16 -
"State vs Memory" - and do not confuse the two):

    RUN     = what happened during one execution
    SESSION = the persistent conversational/workflow state
              associated with a thread

Sessions are discovered directly from LangGraph checkpoint state, not a
second persistence layer:

    NexusRuntime.list_sessions() (runtime.py)
          │
          ▼
    GET /v1/sessions, GET /v1/sessions/{thread_id}  (NEXUS API)
          │
          ▼
    NEXUS Console: Sessions page → Session Detail (state/message
    inspector, not a second chatbot -- the Playground remains the
    only execution surface)

The Dashboard is implemented in Phase 6.8. Broader metrics remain future work. Phase 6.7 provides
factual run comparison and a guarded fresh re-run for eligible first-turn runs; this is not
deterministic replay.

The Console must NEVER manipulate LangGraph directly.

The API is the application boundary.

NexusRuntime is the execution boundary.

LangGraph is an orchestration implementation detail behind the runtime.

---

# 4. Important Architectural Principle

Keep these boundaries explicit:

    NEXUS Console
        ↓
    NEXUS API
        ↓
    NexusRuntime
        ↓
    LangGraph
        ↓
    Agents / Tools

Do not allow:

    Console → LangGraph

Do not allow:

    API endpoint → arbitrary LangGraph node

Do not allow:

    LLM → authorization decision

Do not allow:

    Agent → unrestricted tool execution

The runtime should remain the central execution abstraction.

---

# 5. Existing Agents

The current reference workloads are:

- emotional / counselor
- logical
- math
- coding

These agents are intentional.

Do not remove them simply because NEXUS is becoming a platform.

They serve two purposes:

1. They demonstrate that NEXUS can orchestrate heterogeneous agents.
2. They provide reference workloads for testing, evaluation, and the
   future Agent Playground.

Agents should remain individually testable.

The automatic routing path should also remain supported.

Conceptually:

    User input
       ↓
    Classifier
       ↓
    Router
       ↓
    Specialist agent

The future NEXUS Console should eventually allow:

- automatic routing
- direct agent selection
- "Test Agent"

---

# 6. Agent Definition

An agent should conceptually be treated as:

    Agent =
        LLM
        + Tools
        + State
        + Control Flow

An LLM by itself is not an agent.

Do not describe ordinary LLM calls as agents unless they participate
in an execution/control-flow model.

---

# 7. LangGraph Mental Model

Use:

    State = information
    Node  = work
    Edge  = control flow

LangGraph provides orchestration.

It should not become the public product abstraction.

NexusRuntime should hide LangGraph-specific implementation details
from API consumers wherever practical.

---

# 8. MCP Mental Model

MCP is a tool/resource integration protocol.

Conceptually:

    Host/Application
          ↓
        Client
          ↓
        MCP
          ↓
        Server
          ↓
    Tools / Resources / Prompts
          ↓
      External systems

Important:

- Tool = action
- Resource = information
- Prompt = reusable prompt/template

MCP does NOT solve:

- authentication
- authorization
- SSRF
- prompt injection
- data governance
- audit requirements

Those remain NEXUS responsibilities.

Do not treat MCP as a security boundary.

---

# 9. Security Principles

Security is a first-class architecture concern.

The following rules are mandatory.

## 9.1 LLM is not a security boundary

Never rely on model instructions for:

- authorization
- identity
- permissions
- tool access
- data access

Security decisions must be deterministic and external to the model.

---

## 9.2 Authentication vs Authorization

Authentication answers:

    Who is this caller?

Authorization answers:

    Is this caller allowed to perform this action?

Do not confuse the two.

---

## 9.3 Least privilege

Agents should receive only the tools they need.

Tool access must be controlled by deterministic policy.

Never allow the model to invent or elevate its own permissions.

---

## 9.4 Tool authorization

Tool authorization happens before tool execution.

The tool policy must be enforced independently of the model's output.

---

## 9.5 SSRF

The secure fetch implementation must maintain protections including:

- HTTPS-only by default
- credential rejection
- malformed URL rejection
- DNS/IP validation
- private IP blocking
- loopback blocking
- link-local blocking
- multicast blocking
- cloud metadata address blocking
- exact domain allowlisting
- redirect revalidation
- response-size limits
- request timeouts

Do not weaken existing SSRF protections.

When modifying networking code, add regression tests.

---

## 9.6 Prompt injection

External content must be treated as untrusted.

Do not assume retrieved web/tool content is trustworthy.

Prompt injection is mitigated, not solved.

Do not make claims that NEXUS "eliminates" prompt injection.

---

## 9.7 Secrets

Never:

- print API keys
- log Authorization headers
- commit credentials
- include secrets in test fixtures
- expose environment variables through API responses
- put secrets into observability events

Be especially careful with:

- `.env`
- exception messages
- HTTP headers
- tool payloads
- structured logs
- SSE events

---

# 10. Observability

NEXUS uses structured observability.

Important lifecycle events include:

- workflow_started
- classifier_started
- classifier_completed
- route_selected
- agent_started
- agent_completed
- tool_started
- tool_completed
- tool_denied
- tool_failed
- workflow_completed
- workflow_failed

Every event should have appropriate correlation information such as:

- request_id
- thread_id
- timestamp

Do not add event types unnecessarily.

Prefer extending event metadata over creating duplicate event systems.

---

# 11. Run / Trace Model

A run represents one execution.

A run may expose:

- request_id
- thread_id
- status
- route
- classification
- timestamps
- duration
- events
- tool activity
- token usage
- cost when available
- safe error information

Do not expose sensitive content merely because it is available internally.

---

# 12. Replay Terminology

Be precise.

### Run

One execution.

### Re-run

Execute the same input again.

### Replay

Reproduce a previous execution using recorded model/tool inputs and
outputs.

NEXUS supports evaluation re-runs and the Phase 6.7 first-turn Console re-run.

Do NOT claim deterministic replay unless the system actually records
everything required for deterministic replay.

---

# 13. Evaluation

Evaluation is part of the platform.

Evaluation must use the same NexusRuntime execution boundary as normal
runtime traffic.

Conceptually:

    Evaluation Dataset
          ↓
    Evaluation Runner
          ↓
      NexusRuntime
          ↓
     Agent execution
          ↓
     Run / Trace Store
          ↓
       Metrics
          ↓
    Evaluation Result

The evaluator must not call LangGraph nodes directly.

---

# 14. Evaluation Principles

Current evaluation is deliberately deterministic.

Supported dimensions include:

- routing correctness
- execution success
- tool usage
- response checks
- latency
- token usage
- cost when available

Do not introduce an LLM-as-judge casually.

Do not treat an LLM judge as inherently objective.

Evaluation should never fabricate:

- token counts
- cost
- latency
- success

If information is unavailable, represent it as unavailable/null.

---

# 15. Cost Tracking

Cost is only valid when:

1. provider token usage is available
2. pricing is configured

Pricing comes from operator configuration.

Never guess provider pricing.

Never silently estimate cost.

If usage or pricing is unavailable:

    cost = null

---

# 16. State vs Memory

Do not confuse state and memory.

State is information required by an active workflow/thread.

Memory is information deliberately retained for future interactions.

Current NEXUS primarily implements durable thread/workflow state.

Do not claim that NEXUS has a sophisticated long-term memory system
unless one has actually been implemented.

---

# 17. Reliability Principles

Use the following mental model:

    R-S-R-O-G

    Reliability
    Security
    Scalability
    Observability
    Governance

When implementing platform features, consider all five.

Common reliability mechanisms include:

- bounded retries
- timeouts
- graceful fallback
- validation
- circuit breaking where appropriate
- failure isolation
- idempotency where appropriate

Never add retries blindly.

Retries must be limited and appropriate to the failure type.

---

# 18. API Principles

The API is the stable application boundary.

The API should:

- use typed request/response models
- use consistent errors
- validate input
- enforce authentication
- enforce authorization
- enforce rate limits
- avoid leaking internal exceptions
- correlate requests with request_id
- expose safe observability information

Do not expose LangGraph implementation details unnecessarily.

---

# 19. Runtime Principles

NexusRuntime is the primary execution abstraction.

Prefer:

    NexusRuntime.execute(...)

over direct calls to graph nodes.

The runtime owns concerns such as:

- graph execution
- thread/session context
- checkpointing
- access checks
- execution correlation

The API should call the runtime.

The CLI should call the runtime.

The evaluation system should call the runtime.

This creates one execution path.

---

# 20. Persistence

Distinguish:

### Durable state

State that must survive:

- process restart
- API restart
- potentially multiple instances

Examples:

- LangGraph checkpoints (SQLite: single-process durable; PostgreSQL,
  Phase 5: durable and cross-process-safe)
- durable thread ownership metadata where implemented (PostgreSQL
  backend only - see `access.PostgresAccessStore`)

### Process-local state

Temporary state that may disappear on restart, and is NOT shared across
multiple API instances regardless of which checkpointer backend is
active.

Examples currently include:

- bounded RunStore
- bounded EvaluationStore
- process-local rate limiter
- in-memory ThreadAccessRegistry (the SQLite-backend default)

Do not claim process-local data is durable.

---

# 21. Phase History

## Phase 0 - Correctness & Hardening

Established:

- typed routing
- latest-turn semantics
- model configuration
- timeouts
- bounded retries
- fallback handling
- CLI robustness
- MCP startup degradation
- initial test coverage

---

## Phase 1 - Runtime & Observability

Established:

- NexusRuntime
- persistent thread state
- request IDs
- structured events
- observability
- thread isolation
- restart/resume

---

## Phase 2 - Security & Tool Governance

Established:

- secure native fetch
- SSRF protections
- URL validation
- domain allowlisting
- tool authorization
- untrusted-content handling
- thread access boundary
- security documentation

---

## Phase 3 - NEXUS API

Established:

- FastAPI
- session endpoints
- message endpoint
- run endpoint
- health/readiness
- OpenAPI
- safe errors
- runtime lifecycle

---

## Phase 4 - Evaluation & Advanced Observability

Established:

- deterministic evaluation framework
- evaluation datasets
- routing evaluation
- execution evaluation
- tool evaluation
- response evaluation
- latency metrics
- token metrics
- configurable cost tracking
- evaluation comparison
- shared RunStore
- richer run API
- evaluation API

---

## Phase 5 - Production Runtime & Security

Established:

- bearer-token authentication (`auth.py`), enforced at the API boundary
  before any route handler runs
- authorization checked against the authenticated caller for sessions,
  runs, and evaluations (`access.py`)
- a bounded, per-principal, process-local rate limiter (`rate_limit.py`)
- SSE execution streaming (`POST /v1/sessions/{thread_id}/messages/stream`),
  reusing the existing observability event vocabulary
- an optional PostgreSQL backend for durable, cross-process checkpoint
  and thread-ownership state (`access.PostgresAccessStore`,
  `AsyncPostgresSaver`), alongside the unchanged SQLite default
- DNS-rebinding-resistant `fetch` connections (IP-pinned via a custom
  httpcore network backend), closing the TOCTOU gap Phase 2 documented
  but did not fix
- centralized, validated startup configuration (`config.py`)
- an explicit multi-instance analysis: PostgreSQL makes checkpoint state
  and thread ownership cross-process-safe; `RunStore`, `EvaluationStore`,
  and the rate limiter remain process-local regardless of backend

Current verified baseline (after Phase 5): **283 tests passing, 4 skipped**
(PostgreSQL integration tests - skipped because no PostgreSQL instance
was available in that environment, not faked).

Do not assume this number remains unchanged.
Always run the suite.

---

## Phase 6.1 - NEXUS Console: Agent Playground + Live Execution Trace

Established:

- a real TypeScript/React/Vite frontend (`frontend/`) - a pure HTTP/SSE
  client of the existing API, never LangGraph, never duplicating runtime
  logic
- real runtime status (polled `GET /health`, not hardcoded)
- Auto Route vs. direct-agent execution mode in the UI
- a real NEXUS session, reused across messages in one Playground load
- a dedicated SSE client (`frontend/src/lib/sseClient.ts`) - hand-rolled,
  since browser `EventSource` cannot send a POST body or an
  `Authorization` header
- a live execution trace, reduced from real SSE events as they arrive
  (`frontend/src/lib/traceReducer.ts`, pure and unit-tested), not
  rendered after the fact from the final response
- the real final response and real run metadata (tokens/cost shown as
  "Not reported," never invented, when the backend didn't return them)
- polished, safe error states built from the API's existing
  `{"error": {"code", "message"}}` shape
- backend: `main.py`'s `DIRECT_AGENT_GRAPH_BUILDERS` (four minimal
  classifier-free graphs reusing the existing node functions - a state
  field was deliberately not used to signal "skip the classifier," since
  that would leak across turns on a checkpointed thread) and
  `NexusRuntime.execute(..., agent=...)`, both additive and optional
  (`agent=None` is byte-for-byte the same behavior as Phase 5)
- backend: CORS middleware (`api.py`, `NEXUS_CONSOLE_ORIGINS`) - a real
  defect found only by running the real Console against the real API in
  a real browser; curl/httpx-based tests structurally cannot catch this
  (see Section 25's "Development Workflow" for why live verification in
  the actual client environment is not optional)

Current verified baseline (after Phase 6.1): backend **306 tests passing,
4 skipped**; frontend **72 tests passing** (separate suite, Vitest -
`cd frontend && npm test`).

Do not assume either number remains unchanged.
Always run both suites.

---

## Phase 6.2 - NEXUS Console: Agent Registry + Test Agent

Established:

- a new top-level `agents.py`: `AgentDefinition` (Pydantic) - id, name,
  description, status, execution_mode, tools, capabilities, tags,
  version. Deliberately excludes system prompts, model/provider
  configuration, API keys, and any other internal detail (see
  SECURITY.md)
- `list_agents()`/`get_agent()` backing two new endpoints,
  `GET /v1/agents` and `GET /v1/agents/{agent_id}`, in the same
  auth/rate-limit dependency chain (`Depends(enforce_rate_limit)`) as
  every other endpoint - never public/unauthenticated
- `is_executable()` - the registry is now the authoritative allowlist for
  direct-agent execution: `api.py`'s `MessageRequest.agent` validator
  calls it before a turn can reach `NexusRuntime.execute()`/graph
  construction, so an unknown or unavailable agent id is rejected with
  `400 INVALID_REQUEST` at the API boundary, never at graph-build time
- `status` is computed, not hardcoded - `logical`'s reflects whether
  `main.logical_react_agent` was actually constructed; `tools` is read
  from the same `tool_policy.AGENT_TOOL_POLICY` the runtime itself
  enforces, never a second, driftable list
- a Console Agents page (`/agents`) rendering the real registry as cards,
  and an agent detail view (`/agents/:agentId`) - both built on
  `src/hooks/useAgentRegistry.ts`/`useAgent.ts`, never a hardcoded list
- a "Test Agent" flow that is navigation, not a second execution
  mechanism: `<Link to="/playground?agent=<id>">` into the *existing*
  Playground. No new message composer, SSE client, session-creation
  path, or execution state was added
- `usePlaygroundExecution.ts` gained an optional `initialAgentId`
  parameter and now owns the agent-registry fetch; an unknown or
  unavailable `?agent=` id falls back to Auto Route with a visible
  notice, never a silent failure or an invented agent
- `AgentModeSelector`, `AgentGrid`, and `RouteVisualization` (Phase 6.1)
  now take `agents: Agent[]` as a required prop instead of importing a
  hardcoded list; `types/agent.ts` no longer hardcodes a static agent
  array

Current verified baseline (after Phase 6.2): backend **342 tests
passing, 4 skipped**; frontend **99 tests passing** (`cd frontend && npm
test`).

Do not assume either number remains unchanged.
Always run both suites.

---

## Phase 6.3 - NEXUS Console: Runs + Run Detail

Established:

- `run_store.py`: `RunEvent` gained a `route` field (populated only on
  `route_selected`); `RunRecord` gained an `agent` field via a new
  `_extract_agent()` helper, reading the one `agent_started` event's
  `node` - populated for BOTH Auto Route and Direct Agent runs, unlike
  `route`, which stays null for a direct-agent run; `RunStore` gained
  `list_recent()`, returning the bounded store's contents
  most-recently-recorded-first
- `runtime.py`: `NexusRuntime.owner_of(thread_id)` - a read-only
  ownership lookup, deliberately distinct from `verify_access`/
  `require_access`, which has a first-touch *claiming* side effect. A
  list endpoint checking many candidate runs' ownership must never risk
  silently claiming a thread it only enumerated
- `api.py`: a new `GET /v1/runs` (list, most recent first, optional
  `limit`/`status`/`agent`/`route` filters, same auth/rate-limit chain as
  every other endpoint) - a run whose thread isn't owned by the caller is
  silently excluded, never surfaced via a 403 or any other signal that it
  exists. `GET /v1/runs/{request_id}` gained additive `response` (the
  final reply - `RunRecord.reply` already existed, just wasn't exposed
  here) and `agent` fields
- the Playground's live-trace pipeline is now shared, not duplicated:
  `lib/runToTrace.ts` (new) reshapes a stored `RunResponse` into the same
  `NexusEvent[]` shape SSE produces, plus one synthesized `run_completed`
  event mirroring what `api.py`'s SSE endpoint already appends, then
  folds it through the SAME `reduceTraceEvents` (`traceReducer.ts`,
  unmodified since Phase 6.1). `RunDetailPage.tsx` renders the result
  with the SAME `ExecutionTrace`/`FinalResponse` components the
  Playground uses - neither component knows or cares whether its data
  came from live SSE or a stored run
- a Console Runs page (`/runs`): a dense table (status, agent, route,
  request ID, time, duration, tokens, cost), server-side status/agent
  filtering, client-side search/sort (the bounded store is small enough
  that this is appropriate, not a shortcut), and a Run Detail view
  (`/runs/:requestId`) with a metadata summary and the reused trace
- `src/hooks/useRuns.ts`/`useRun.ts`, following the same
  loading/ready/error(/not_found) pattern as `useAgentRegistry.ts`/
  `useAgent.ts`; a new shared `components/CopyButton.tsx` for
  request/thread IDs
- deliberately NOT built: re-run/replay (the original user message text
  is never persisted anywhere - observability events never carry
  content, by design - so there is no input to re-run with), a separate
  route filter (the new `agent` field already subsumes it), and any
  "running" status in the list (`RunStore.record()` only ever runs after
  a turn completes or fails)

Current verified baseline (after Phase 6.3): backend **366 tests
passing, 4 skipped**; frontend **132 tests passing** (`cd frontend && npm
test`).

Do not assume either number remains unchanged.
Always run both suites.

---

## Phase 6.4 - NEXUS Console: Sessions + State Explorer

Established:

- `runtime.py`: `NexusRuntime.list_sessions(principal_id, limit=, scan_limit=)` -
  discovers this principal's sessions directly from the checkpointer's
  own `alist(None)`, most recently updated first. NOT a second
  persistence layer: `checkpoint["channel_values"]`/`checkpoint["ts"]`
  are the exact same underlying data `get_state()`'s `StateSnapshot.
  values`/`.created_at` are built from. A new `SessionSnapshot`
  dataclass; a new `DEFAULT_SESSION_SCAN_LIMIT` constant
  (`NEXUS_SESSION_SCAN_LIMIT`, default 2000) bounding how many raw
  checkpoint entries are scanned - a session outside that window won't
  appear in the list (still fully readable directly by thread_id), the
  same honest bound `RunStore` already has
- ownership reuses Phase 6.3's read-only `owner_of()` - `list_sessions`
  must never have `verify_access`'s first-touch claiming side effect
  merely from scanning past a thread it doesn't own
- `api.py`: a new `GET /v1/sessions` (list, same auth/rate-limit chain
  as every other endpoint) - a session whose thread isn't owned by the
  caller is silently excluded, never surfaced via a 403 or any other
  signal that it exists. `GET /v1/sessions/{thread_id}` gained an
  additive `messages` field (full history, role/content only, oldest
  first) - `null` (not `[]`) in list results, which never fetch content
- `GET /v1/runs` gained an additive `thread_id` filter - the backend half
  of Session → Runs navigation (`/runs?thread_id=<id>`)
- a Console Sessions page (`/sessions`) rendering real session state as
  a table, and a Session Detail view (`/sessions/:threadId`) with a
  metadata summary and message history - both built on
  `src/hooks/useSessions.ts`/`useSession.ts`, never a hardcoded or
  fabricated list
- message content is rendered as a plain React text node only
  (`SessionMessageList.tsx`) - never `dangerouslySetInnerHTML`, never
  markdown-parsed; there is no markdown renderer anywhere in this
  codebase, and this phase does not add one
- cross-navigation without duplicating anything: Run Detail's "View
  Session", Session Detail's "View Runs" (reads `?thread_id=` in the
  *existing* `RunsPage.tsx`, not a second Runs surface), and the
  Playground's "View Session" (shown only once a turn has actually
  completed, since session creation alone writes no checkpoint yet)
- **RUN and SESSION remain distinct** (Section 16): a run is one
  execution; a session is persistent thread/workflow *state*, not
  long-term memory. No semantic/vector memory system was added

Historical verified baseline after Phase 6.4 and before Phase 6.5: backend
**389 tests passing, 4 skipped**; frontend **159 tests passing**. Current
counts are recorded after Phase 6.5 verification below.

Do not assume either number remains unchanged.
Always run both suites.

---

# 22. Phase 5 - Status: COMPLETE

Phase 5 was:

    Production Runtime & Security

Objectives achieved:

- authentication
- authorization
- rate limiting
- SSE
- PostgreSQL/durable runtime state (dispatch verified deterministically;
  full live integration environment-dependent - see Section 21)
- multi-process analysis
- stronger SSRF/DNS-rebinding protection
- production-oriented configuration

Phase 5 did NOT include the GUI, by design.

Known residual limitations carried forward (see README.md "Known
limitations" and SECURITY.md for full detail): authentication supports a
single configured bearer token (no per-user accounts/OAuth/SSO/RBAC); the
rate limiter and RunStore/EvaluationStore are process-local even when the
PostgreSQL backend is active; no deterministic replay; no LLM-as-judge;
the PostgreSQL backend was not verified against a live database in the
development environment (no PostgreSQL/Docker available there); on
Windows, `psycopg`'s async mode requires a `SelectorEventLoop`
(`ProactorEventLoop`, Windows' default, is incompatible) - not an issue
on Linux/macOS.

Phase 6.1 through Phase 6.8 (see above and below) are implemented. Further
Console work requires an explicitly scoped request - see Section 23 and Section 41.

---

# 23. Future Phase - NEXUS Console (remaining sections)

The Console is called:

    NEXUS Console

It consumes the NEXUS API only.

It does NOT directly manipulate LangGraph.

**Phase 6.1 is complete** (Agent Playground + live execution trace),
**Phase 6.2 is complete** (Agent Registry, Agents page, Test Agent flow),
**Phase 6.3 is complete** (Runs page + Run Detail, reusing the
Playground's trace pipeline), **Phase 6.4 is complete** (Sessions page +
Session Detail, a state explorer distinct from Runs), and **Phase 6.5 is
complete** (Evaluations history, synchronous baseline execution, detail,
metrics, case results, and comparison using the existing API), and
**Phase 6.6 is complete** (read-only Tools/governance registry and retained
activity using the existing tool policy and RunStore). The areas below are
what remain:

- Dashboard
- Metrics
- Governance
- Run comparison
- Replay/re-run

Do not re-build the Playground, execution trace, Agent Registry, Runs
history, Sessions explorer, or Evaluations experience from scratch for a later sub-phase -
extend `frontend/src/features/playground/`,
`frontend/src/features/agents/`, `frontend/src/features/runs/`,
`frontend/src/features/sessions/`, `frontend/src/features/evaluations/`, and
`frontend/src/lib/` in place;
they were built to be extended (see ARCHITECTURE.md's "NEXUS Console
(Phase 6.1)", "NEXUS Console (Phase 6.2: Agent Registry)", "NEXUS
Console (Phase 6.3: Runs + Run Detail)", and "NEXUS Console (Phase 6.4:
Sessions + State Explorer)" sections). The Test Agent flow must continue
to navigate into the existing Playground - do not add a second
execution surface for a future Console section either. The Playground's
trace reducer (`traceReducer.ts`) must remain the single source of
trace-rendering logic - a future section needing to display execution
events should reshape its data into `NexusEvent[]` and reuse it (see
`lib/runToTrace.ts` for the pattern), not build a second trace renderer.
Sessions is the counterexample that proves this rule has a boundary: it
displays persisted *state* (messages/route/classification), not an
execution trace, so it deliberately does NOT use `traceReducer.ts` -
don't force a future state-oriented section through the trace pipeline
just because Runs and Playground both use it. Do not implement long-term
or semantic memory for any future section - see Section 16.

The desired visual direction is:

- premium
- dark developer-console aesthetic
- technically sophisticated
- information-dense but readable
- polished
- animated where meaningful
- closer to Linear / Vercel / Datadog than a generic chatbot

The Console should visualize real runtime data.

Do not build fake dashboards disconnected from actual NEXUS execution.

The Console will need to authenticate against the Phase 5 API
(`NEXUS_API_TOKEN` bearer auth) and should be designed with a future
multi-user credential model in mind, even though only a single configured
token is supported today - do not hardcode assumptions that break when
real user accounts are eventually added.

---

# 24. Agent Playground - DELIVERED (Phase 6.1)

The Console's Playground supports both modes this section originally
specified as future work - both now real, both live-verified:

### Automatic routing (unchanged backend behavior)

    User input
       ↓
    Classifier
       ↓
    Router
       ↓
    Agent

### Direct agent testing (Phase 6.1 addition)

    User
      ↓
    Selected Agent          <- classifier and router do not run
      ↓
    Execution

Implemented via `main.py`'s `DIRECT_AGENT_GRAPH_BUILDERS` and
`NexusRuntime.execute(..., agent=...)` - see the Phase History entry
above and ARCHITECTURE.md's "NEXUS Console (Phase 6.1)" section for why
a state field was deliberately not used for this.

The four reference agents:

- logical
- coding
- math
- counselor

are all available in both modes, exactly as this section originally
specified.

**Phase 6.2 update**: which agent ids are valid for direct execution is
no longer a hardcoded `Literal` type on `MessageRequest.agent` - it is
now delegated to `agents.is_executable()`, the Agent Registry's
allowlist (see Section 21's Phase 6.2 entry and ARCHITECTURE.md's "NEXUS
Console (Phase 6.2: Agent Registry)" section). The execution mechanism
itself (`DIRECT_AGENT_GRAPH_BUILDERS`, `NexusRuntime.execute(...,
agent=...)`) is unchanged.

**Phase 6.3 update**: the live execution trace this section describes is
no longer the only way to see one - a completed run's trace is now also
viewable after the fact, via the Runs page (`/runs/:requestId`). This is
NOT a second trace implementation: `lib/runToTrace.ts` reshapes a stored
`GET /v1/runs/{request_id}` response into the same event shape
`traceReducer.ts` already consumes, then renders it with the exact same
`ExecutionTrace`/`FinalResponse` components. A direct-agent run's stored
trace still shows no classifier/route step, for the same structural
reason the live one doesn't (see Section 21's Phase 6.3 entry and
ARCHITECTURE.md's "NEXUS Console (Phase 6.3: Runs + Run Detail)"
section). **Durable rule**: any future Console section that needs to
display execution events must reuse `traceReducer.ts` via this same
reshape-then-fold pattern, not build a second trace renderer.

---

# 25. Development Workflow

When implementing a phase:

1. Inspect the repository.
2. Read the relevant architecture/security documentation.
3. Run the existing tests.
4. Understand the installed package versions.
5. Make the smallest coherent architectural change.
6. Add tests with the implementation.
7. Run targeted tests.
8. Run the complete suite.
9. Perform real runtime/API verification.
10. Clean temporary artifacts.
11. Update documentation.
12. Report actual results.

Never report tests as passing unless they were actually executed.

Never fabricate live verification.

**Live verification must use the real client environment, not just
`curl`/`httpx`.** Phase 6.1 shipped a browser-based frontend; the entire
existing backend test suite (and an early round of manual `curl` checks)
passed cleanly while the Console itself reported "Runtime Offline,"
because the API had no CORS headers - a restriction only browsers
enforce. The defect was invisible to every tool used until the actual
Console was opened in an actual browser. When a phase adds a new kind of
client (a browser, a mobile app, a CLI in a different language, ...),
verify with that actual client, not a proxy for it that happens to skip
the constraints real clients are subject to.

---

# 26. Dependency Discipline

Before adding a dependency:

1. Determine whether an existing dependency already solves the problem.
2. Check the installed version.
3. Inspect the actual API.
4. Prefer minimal dependencies.
5. Add tests.
6. Update dependency manifests.

Do not introduce dependencies merely because they are popular.

Do not assume documentation for a different version matches the installed
version.

---

# 27. Coding Style

Prefer:

- explicit types
- small modules
- clear interfaces
- dependency injection where useful
- deterministic behavior
- focused functions
- descriptive names
- minimal global state
- defensive error handling

Avoid:

- giant functions
- hidden side effects
- unnecessary abstractions
- duplicated execution paths
- magic configuration
- silent fallbacks that hide serious failures

Do not rewrite working code solely for stylistic preference.

---

# 28. Testing Standards

Tests should cover:

- happy paths
- validation failures
- authentication failures
- authorization failures
- tool denial
- tool failures
- network failures
- provider failures
- timeout behavior
- persistence
- thread isolation
- request correlation
- observability
- secret leakage
- API behavior

Tests involving external providers should not be required for the core
test suite.

CI must be able to run without real API credentials.

---

# 29. External Provider Rules

Real LLM calls are optional for tests.

Never make the test suite dependent on:

- Anthropic credentials
- OpenAI credentials
- external MCP servers
- arbitrary websites

Use mocks/fakes for deterministic tests.

Live provider tests must be explicitly invoked.

Never replace credentials without explicit instruction.

Never print credentials.

---

# 30. Error Handling

Errors should be:

- explicit
- typed where practical
- safe for external exposure
- observable internally
- actionable for developers

External API responses should not expose:

- raw stack traces
- provider credentials
- authorization headers
- internal secrets

Observability should contain safe error types rather than raw exception
objects.

---

# 31. Documentation Standards

When architecture changes, update:

- README.md
- ARCHITECTURE.md
- SECURITY.md where security is affected
- this CLAUDE.md if the engineering rules or architecture materially
  change

Documentation must reflect the actual implementation.

Do not document future functionality as if it already exists.

Clearly distinguish:

- implemented
- partially implemented
- planned
- intentionally out of scope

---

# 32. Git Discipline

Use focused commits.

Preferred style:

    feat: ...
    fix: ...
    docs: ...
    test: ...
    refactor: ...

For major phases, a phase-level commit may be appropriate.

Do not commit:

- .env
- API keys
- temporary databases
- logs
- caches
- generated secrets
- local development artifacts

Always inspect:

    git status

before finalizing a phase.

---

# 33. Security Incident Rule

If you discover a real credential or secret in the repository:

1. Do not reproduce it in output.
2. Do not commit it.
3. Do not move it into another file.
4. Identify the affected file safely.
5. Recommend rotation/revocation.
6. Remove it from tracked content where appropriate.
7. Check git status/history implications.

Never paste the secret into a report.

---

# 34. Architecture Decision Rule

Before making a major architectural change, ask:

1. What problem does this solve?
2. Which existing boundary should own the solution?
3. Does it preserve NexusRuntime as the execution boundary?
4. Does it preserve deterministic security?
5. Does it preserve testability?
6. Does it introduce unnecessary infrastructure?
7. Is it actually needed in the current phase?

Prefer the smallest architecture that supports the current product goal.

---

# 35. Do Not Overbuild

NEXUS is intentionally being built incrementally.

Do not implement future phases early.

If a task belongs to a later phase, document it as future work rather
than silently implementing it.

Examples:

- GUI → Phase 6
- deployment → Phase 7
- marketplace → future
- billing → future
- full multi-tenancy → future
- deterministic replay → future
- distributed tracing → future

A smaller, coherent implementation is preferable to a sprawling
unfinished platform.

---

# 36. Product Positioning

NEXUS should be described as:

    AI Agent Runtime & Orchestration Platform

Possible conceptual positioning:

    Build → Run → Observe → Evaluate → Govern

Do not position NEXUS as:

- a generic chatbot
- a single-purpose agent
- a company-specific internal tool
- a collection of unrelated demos

The four current agents are reference workloads inside the platform.

---

# 37. Important Technical Mental Models

Remember:

    LLM
      = reasoning/generation

    RAG
      = retrieval/grounding

    Tool
      = external action

    Agent
      = LLM + tools + state + control flow

    LangGraph
      = orchestration

    MCP
      = integration protocol

    NEXUS
      = runtime + orchestration + tools + security +
        observability + evaluation + governance

Another useful model:

    LangGraph = orchestrate
    MCP       = connect
    RAG       = retrieve
    LLM       = reason/generate
    NEXUS     = govern the execution

---

# 38. Engineering Philosophy

NEXUS should demonstrate engineering judgment, not just framework
knowledge.

Prioritize:

- reliability
- security
- observability
- testability
- maintainability
- explicit boundaries
- measurable behavior

A feature is not complete merely because it works in the happy path.

For every significant feature consider:

- failure mode
- timeout
- security implications
- observability
- test strategy
- persistence implications
- concurrency implications
- future API/GUI consumption

---

# 39. Claude Code Role

Claude Code is an implementation accelerator.

The architecture and engineering decisions should remain explicit.

When working on NEXUS:

- inspect before modifying
- explain significant architectural decisions
- do not blindly accept generated abstractions
- verify behavior through tests
- verify important behavior at runtime
- preserve existing boundaries
- do not invent unsupported APIs
- inspect installed library versions

Code generation speed is not a substitute for engineering validation.

---

# 40. Definition of Done

A feature is not done when code has been written.

For a meaningful feature, "done" generally means:

    Code
      +
    Tests
      +
    Runtime verification
      +
    Security review
      +
    Observability
      +
    Documentation

If one of these is intentionally omitted, explicitly state why.

---

# 41. Current Priority

Phase 5 (Production Runtime & Security) is **complete** - see Section 22.

Phase 6.1 (NEXUS Console: Agent Playground + Live Execution Trace) is
**complete** - see the Phase History entry above Section 22, and
Sections 23-24.

Phase 6.2 (NEXUS Console: Agent Registry + Test Agent) is **complete** -
see the Phase History entry above Section 22.

Phase 6.3 (NEXUS Console: Runs + Run Detail) is **complete** - see the
Phase History entry above Section 22.

Phase 6.4 (NEXUS Console: Sessions + State Explorer) is **complete** -
see the Phase History entry above Section 22.

Phase 6.5 (NEXUS Console: Evaluations) is **complete** - see Section 42.

Phase 6.6 (NEXUS Console: Tools / Governance) is **implemented; browser verification remains blocked by the local browser renderer** - see Section 43.

Phase 6.7 (NEXUS Console: Run Comparison + Re-run) is **implemented; automated verification complete** - see Section 44.

Phase 6.8 (NEXUS Console: Dashboard + Console Polish) is **implemented; automated verification complete** - see Section 45.

Phase 7 (Production Packaging) is **implemented; not yet live-verified** - see Section 46. A
backend Dockerfile, a frontend Dockerfile, a local Compose stack (PostgreSQL + API + Console), and
a GitHub Actions CI workflow all exist and were statically reviewed (YAML validated, the api
service's environment substitution logic specifically checked for a bug that was found and fixed
before being reported as done, the repository-hygiene scans dry-run against the real working tree).
None of the image builds, the Compose stack, or live PostgreSQL behavior have been executed in this
development environment, which has neither Docker nor a local PostgreSQL installation - see Section
46 for the exact boundary between what was authored/reviewed and what remains genuinely unverified.

The immediate priority is now:

    No additional Console phase is currently in scope. The first real Docker/CI environment
    should be used to observe the Phase 7 CI workflow actually running, and to perform the
    live PostgreSQL validation this development environment could not.

Extend the existing `frontend/` application only when the user explicitly scopes further work, on top of the stable API and
runtime created by Phases 0-5 and the Console foundation (API client,
SSE client, trace model/reducer, component/state patterns, the Agent
Registry, Runs, Sessions, Evaluations, and Tools) established in Phase 6.1-6.6. Do not
re-scaffold the frontend or duplicate `lib/apiClient.ts`/`lib/sseClient.ts`/
`lib/traceReducer.ts`; do not build a second agent listing, a second
execution surface, or a second trace renderer alongside
`features/agents/`, `features/playground/`, `features/runs/`,
`features/sessions/`, and `features/evaluations/`.

Do not prematurely build later Console sections before explicitly asked
to - "complete" above refers only to each phase's own stated scope, not
a signal to keep going without instruction. The same applies to Phase 7: do not begin cloud
deployment, TLS/reverse-proxy configuration, or a distributed rate limiter/RunStore without an
explicit, separately scoped request.

---

# 42. Phase 6.5 - NEXUS Console: Evaluations

Phase 6.5 is complete. It adds an ownership-filtered `GET /v1/evaluations` list endpoint and a
Console history and detail experience at `/evaluations` and `/evaluations/:evaluationId`.

- The list endpoint uses the same authentication and rate-limit dependency chain as other API
  resources. It returns lightweight summaries for the authenticated principal only, newest
  recorded first, with a bounded `limit` from 1 through 200. Missing, unowned, and evicted
  evaluations remain undiscoverable and detail retrieval remains a safe 404.
- Evaluation history remains in the existing bounded, process-local `EvaluationStore`, capped by
  `NEXUS_EVALUATION_STORE_SIZE` (default 100). It resets when the API process restarts and is not
  shared between processes, including when PostgreSQL stores checkpoint state.
- Running the baseline uses the existing synchronous `POST /v1/evaluations` and the same
  `NexusRuntime` execution boundary. The Console disables repeat submission during the request and
  explains that no streaming progress is available. It navigates to the returned evaluation on
  completion and renders safe API errors on failure.
- Detail reads the existing summary, per-case results, and metrics endpoints. It renders the actual
  case response and deterministic dimension outcomes, then links each case's existing
  `request_id` to Run Detail. The comparison view calls the existing comparison endpoint and labels
  deltas neutrally as B minus A; it does not select a winner.
- Null token/cost values and absent optional rates are displayed as unavailable. No values are
  inferred. No new trace representation, execution path, persistence backend, or authentication
  system was introduced.
- The Console remains an API client: its API calls live in `lib/apiClient.ts`, state orchestration
  lives in `hooks/useEvaluations.ts`, and presentation lives under `features/evaluations/`.

Verification after Phase 6.5: backend **398 passed, 4 skipped**; frontend **172 passed across 25 test
files**; production build succeeded. Chrome exercised the real API and Console at desktop, 900px,
and 480px widths with no document-width overflow or captured runtime exceptions. Two real baseline
requests returned HTTP 201 and two real IDs compared with HTTP 200. Both evaluations completed with
1 of 5 cases passing and 4 failing; returned run records had `APIConnectionError`. No live provider
success is claimed. Token and cost values were unavailable and remained so in the UI.

Later work remains Dashboard and broader metrics; see Section 23. Phase 6.7 adds run comparison
and a guarded fresh re-run for eligible first-turn input. It does not add deterministic replay.

---

# 43. Phase 6.6 - NEXUS Console: Tools / Governance

Phase 6.6 implements a read-only Tools page backed by `GET /v1/tools` and
`GET /v1/tools/activity`.

- Tool identity and description come from the tool definitions bound to the Logical agent. Public
  allowed agents are derived from `tool_policy.AGENT_TOOL_POLICY`; the active status means a tool
  is bound to at least one currently callable supported agent graph. The current `fetch` tool is a
  native NEXUS implementation.
- Tool control descriptions summarize enforced behavior only. They do not expose configuration
  values, private allowlist entries, addresses, or connection details.
- Activity projects completed, denied, and failed events from the existing bounded `RunStore`.
  Each event is associated with the parent run's agent and includes the request ID for Run Detail
  navigation. The API filters activity through `NexusRuntime.owner_of()` and does not expose
  thread IDs or payloads.
- Activity is process-local and resets on restart. It is not a durable or system-wide audit log.
  The Console does not execute tools, edit policy, grant permissions, or add RBAC/dynamic
  registration.
- The `/tools` page links to existing Agent Detail and Run Detail routes. API calls remain in
  `lib/apiClient.ts`, loading state lives in `hooks/useTools.ts`, and presentation lives under
  `features/tools/`.
- Verification: backend **411 passed, 4 skipped**; frontend **181 passed across 26 test files**;
  frontend production build succeeded. The real API returned the `fetch` registry and an empty
  activity result, and its CORS preflight returned the expected Console origin. Real browser
  verification remains blocked: Chrome and Edge headless both exited before opening the page due
  to a GPU-process failure in this environment.

---

# 44. Phase 6.7 - NEXUS Console: Run Comparison + Re-run

Phase 6.7 adds factual comparison and a guarded re-run path over the existing bounded RunStore.

- `GET /v1/runs/compare/{request_id_a}/{request_id_b}` returns owner-checked safe run summaries and
  B-minus-A deltas for measured duration, token, cost, and tool-event values. Missing measurements
  remain unavailable; the result does not rank or select a winner.
- `POST /v1/runs/{request_id}/replay` runs eligible first-turn input again through
  `NexusRuntime.execute()` in a newly-created session owned by the caller. The route relies on the
  existing auth, rate limit, runtime ownership, agent allowlist, and deterministic tool policy.
  The source thread is not changed and the resulting run has a new request ID and `replay_of` link.
- The source input is retained only in private, excluded RunRecord fields in process memory. It is
  never returned by the API or included in Pydantic serialization. It remains sensitive data in
  memory until the run is evicted or the process exits. Nothing is written to a durable store.
- A run with prior thread state is marked non-replayable because that context is not captured.
  Missing, evicted, or unowned source records return safe errors. Store capacity is checked before
  execution and eviction preserves both source and result.
- The Console's compare route reuses shared Run Detail trace components. The re-run action requires
  explicit confirmation and explains that it starts a fresh session, may execute tools, and is not
  deterministic replay.
- Comparison/re-run history remains subject to RunStore's process-local bound and restart reset.
  Fresh execution may differ and may incur real provider or tool side effects.

Verification: backend **423 passed, 4 skipped**; frontend **189 passed across 27 test files**;
lint completed with existing warnings outside Phase 6.7 files; TypeScript/Vite production build
succeeded. Real browser verification was attempted once after implementation; the local renderer
failed to initialize, so interactive behavior remains unverified in a real browser.

---

# 45. Phase 6.8 - NEXUS Console: Dashboard + Console Polish

Phase 6.8 adds the top-level Dashboard at `/` and makes it the unknown-route fallback. It reuses the
existing API client and per-resource hooks. The Dashboard loads bounded run summaries, evaluation
summaries, tool definitions, owned tool activity, and the public agent registry. Each section has
independent loading, empty, retry, and error states.

- The existing `GET /v1/runs` response contains full run records, including event traces, tool-event
  details, and final replies. Dashboard cards do not need these large fields, so the read-only
  `GET /v1/runs/summary?limit=10` projection returns only request ID, status, route, agent, timing,
  usage, and cost. It uses the existing auth, rate limit, and per-thread ownership check, is capped
  at 50 entries, and reads the same bounded RunStore.
- Run count, outcomes, and mean duration describe the retained data/sample actually returned.
  Token/cost totals sum only reported measurements and state coverage when incomplete. Unknown cost
  and token values are never displayed as zero. The dashboard is an operational view, not durable
  analytics; RunStore and EvaluationStore remain process-local and reset on restart.
- Sidebar navigation now includes Dashboard. At narrow widths it becomes a compact icon rail with
  accessible link labels. Run Detail links to its agent and to tool activity when tool events exist;
  the run action is labeled “Re-run” to distinguish fresh execution from deterministic replay.
- Existing tools and evaluation APIs remain unchanged. No database, aggregate analytics service, or
  background pipeline was added. Dashboard event rows contain only the existing safe tool-activity
  projection, never raw arguments, results, credentials, or headers.
- Verification: backend **427 passed, 4 skipped**; frontend **202 passed across 30 test files**;
  production build passed; lint completed with existing warnings outside new Phase 6.8 files.
  Browser verification was attempted once after implementation and blocked by the local renderer.

---

# 46. Phase 7 - Production Packaging

Phase 7 packages the existing platform for deployment: a backend Dockerfile, a frontend Dockerfile,
a local Compose stack, and a GitHub Actions CI workflow. It changes no runtime behavior - not
`NexusRuntime`, not `api.py`, not any Console feature. A container is a deployment wrapper, not a
second runtime: the backend image's only job is running `uvicorn api:app`, the exact ASGI app object
`api.py` already defines, and every startup behavior still happens inside its existing `lifespan()`.

- `Dockerfile` (root): two-stage build. `requirements-docker.txt` (new) mirrors
  `requirements.txt`/`pyproject.toml`'s dependencies plus the optional `postgres` extra, minus
  `ipykernel` (a notebook-only dependency never imported by application code) - one image supports
  both the SQLite and PostgreSQL backends, selected at runtime by `NEXUS_DATABASE_URL`, exactly as
  `runtime.create_runtime` already dispatches outside Docker. Runs as a dedicated non-root `nexus`
  user. `NEXUS_ENVIRONMENT=production` is the only baked-in default, specifically so the existing
  `config.load_config()` fail-closed rule (production requires `NEXUS_API_TOKEN`) applies without a
  deployer needing to remember to set it. `HEALTHCHECK` uses the existing `GET /ready` endpoint.
- `frontend/Dockerfile`: builds the existing `npm run build` (Vite, unchanged) and serves the static
  output with nginx (`frontend/nginx.conf`, SPA fallback to `index.html`) - no Node.js runtime in
  the final image. `VITE_NEXUS_API_BASE_URL` is a Vite build-time value (baked into the compiled JS,
  exactly as it already works outside Docker); `VITE_NEXUS_API_TOKEN` is deliberately not accepted
  as a build argument, since a shared/distributed image is a different exposure than a developer's
  local `.env.local`.
- `docker-compose.yml`: PostgreSQL + the API (`NEXUS_DATABASE_URL` pointing at it) + the Console -
  exercises the existing Phase 5 `AsyncPostgresSaver`/`access.PostgresAccessStore` code path, not a
  new persistence layer. PostgreSQL and the API are both bound to `127.0.0.1` only, not `0.0.0.0`.
  Required variables (`NEXUS_API_TOKEN`, `ANTHROPIC_API_KEY`, `POSTGRES_PASSWORD`) use Compose's
  `${VAR:?message}` required-substitution form - a missing value fails immediately with a clear
  message rather than starting with an empty credential. `.env.docker.example` (checked in,
  placeholder values only) documents them; `.env.docker` (gitignored) holds real values.
- **A real bug was found and fixed during this phase, not after being reported as done**: an early
  draft mapped `ANTHROPIC_MODEL: ${ANTHROPIC_MODEL:-}` in the api service's `environment:` block.
  `main.resolve_model_name`'s `env.get("ANTHROPIC_MODEL", DEFAULT_MODEL)` only falls back to the
  pinned default when the key is *absent*, not when it's an empty string - that mapping would have
  silently broken model resolution for every deployment that left `ANTHROPIC_MODEL` unset (the
  common case). Fixed by switching the api service's `environment:` to Compose's list form with a
  bare `- ANTHROPIC_MODEL` entry, which passes the variable through only when actually set and omits
  it entirely otherwise - restoring the "absent means use the default" semantics `main.py` relies on.
- `.github/workflows/ci.yml`: `backend-tests` (pytest, no credential); `frontend-tests` (vitest,
  oxlint, `npm run build`); `postgres-integration` (a real, disposable `postgres:16-alpine` GitHub
  Actions service container - runs the full backend suite with `NEXUS_TEST_DATABASE_URL` set,
  un-skipping the 4 tests in `tests/test_postgres_backend.py` that skip locally; the LLM is stubbed
  by that file's existing autouse fixture, so this needs a real database but no real model provider);
  `repo-hygiene` (credential-pattern, em-dash, and merge-conflict-marker scans via `git grep` over
  tracked content); `docker-build` (builds both images, validates `docker-compose.yml` structurally
  via `docker compose config`, then runs a Compose health/readiness/authenticate/create-session
  smoke test with a placeholder Anthropic key - deliberately stopping before sending a message, since
  that would require either a real provider credential or a real network call to Anthropic, exactly
  what this workflow's credential-free design avoids; the equivalent execute/persist/restart/
  ownership-denial validation against a live database is covered deterministically by
  `postgres-integration` instead).
- **Verification boundary - stated exactly, not glossed over.** This development environment has
  neither Docker nor a local PostgreSQL installation (checked directly: no `docker` binary, no
  Docker Desktop install directory, no `psql`/`pg_ctl`, no PostgreSQL install directory). As a
  result, the image builds, the Compose stack, and live PostgreSQL behavior have not been executed
  or observed here. What WAS verified here: the full backend suite (427 passed, 4 skipped) and full
  frontend suite (202 passed) still pass unchanged after every Phase 7 file was added; a targeted
  check confirmed the backend suite - including `import main` - passes with `ANTHROPIC_API_KEY`
  entirely absent (the `.env` file was moved aside and restored immediately afterward, verified
  identical), which is what makes the CI workflow's credential-free design a verified fact rather
  than an assumption; the frontend production build succeeds; `docker-compose.yml` and
  `.github/workflows/ci.yml` both parse as valid YAML; the CI repository-hygiene job's exact shell
  commands were dry-run locally against the real working tree, including the new Phase 7 files
  themselves, and found no matches. The CI workflow is written to real, documented GitHub
  Actions/Docker Compose semantics, but had not been observed running as of this writing, since
  exercising it requires a push or pull request this phase did not perform. Do not treat "the
  workflow exists and is well-formed" as equivalent to "the workflow has been observed to pass."
- The documented Windows/`psycopg`/`ProactorEventLoop` issue does not apply to the container/Compose
  path even on a Windows Docker Desktop host, since containers always run Linux; it remains relevant
  only to running the app directly on native Windows against Postgres, unchanged from Phase 5.
- Not added, and explicitly out of scope for this phase: TLS termination, a reverse proxy, a
  secrets manager, autoscaling, a real cloud deployment target, image digest pinning, container
  vulnerability scanning, a distributed rate limiter, or persistent `RunStore`/`EvaluationStore`
  history. See SECURITY.md Section 22 and README "Known limitations".
