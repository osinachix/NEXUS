# NEXUS Codex Repository Instructions

## 1. Purpose

This file is the primary repository-level instruction map for Codex working on NEXUS.

NEXUS is an AI Agent Runtime & Orchestration Platform.

Tagline:

    Connect. Orchestrate. Execute. Observe.

NEXUS is a reusable, domain-agnostic platform for:

    Build -> Run -> Observe -> Evaluate -> Govern

The goal is not to build a generic chatbot. The four current agents are reference
workloads used to demonstrate the platform runtime, orchestration, tools, security,
observability, evaluation, and Console capabilities.

IMPORTANT:

- Keep NEXUS domain-agnostic.
- Do not introduce company-specific branding, employer names, customer names,
  proprietary enterprise systems, or business-domain assumptions.
- Do not turn the project into a company-specific demo.
- Do not invent functionality that is not implemented.
- Do not describe planned functionality as implemented.
- Prefer a small, coherent, deeply verified platform over a large unfinished one.

---

## 2. Source of Truth and Repository Orientation

Before making meaningful changes, inspect the repository and read the relevant source
files. Do not rely only on this file.

Primary documentation:

1. `README.md`
   - user-facing product description
   - roadmap
   - API surface
   - setup and verification commands
   - known limitations

2. `ARCHITECTURE.md`
   - detailed architecture
   - phase history
   - execution boundaries
   - persistence model
   - observability model
   - security architecture
   - Console architecture

3. `SECURITY.md`
   - security threat model
   - SSRF protections
   - tool authorization
   - authentication and authorization
   - secret-handling rules
   - security limitations

4. `CLAUDE.md`
   - historical engineering instructions
   - architecture decisions accumulated during previous implementation
   - detailed phase history
   - product philosophy
   - testing and documentation rules

`CLAUDE.md` remains useful historical project knowledge. This file adapts those
principles for Codex. Do not casually delete or rewrite `CLAUDE.md`.

If documentation and code disagree, inspect the implementation and tests, determine
the actual current behavior, then update documentation as part of the change.

The code and tests are authoritative for what actually exists.
Documentation is authoritative for intended architectural boundaries and decisions
when it is consistent with the implementation.

---

## 3. Current Product Status

Completed:

- Phase 0: Correctness & Hardening
- Phase 1: Runtime & Observability
- Phase 2: Security & Tool Governance
- Phase 3: API Layer
- Phase 4: Evaluation & Advanced Observability
- Phase 5: Production Runtime & Security
- Phase 6.1: Agent Playground + Live Execution Trace
- Phase 6.2: Agent Registry + Test Agent
- Phase 6.3: Runs + Run Detail
- Phase 6.4: Sessions + State Explorer
- Phase 6.5: Evaluations Console (COMPLETE)
- Phase 6.6: Tools / Governance (implemented; browser verification blocked by local renderer)
- Phase 6.7: Run Comparison + guarded fresh re-run (implemented)
- Phase 6.8: Dashboard + Console Polish (implemented; browser verification blocked by local renderer)

Current priority:

    Phase 6.8 is implemented; take on another phase only when explicitly scoped

The planned Phase 7 scope is production packaging. Do not infer or begin that phase from routine
Console polish.

Phase 7 is production packaging.

Do not implement Phase 7 merely because a feature would eventually be useful.

Current verified baseline documented by the previous implementation work:

- Backend: 427 tests passing, 4 skipped
- Frontend: 202 tests passing across 30 test files

These numbers are a historical baseline, not a guarantee. Always run the actual
tests after changes and report the actual results.

---

## 4. High-Level Architecture

The central architecture is:

    Client
      |
      +-- CLI
      |
      +-- HTTP API
      |
      +-- NEXUS Console
              |
              v
          NEXUS API
              |
              v
         NexusRuntime
              |
              v
           LangGraph
              |
              v
        Agents / Tools

The strict boundaries are:

    NEXUS Console
        |
        v
    NEXUS API
        |
        v
    NexusRuntime
        |
        v
    LangGraph
        |
        v
    Agents / Tools

Rules:

- The Console is an API client.
- The Console never imports Python.
- The Console never manipulates LangGraph.
- `api.py` is the HTTP application boundary.
- `NexusRuntime` is the execution boundary.
- LangGraph is an orchestration implementation detail.
- Agent behavior belongs in the runtime/agent layer, not in frontend code.
- Security decisions must not be delegated to frontend code or LLM output.
- Evaluation must use the same runtime execution path as normal execution.

---

## 5. Automatic Routing Graph

The existing automatic graph is:

    START
      |
      v
    classifier
      |
      v
    router
      |
      +------> counselor
      |
      +------> logical
      |
      +------> math
      |
      +------> coding
                 |
                 v
                END

The router is deterministic Python control flow.

The classifier is an LLM structured-output operation.

The four reference agents are:

- counselor
- logical
- math
- coding

The uploaded/generated `graph.png` represents this automatic-routing topology.

Do not treat that diagram as the complete NEXUS architecture.

---

## 6. Direct Agent Execution

The Console also supports direct-agent execution.

Topology:

    User
      |
      v
    NexusRuntime
      |
      v
    Selected Agent
      |
      v
     END

Direct-agent execution deliberately bypasses:

- classifier
- router

The implementation uses dedicated classifier-free graph builders in `main.py`.

Do not reintroduce classifier/router steps into direct-agent execution merely to
make the graphs look uniform.

Do not create a second execution implementation in the frontend.

The frontend selects an agent and calls the API. The backend remains authoritative
for whether that agent exists and is executable.

---

## 7. Agent Registry

`agents.py` is the public agent metadata and direct-execution allowlist layer.

It provides:

- `AgentDefinition`
- `list_agents()`
- `get_agent()`
- `is_executable()`

The registry describes public metadata only.

It must not expose:

- system prompts
- API keys
- credentials
- provider secrets
- internal implementation details
- hidden model configuration that is not intentionally public

Agent execution behavior remains in `main.py` and the runtime layer.

Do not duplicate the registry as a hardcoded frontend list.

The Console must discover agents through:

    GET /v1/agents
    GET /v1/agents/{agent_id}

---

## 8. Run vs Session

These are deliberately different concepts.

RUN:

    what happened during one execution

SESSION:

    persistent conversational/workflow state associated with a thread

Runs are stored in `run_store.py`.

Sessions are discovered from LangGraph checkpoint state.

Do not merge these concepts.

Do not describe a session as long-term memory.

Do not add semantic/vector memory unless a future phase explicitly requires it.

Current RunStore limitation:

- bounded
- in-process
- resets on restart
- not a durable historical database
- eligible first-turn run inputs are retained privately in process memory for Phase 6.7 re-runs
- re-run inputs are excluded from API responses and Pydantic serialization, but remain sensitive
  process memory until record eviction or process exit
- later turns with prior thread state are not eligible for re-run; the feature is not deterministic replay

Do not pretend `GET /v1/runs` is backed by durable run history.

Current Session listing limitation should likewise be understood from
`ARCHITECTURE.md`.

---

## 9. Trace Architecture

The Playground has one canonical live trace pipeline.

Important frontend modules include:

- `frontend/src/lib/sseClient.ts`
- `frontend/src/lib/sseParser.ts`
- `frontend/src/lib/traceReducer.ts`
- `frontend/src/components/ExecutionTrace*`
- related trace/event types

Historical Run Detail uses:

    stored run
       |
       v
    runToTrace.ts
       |
       v
    NexusEvent[]
       |
       v
    traceReducer.ts
       |
       v
    same ExecutionTrace components

This is an important architectural rule.

If a future Console feature needs to display execution events:

1. reshape its source data into the existing event vocabulary
2. reuse `traceReducer.ts`
3. reuse existing trace rendering components

Do NOT build a second trace renderer or second event vocabulary.

Sessions are the intentional exception because Sessions display persisted state and
message history, not an execution trace.

---

## 10. NEXUS API Boundary

`api.py` must remain thin.

It translates:

    HTTP request
        ->
    NexusRuntime call
        ->
    HTTP response

It must not directly call:

- classifier nodes
- router nodes
- specialist agent functions
- LangGraph graph objects

Execution must go through `NexusRuntime`.

The API currently provides, among other endpoints:

- `GET /health`
- `GET /ready`
- `POST /v1/sessions`
- `GET /v1/sessions`
- `GET /v1/sessions/{thread_id}`
- `POST /v1/sessions/{thread_id}/messages`
- `POST /v1/sessions/{thread_id}/messages/stream`
- `GET /v1/runs`
- `GET /v1/runs/{request_id}`
- `GET /v1/runs/compare/{request_id_a}/{request_id_b}`
- `POST /v1/runs/{request_id}/replay`
- `GET /v1/agents`
- `GET /v1/agents/{agent_id}`
- `GET /v1/tools`
- `GET /v1/tools/activity`
- evaluation endpoints

Consult the actual OpenAPI contract and `api.py` before adding or changing endpoints.

Do not remove existing response fields casually.

Prefer additive, backward-compatible API changes unless the current phase explicitly
requires a breaking change.

Use stable machine-readable error codes.

Never expose raw stack traces, secrets, provider credentials, authorization headers,
or raw internal exception details to API clients.

---

## 11. Authentication and Authorization

Authentication is handled at the HTTP boundary by `auth.py`.

The runtime must not know about:

- HTTP headers
- FastAPI `Request`
- bearer tokens
- authentication implementation details

The runtime receives a plain:

    principal_id: str

Authorization is handled through `access.py`.

Important distinction:

    Authentication = who is the caller?
    Authorization  = may this caller access this resource?

Do not collapse these responsibilities.

Current authentication model:

- optional development mode without a configured token
- bearer-token mode with `NEXUS_API_TOKEN`
- production configuration refuses to start without authentication

Current model is intentionally minimal:

- one configured bearer token
- no OAuth
- no SSO
- no RBAC
- no real user account system

Do not silently invent multi-user identity semantics.

Ownership checks must happen on the backend.

List endpoints must avoid resource-existence leaks. Follow the existing pattern:
unowned resources are excluded from list results rather than revealed through
authorization errors.

---

## 12. Rate Limiting

`rate_limit.py` contains the current bounded fixed-window limiter.

Important limitation:

- process-local
- in-memory
- not distributed
- resets on process restart

Do not claim that it provides distributed production rate limiting.

A future shared Redis/Postgres implementation would be a separate architectural
decision.

---

## 13. Tool Security

The LLM is NOT the security boundary.

Security-sensitive decisions must be deterministic.

Current tool/network protections include concepts such as:

- HTTPS-only defaults
- URL validation
- credential rejection in URLs
- exact domain allowlisting
- DNS/IP validation
- SSRF protection
- redirect revalidation
- response-size limits
- timeouts
- tool authorization
- untrusted-content handling
- DNS-rebinding-resistant fetch connections

`tool_policy.py` is a security boundary.

`tool_registry.py` provides safe read-only metadata only. It derives tool definitions from the
definitions actually bound in `main.py` and allowed agents from `AGENT_TOOL_POLICY`. It does not
authorize calls and must not become a second policy source.

Do not weaken it for convenience.

Do not allow model output to bypass tool authorization.

Do not treat fetched content as trusted instructions.

Prompt injection is mitigated, not solved.

If changing tool behavior, add security tests, not only happy-path tests.

---

## 14. MCP

MCP remains an architectural integration capability.

Mental model:

    Host/Application
          |
        Client
          |
       MCP protocol
          |
        Server
          |
    Tools / Resources / Prompts
          |
       External systems

Important distinction:

- Tool = action
- Resource = information
- Prompt = reusable instruction/template

MCP does not solve authorization, identity, SSRF, or governance automatically.

The current secure fetch path is implemented natively with `httpx` because NEXUS
needed deterministic interception of redirects, streaming limits, DNS validation,
and connection pinning.

Do not reintroduce an MCP fetch implementation merely because MCP appears in the
architecture documentation.

---

## 15. Observability

`observability.py` provides structured lifecycle events.

Core principles:

- every event is correlated with `request_id`
- every event is correlated with `thread_id`
- log metadata, not user content
- log error types, not raw exception objects
- never log prompts
- never log message content
- never log tool arguments/results
- never log authorization headers
- never log credentials
- logging failures must not crash execution
- do not fabricate token usage

Typical lifecycle events include:

- `workflow_started`
- `classifier_started`
- `classifier_completed`
- `route_selected`
- `agent_started`
- `agent_completed`
- `tool_started`
- `tool_completed`
- `tool_failed`
- `tool_denied`
- `workflow_completed`
- `workflow_failed`
- HTTP request events
- streamed completion events

Preserve the existing event vocabulary unless there is a strong architectural
reason to change it.

If adding an event, update:

- backend tests
- frontend event types if needed
- trace reduction if needed
- documentation

---

## 16. Cost and Token Accounting

NEXUS must never fabricate cost.

Cost is only available when:

1. the provider reports token usage
2. pricing is explicitly configured

`pricing.py` intentionally returns `None` when information is missing.

Do not add hardcoded model prices unless explicitly required and documented.

UI should display unavailable values honestly:

- `Not reported`
- `--`
- or another clearly unavailable representation

Never display fake zeroes for unknown cost or token usage.

---

## 17. Evaluation Architecture

The evaluation framework lives under `evals/`.

Evaluation must execute through the same runtime path as normal execution.

Do not call LangGraph nodes directly from evaluation code.

Current evaluation concepts include:

- deterministic routing checks
- execution checks
- tool usage checks
- response checks
- latency metrics
- token metrics
- configurable cost metrics
- evaluation comparison

Evaluation results should remain measurable and reproducible.

Do not introduce subjective rankings or "best agent" labels without a concrete,
documented evaluation definition.

If adding LLM-as-judge in a future phase, treat it as a distinct probabilistic
evaluation mechanism and document its limitations.

---

## 18. Frontend Architecture

The frontend is:

- React
- TypeScript
- Vite
- Tailwind CSS
- Vitest
- React Testing Library

Current principle:

    frontend
       |
       v
    apiClient / sseClient
       |
       v
    NEXUS API

Only the frontend `src/lib/` API/SSE layer should perform network access.

Do not scatter `fetch()` calls through arbitrary components.

Existing organization:

    frontend/src/
      types/
      lib/
      hooks/
      components/
      features/

Feature pages should remain reasonably thin.

Use hooks for API/state orchestration.

Use reusable components for presentation.

Avoid introducing Redux or another state-management library unless the existing
architecture genuinely cannot support the feature.

---

## 19. Console Product Direction

The NEXUS Console should feel like a premium developer platform.

Desired direction:

- dark developer-console aesthetic
- information-dense but readable
- technically sophisticated
- polished
- restrained animation
- clear hierarchy
- strong typography
- useful empty/loading/error states
- real runtime data
- no fake dashboards
- no placeholder metrics presented as real

Conceptual inspiration may include:

- Linear
- Vercel
- Datadog

Do not clone another product.

The Console should communicate:

    Build
    Run
    Observe
    Evaluate
    Govern

The UI should expose actual NEXUS runtime behavior rather than merely decorating
a chatbot.

---

## 20. Existing Console Surfaces

Completed:

### `/playground`

- Auto Route mode
- direct-agent mode
- real session creation
- real SSE execution
- live execution trace
- final response
- run metadata
- agent selection

### `/agents`

- API-backed agent registry
- status
- description
- tools
- capabilities
- Test Agent navigation

### `/agents/:agentId`

- agent details
- safe public metadata
- Test Agent

### `/runs`

- recent run history from RunStore
- status
- agent
- route
- request id
- timing
- token/cost data when available
- filters
- search/sort
- ownership isolation

### `/runs/:requestId`

- run metadata
- reused execution trace
- final response
- safe failure information
- session navigation where implemented

### `/sessions`

- persisted thread/session discovery
- ownership filtering
- last activity
- state metadata

### `/sessions/:threadId`

- session metadata
- persisted message history
- navigation back to related runs

### `/tools`

- read-only metadata derived from actual bound tool definitions and `tool_policy.AGENT_TOOL_POLICY`
- links to allowed agents and retained activity's parent runs
- caller-owned completed, denied, and failed events from the bounded process-local RunStore
- no tool execution, policy editing, or durable/global audit history

Do not create duplicate execution surfaces.

---

## 21. Frontend Security and Data Handling

Never render untrusted message content using:

    dangerouslySetInnerHTML

unless a future, explicitly reviewed feature introduces a trusted sanitization
pipeline.

Current session message rendering should remain plain React text.

Do not put secrets into:

- source control
- frontend bundles
- UI
- URLs
- query strings
- logs
- screenshots
- test fixtures

The Console may use the configured local API token mechanism already present in
the project, but do not build a fake login system.

Do not assume the current one-token model is equivalent to a future real identity
system.

---

## 22. State and Memory

State is not memory.

Current persisted thread state is conversation/workflow state.

Long-term semantic memory is NOT implemented.

Do not introduce:

- vector memory
- semantic memory
- user profiling
- hidden memory
- automatic user-memory extraction

unless a future phase explicitly requires it.

Any future memory system must have an explicit persistence, privacy, authorization,
retention, and evaluation design.

---

## 23. Model and Provider Discipline

Current model configuration is environment-driven and intentionally pinned by
default rather than using a floating `-latest` alias.

Do not silently change the default model.

Do not assume a provider API based on memory.

Inspect installed versions and actual APIs before modifying integrations.

Real provider calls are optional for the core test suite.

Tests must not require:

- Anthropic credentials
- OpenAI credentials
- external MCP servers
- arbitrary websites

Use mocks/fakes for deterministic tests.

Live provider verification should be explicit.

Never replace credentials.

---

## 24. Dependency Discipline

Before adding a dependency:

1. Check whether an existing dependency already solves the problem.
2. Inspect the installed version.
3. Verify the actual API.
4. Prefer the smallest dependency surface.
5. Add tests.
6. Update `pyproject.toml` and other manifests.
7. Verify installation/import behavior.

Do not add a library merely because it is popular.

Do not use a library API from a different installed version.

---

## 25. Testing Requirements

A meaningful feature is not complete when code merely compiles.

Expected sequence:

1. Inspect repository.
2. Read relevant architecture/security docs.
3. Run the existing targeted tests or full suite.
4. Implement the smallest coherent change.
5. Add focused tests.
6. Run targeted tests.
7. Run the complete backend suite.
8. Run the complete frontend suite when frontend code changes.
9. Perform real runtime verification.
10. Perform browser verification when browser behavior is involved.
11. Clean temporary artifacts.
12. Update documentation.
13. Inspect git status.
14. Report actual results.

Never claim a test passed unless it actually ran.

Never claim live verification unless it actually happened.

Never substitute curl/httpx for browser verification when the behavior is
browser-specific.

CORS is an example of a defect that can be invisible to non-browser clients.

For backend changes, consider:

- happy path
- validation
- auth
- authorization
- ownership isolation
- persistence
- thread isolation
- request correlation
- observability
- error handling
- secret leakage
- concurrency
- security boundaries

For frontend changes, consider:

- loading
- success
- empty
- filtered-empty
- error
- unauthorized
- not found
- narrow viewport
- navigation
- API failure
- real browser behavior

---

## 26. Runtime Verification

When practical, verify the real stack:

    API server
       +
    Console
       +
    Browser
       +
    real API contract

For important Console changes, prefer a real browser flow.

Verify:

- API connectivity
- CORS
- routing
- SSE where relevant
- actual data rendering
- navigation
- responsive behavior
- error states
- no console errors
- no leaked credentials

If the provider key is invalid, verify the failure path safely rather than inventing
a successful LLM response.

Do not modify a user's API key merely to make a demo pass.

---

## 27. Documentation Rules

When architecture changes, update the appropriate documentation.

At minimum consider:

- `README.md`
- `ARCHITECTURE.md`
- `SECURITY.md`
- `CLAUDE.md`
- this `AGENTS.md` when repository instructions or architecture boundaries change

Documentation must distinguish:

- implemented
- partially implemented
- planned
- intentionally out of scope
- known limitations

Do not let phase numbers or status drift.

If a phase is completed, document what was actually verified.

---

## 28. Git Discipline

Keep commits focused.

Preferred prefixes:

    feat:
    fix:
    docs:
    test:
    refactor:
    chore:

Do not commit:

- `.env`
- API keys
- temporary databases
- SQLite WAL/SHM artifacts
- logs
- caches
- generated secrets
- local development artifacts

Always inspect:

    git status

before finalizing.

Do not rewrite unrelated history.

Do not make broad formatting changes unrelated to the task.

---

## 29. Secret Incident Rule

If you discover a real credential or secret:

1. Do not reproduce it in output.
2. Do not commit it.
3. Do not move it to another file.
4. Do not paste it into tests or documentation.
5. Identify the affected file safely.
6. Recommend rotation/revocation.
7. Remove it from tracked content if appropriate.
8. Check git status and relevant history implications.

The repository currently has a local `.env` pattern that is intentionally ignored.
Treat its contents as secret.

Do not print secret values during inspection.

---

## 30. No Em Dash Character

NEXUS project convention:

    DO NOT USE THE EM DASH CHARACTER.

Use a normal hyphen:

    -

This applies to:

- source code comments
- Markdown
- documentation
- UI copy
- commit messages
- generated text
- tests
- diagrams

Before finalizing a documentation-heavy change, search the repository for the em dash character.

---

## 31. Architecture Decision Rule

Before a major architectural change, answer:

1. What problem does this solve?
2. Which existing boundary should own the solution?
3. Does it preserve `NexusRuntime` as the execution boundary?
4. Does it preserve deterministic security?
5. Does it preserve testability?
6. Does it introduce unnecessary infrastructure?
7. Is it actually required in the current phase?
8. Does it create a second implementation of something NEXUS already has?

Prefer the smallest architecture that solves the current product requirement.

---

## 32. Do Not Overbuild

Do not implement future functionality merely because it would look impressive.

Examples of currently non-complete areas include:

- full OAuth/SSO
- RBAC
- distributed rate limiting
- deterministic replay
- long-term semantic memory
- marketplace
- billing
- full multi-tenancy
- production deployment packaging
- advanced model routing
- human approval workflows

Some of these are long-term platform goals, but they are not automatically part of
the current phase.

A polished, verified implementation is more valuable than a large collection of
unfinished abstractions.

---

## 33. Product Mental Models

Keep these mental models consistent:

    LLM
      = reasoning / generation

    RAG
      = retrieval / grounding

    Tool
      = external action

    Agent
      = LLM + tools + state + control flow

    LangGraph
      = orchestration

    MCP
      = integration protocol

    NEXUS
      = runtime + orchestration + tools + security
        + observability + evaluation + governance

Another useful model:

    LangGraph = orchestrate
    MCP       = connect
    RAG       = retrieve
    LLM       = reason/generate
    NEXUS     = govern the execution

---

## 34. Engineering Philosophy

NEXUS is intended to demonstrate engineering judgment, not just framework knowledge.

Prioritize:

- reliability
- security
- observability
- testability
- maintainability
- explicit boundaries
- measurable behavior
- clear UX
- honest limitations

For every significant feature consider:

- failure modes
- timeout behavior
- security implications
- observability
- testing
- persistence
- concurrency
- API compatibility
- frontend behavior
- future extensibility

Do not rewrite working code only because another style is preferred.

---

## 35. Codex Working Style

When taking a task:

1. Inspect before modifying.
2. Build a concise mental model of the current implementation.
3. Identify the existing boundary that should own the change.
4. Prefer existing abstractions over new ones.
5. Make the smallest coherent patch.
6. Add tests with the implementation.
7. Verify incrementally.
8. Run the full relevant suite.
9. Perform real runtime/browser verification when applicable.
10. Update documentation.
11. Review the diff for accidental changes.
12. Report what was actually done and verified.

Do not blindly follow generated code.

Do not invent APIs.

Do not silently change architecture.

If a requested feature conflicts with an existing architectural rule, stop and
explain the conflict before making a broad workaround.

If a task is underspecified but can be safely implemented within the current
architecture, use the smallest reasonable interpretation and document the decision.

---

## 36. Definition of Done

For a meaningful NEXUS feature:

    Implementation
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
        =
    Done

If one part is intentionally omitted, explicitly state why.

The final report should include:

- files changed
- architecture decisions
- tests executed and actual results
- live verification performed
- known limitations
- documentation updated
- anything not verified

Never fabricate verification.

---

## 37. Current Mission

Phases 6.1 through 6.8 are implemented in the existing NEXUS Console. Browser verification for
Phases 6.6 through 6.8 is blocked by a local Chrome/Edge renderer initialization failure. Phase 6.7
adds factual run comparison and a guarded fresh re-run for eligible first-turn runs; it does not
provide deterministic replay. The Console uses bounded existing APIs and one lightweight run-summary
projection; it has no dashboard analytics service or new persistence layer.

Do not restart the project.

Do not replace the existing architecture with a new framework.

Do not throw away the existing Console.

Extend the existing:

    frontend/

and existing:

    NEXUS API
        ->
    NexusRuntime
        ->
    LangGraph

architecture.

The next work should build naturally on:

- Playground
- Agent Registry
- Runs
- Sessions
- shared API client
- shared SSE client
- shared trace reducer
- shared design language
- existing evaluation framework
- existing observability
- existing security boundaries

The end result should feel like one platform, not a collection of disconnected
demo pages.

The highest standard is:

    real data
    + clear architecture
    + strong security
    + excellent observability
    + deterministic tests
    + polished Console UX
    + honest limitations

That is the NEXUS standard.
