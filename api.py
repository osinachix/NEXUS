"""NEXUS API: a thin FastAPI service layer over NexusRuntime.

ARCHITECTURAL RULE (do not violate): this module must never call
`classify_message`, `router`, `counselor_agent`, `logical_agent`,
`math_agent`, `coding_agent`, or touch a LangGraph graph object directly.
Every execution goes through `NexusRuntime.execute()` / `get_state()` --
the exact same entrypoints the CLI (`main.py: run_chatbot`) already uses.
This module's only job is translating HTTP requests into those calls and
their results into HTTP responses. Business/agent logic lives in `main.py`
and below; this file should stay thin.

    Client -> Authentication -> Authorization -> Rate limiting -> NEXUS API
           -> NexusRuntime -> LangGraph -> Agents / Tools

As of Phase 5, real (if minimal) authentication exists -- see auth.py.
Every non-health route depends on `get_principal` (authenticate) and
`enforce_rate_limit` (authenticate + rate-limit), which resolve an HTTP
`Authorization` header to an `auth.Principal` *before* the route body
runs. `access.py`'s thread-ownership bookkeeping is unchanged in kind
(still not authentication by itself) but is now checked against a real
authenticated principal_id rather than one hardcoded constant. See
auth.py, access.py, config.py, rate_limit.py for each piece; ARCHITECTURE.md
"What Phase 5 changed" for the full picture.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Literal

from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field, field_validator

import access
import agents as agents_module
import auth
import config as config_module
import main
import observability
import pricing as pricing_module
import rate_limit
import run_store
import runtime as nexus_runtime
import tool_registry
from evals import dataset as dataset_module
from evals import evaluator as evaluator_module
from evals import metrics as eval_metrics_module
from evals import store as evals_store_module
from evals.models import (
    ComparisonResult,
    EvaluationListResponse,
    EvaluationResult,
    EvaluationRun,
    EvaluationSummary,
    RunMetrics,
)

logger = logging.getLogger("nexus.api")

# Internal principal used ONLY for the unauthenticated /ready probe (never
# tied to a caller's identity -- health checks intentionally require no
# credential). Distinct from any real caller principal (see auth.py).
_READINESS_PRINCIPAL_ID = access.LOCAL_API_PRINCIPAL

# Reserved thread_id used only by the /ready probe (never a real session);
# distinct enough that it can't collide with a generated thread_id.
_READINESS_PROBE_THREAD_ID = "__nexus_readiness_probe__"


# ---------------------------------------------------------------------------
# Request/response models -- the only shapes that cross the HTTP boundary.
# Internal objects (ExecutionResult, LangGraph StateSnapshot, etc.) never
# are returned directly.
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = Field(..., description="Always 'ok' if the process is running.")
    service: str = Field(..., description="Service identifier.")


class ReadinessResponse(BaseModel):
    status: str = Field(..., description="'ready' or 'not_ready'.")
    service: str
    checkpointer: str = Field(
        ..., description="'ok' if the configured SQLite or PostgreSQL checkpointer responded to a cheap, non-LLM probe."
    )


class SessionCreateResponse(BaseModel):
    thread_id: str = Field(..., description="Identifier for the new session/thread.")


class SessionMessage(BaseModel):
    """One persisted turn's message (Phase 6.4). `role` is the LangChain
    message type as-is ('human'/'ai') -- not translated to a NEXUS-specific
    vocabulary, so it stays a direct, honest reflection of what's actually
    stored. Never includes routing/agent metadata: the persisted checkpoint
    state only ever tracks the thread's MOST RECENT classification/route
    (see `SessionResponse.last_route`), not a per-message history of which
    agent handled which turn -- that granularity only exists per-run, in
    `run_store.RunRecord`, not in thread state."""

    role: str
    content: str


class SessionResponse(BaseModel):
    thread_id: str
    status: str = Field(..., description="'active' -- the session has at least one persisted turn.")
    message_count: int = Field(..., description="Number of persisted messages (user + assistant) in this thread.")
    last_message_type: str | None = Field(
        None, description="Classifier category from the most recent turn, if any."
    )
    last_route: str | None = Field(None, description="Route selected on the most recent turn, if any.")
    updated_at: str | None = Field(
        None, description="Timestamp of the most recent checkpoint for this thread, if available."
    )
    messages: list[SessionMessage] | None = Field(
        None, description="Phase 6.4: full message history, oldest first. Only populated by "
        "GET /v1/sessions/{thread_id} -- null (not an empty list) in GET /v1/sessions' list "
        "results, which never fetch full content."
    )


class SessionListResponse(BaseModel):
    """GET /v1/sessions (Phase 6.4). Reflects only sessions discoverable
    within `NexusRuntime.list_sessions`'s bounded checkpoint scan - see
    that method's docstring and README 'Known limitations'."""

    items: list[SessionResponse]
    limit: int


class MessageRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=10_000,
        description="The user message to send to the NEXUS agent runtime for this thread.",
    )
    agent: str | None = Field(
        None,
        description="Phase 6.1: run this specific agent directly, bypassing the classifier/router "
        "entirely (no classifier_* or route_selected events are emitted for a direct-agent turn). "
        "Omit (or null) for the normal automatic-routing behavior. Phase 6.2: validated against the "
        "agent registry (GET /v1/agents) -- must be a known, currently-active agent id.",
    )

    @field_validator("message")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("message must not be blank")
        return value

    @field_validator("agent")
    @classmethod
    def _known_and_active_agent(cls, value: str | None) -> str | None:
        # The registry (agents.py), not a hardcoded Literal, is the
        # authoritative allowlist -- see agents.is_executable's docstring.
        # This is what keeps an unknown or currently-unavailable agent id
        # from ever reaching NexusRuntime.execute()/graph construction.
        if value is not None and not agents_module.is_executable(value):
            raise ValueError(f"unknown or unavailable agent id: {value!r}")
        return value


class MessageResponse(BaseModel):
    thread_id: str
    request_id: str = Field(..., description="Use with GET /v1/runs/{request_id} to look up this execution.")
    response: str = Field(..., description="The assistant's reply for this turn.")
    route: str | None = Field(
        None,
        description="Which specialist agent handled this turn. Populated from route_selected for "
        "automatic routing; null for a direct-agent turn (see MessageRequest.agent) since no "
        "route_selected event is emitted in that mode -- the caller already knows which agent it "
        "asked for.",
    )
    status: str = Field(..., description="'completed' or 'failed'.")
    duration_ms: float


class RunResponse(BaseModel):
    """GET /v1/runs/{request_id}. Built from `run_store.RunRecord` (Phase 4)
    -- see `_to_run_response` below. The original Phase 3 fields
    (request_id/thread_id/status/route/duration_ms/success/created_at) are
    unchanged in name and meaning; everything else is new.
    """

    request_id: str
    thread_id: str
    status: str = Field(..., description="'completed' or 'failed'.")
    route: str | None = Field(
        None, description="Classifier-selected route; null for a direct-agent run (see `agent`)."
    )
    agent: str | None = Field(
        None, description="Phase 6.3: which specialist agent actually ran, populated for BOTH "
        "auto-route and direct-agent runs (unlike `route`, which is only ever set for auto-route)."
    )
    duration_ms: float
    success: bool
    created_at: str = Field(
        ..., description="Alias for completed_at, kept for Phase 3 response-shape compatibility."
    )
    message_type: str | None = Field(None, description="Classifier category for this run, if available.")
    started_at: str
    completed_at: str
    response: str = Field(
        ..., description="Phase 6.3: the assistant's final reply for this run, the same text "
        "POST .../messages already returns synchronously -- never fabricated when absent; a "
        "failed run's fallback reply is still what NEXUS actually sent the caller."
    )
    events: list[run_store.RunEvent] = Field(
        default_factory=list,
        description="Structured lifecycle events for this run (metadata only, e.g. workflow_started, "
        "classifier_completed, route_selected, agent_completed -- never message content).",
    )
    tool_events: list[run_store.ToolEvent] = Field(
        default_factory=list, description="Just the tool_started/tool_completed/tool_denied/tool_failed events."
    )
    usage: run_store.TokenUsage | None = Field(
        None, description="Provider token usage aggregated across this run's LLM calls, if the provider returned it."
    )
    cost_usd: float | None = Field(
        None, description="Only populated when both usage and pricing (NEXUS_PRICING_FILE) are available -- see pricing.py."
    )
    error_type: str | None = Field(
        None, description="Exception type name if the run (or a node within it) failed; never a raw message/traceback."
    )
    replayable: bool = Field(
        False,
        description="Whether the original input and a fresh-thread context are retained for a safe re-run.",
    )
    replay_unavailable_reason: str | None = Field(
        None, description="Safe reason replay is unavailable, when known."
    )
    replay_of: str | None = Field(None, description="Source request ID for a re-run, if this run was replayed.")


class RunComparisonResponse(BaseModel):
    run_a: RunResponse
    run_b: RunResponse
    deltas: run_store.RunComparisonDeltas = Field(
        ..., description="Measured B-minus-A deltas; null fields mean data was unavailable."
    )


def _to_run_response(record: run_store.RunRecord) -> RunResponse:
    return RunResponse(
        request_id=record.request_id,
        thread_id=record.thread_id,
        status=record.status,
        route=record.route,
        agent=record.agent,
        duration_ms=record.duration_ms,
        success=record.success,
        created_at=record.completed_at,
        message_type=record.message_type,
        started_at=record.started_at,
        completed_at=record.completed_at,
        response=record.reply,
        events=record.events,
        tool_events=record.tool_events,
        usage=record.usage,
        cost_usd=record.cost_usd,
        error_type=record.error_type,
        replayable=record.replayable,
        replay_unavailable_reason=record.replay_unavailable_reason,
        replay_of=record.replay_of,
    )


class RunListResponse(BaseModel):
    """GET /v1/runs (Phase 6.3). Reflects only the bounded, in-process
    RunStore -- NOT a durable audit log; see the endpoint description
    below and README 'Known limitations'."""

    items: list[RunResponse]
    total: int = Field(
        ..., description="Count of this principal's runs matching the given filters, before "
        "`limit` truncation -- capped by however many runs the bounded store currently holds, "
        "never an estimate."
    )
    limit: int = Field(..., description="The effective limit applied to this response's `items`.")


class RunListItemSummary(BaseModel):
    """Small run projection for overview surfaces that do not need traces or replies."""

    request_id: str
    status: str
    route: str | None
    agent: str | None
    duration_ms: float
    success: bool
    created_at: str
    started_at: str
    completed_at: str
    usage: run_store.TokenUsage | None
    cost_usd: float | None


class RunSummaryListResponse(BaseModel):
    """Ownership-filtered lightweight view of the bounded, process-local RunStore."""

    items: list[RunListItemSummary]
    total: int
    limit: int


class ToolActivityEvent(BaseModel):
    """Safe projection of a retained tool event from an owned run."""

    request_id: str
    tool: str
    event_type: Literal["tool_completed", "tool_denied", "tool_failed"]
    agent: str | None
    timestamp: str
    duration_ms: float | None = None
    success: bool | None = None
    reason: str | None = None
    error_type: str | None = None


class ToolActivityResponse(BaseModel):
    """Activity is limited to retained, process-local runs owned by caller."""

    items: list[ToolActivityEvent]
    total: int = Field(..., description="Matching retained events owned by this caller, before limit.")
    limit: int


class ErrorDetail(BaseModel):
    code: str = Field(..., description="Stable, machine-readable error code.")
    message: str = Field(..., description="Safe, human-readable description. Never a stack trace or secret.")


class ErrorResponse(BaseModel):
    error: ErrorDetail


# ---------------------------------------------------------------------------
# Errors -- one exception type, mapped centrally to the ErrorResponse shape.
# Never leaks a stack trace, exception args, credentials, or raw tool/LLM
# content to the client. Full detail is logged server-side only.
# ---------------------------------------------------------------------------


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.headers = headers or {}
        super().__init__(message)


def _error_response(
    status_code: int, code: str, message: str, headers: dict[str, str] | None = None
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"error": {"code": code, "message": message}}, headers=headers
    )


# ---------------------------------------------------------------------------
# App lifecycle: NexusRuntime is created once at startup and closed once at
# shutdown -- never per-request. This is the same runtime/checkpointer
# machinery `main.py: run_chatbot` uses for the CLI; the API is a second,
# independent client of it, not a reimplementation.
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Validate configuration BEFORE anything else starts -- config.py raises
    # config_module.ConfigError for anything invalid enough that serving
    # traffic anyway would be misleading (most importantly: production
    # with no way to authenticate a caller). This is intentionally the
    # very first thing that runs in the app's lifecycle.
    app_config = config_module.load_config()
    app.state.config = app_config

    if app_config.auth_enabled:
        logger.info("authentication ENABLED (NEXUS_API_TOKEN configured)")
    else:
        # Explicit and loud, never silent -- see auth.py's module docstring.
        # Never logs the token itself (there isn't one to log in this mode).
        logger.warning(
            "authentication DISABLED -- running in development mode (NEXUS_API_TOKEN not set, "
            "NEXUS_ENVIRONMENT=%r). Every request is treated as principal_id=%r. Do not run this "
            "mode against untrusted networks.",
            app_config.environment,
            auth.DEVELOPMENT_PRINCIPAL.principal_id,
        )
    if app_config.uses_postgres:
        logger.info("durable backend: PostgreSQL (NEXUS_DATABASE_URL configured)")
    else:
        logger.info("durable backend: SQLite (development default)")

    main.logical_react_agent = main.build_logical_agent()
    async with nexus_runtime.create_runtime(
        main.graph_builder,
        fallback_message=main.GENERIC_FAILURE_MESSAGE,
        database_url=app_config.database_url,
        direct_agent_builders=main.DIRECT_AGENT_GRAPH_BUILDERS,
    ) as session:
        app.state.runtime = session
        app.state.run_store = run_store.RunStore()
        # Empty unless NEXUS_PRICING_FILE is set -- see pricing.py. No
        # pricing configured means cost_usd is always null, never estimated.
        app.state.pricing = pricing_module.load_pricing_config()
        app.state.evaluation_store = evals_store_module.EvaluationStore()
        # Process-local, in-memory -- see rate_limit.py's module docstring
        # for the multi-instance limitation this doesn't solve.
        app.state.rate_limiter = rate_limit.RateLimiter(
            app_config.rate_limit_requests, app_config.rate_limit_window_seconds
        )
        yield
    # The checkpointer's (and, for Postgres, the access-store pool's)
    # connection(s) are closed automatically on exiting the `async with`
    # above (create_runtime's own context manager) -- no separate cleanup
    # needed here.


# ---------------------------------------------------------------------------
# CORS (Phase 6.1): the NEXUS Console is a browser-based, separate-origin
# client (e.g. http://localhost:5173 during local development) calling this
# API (e.g. http://127.0.0.1:8000) directly via fetch/SSE. Without explicit
# CORS headers, browsers block every cross-origin request outright (curl/
# httpx-based tests never exercise this, since only browsers enforce CORS --
# this gap was only found by running the real Console against the real API
# in a real browser during Phase 6.1 verification).
#
# Read directly at import time, not through config.py's lifespan-scoped
# NexusConfig: `app.add_middleware()` must run before the ASGI app processes
# its first event of any kind (including the lifespan startup event itself
# -- Starlette builds and freezes the middleware stack on first `__call__`),
# so this cannot wait for `lifespan()` to run. Exact-origin allowlisting
# only (never "*"), consistent with tool_policy.py's exact-domain-match
# philosophy elsewhere in this codebase.
# ---------------------------------------------------------------------------

_DEFAULT_CONSOLE_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")


def _load_console_origins() -> list[str]:
    raw = os.getenv("NEXUS_CONSOLE_ORIGINS")
    if not raw:
        return list(_DEFAULT_CONSOLE_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


app = FastAPI(
    title="NEXUS API",
    description="AI Agent Runtime & Orchestration Platform - Connect. Orchestrate. Execute. Observe.",
    version="0.7.0",
    lifespan=lifespan,
)


class _ObservabilityMiddleware:
    """Correlates each HTTP request with NEXUS's existing structured
    observability (see observability.py) -- not a second logging system.
    Never logs request/response bodies (message text, tool content); only
    method, the matched route template, status, and timing, plus
    request_id/thread_id when an endpoint made them available via
    `request.state`. Dynamic path values are not written to logs.

    A raw ASGI middleware (not `starlette.middleware.base.BaseHTTPMiddleware`)
    deliberately: `BaseHTTPMiddleware` runs the downstream app in a separate
    task via `call_next`, which is known to interfere with exception
    handlers registered via `@app.exception_handler` for errors raised deep
    in a route (the 500 path here would otherwise escape FastAPI's own
    handling instead of returning a safe JSON error). A plain ASGI
    middleware wraps `send` instead and has no such interaction.
    """

    def __init__(self, app: FastAPI):
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_holder = {"status_code": 500}

        async def send_wrapper(message) -> None:
            if message["type"] == "http.response.start":
                status_holder["status_code"] = message["status"]
            await send(message)

        request = Request(scope, receive=receive)
        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            observability.log_event(
                "http_request",
                request_id=getattr(request.state, "request_id", None) or "unknown",
                thread_id=request.path_params.get("thread_id", "unknown"),
                method=request.method,
                path_template=getattr(route, "path", "unmatched"),
                status_code=status_holder["status_code"],
                duration_ms=observability.elapsed_ms(start),
            )


app.add_middleware(_ObservabilityMiddleware)
# Added after (so, per Starlette's middleware ordering, wrapped OUTSIDE)
# _ObservabilityMiddleware -- CORS headers must be attached to every
# response, including ones produced by the exception handlers below, and
# CORSMiddleware itself must see and short-circuit preflight OPTIONS
# requests before they reach anything else.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_load_console_origins(),
    allow_methods=["GET", "POST"],
    allow_headers=["Authorization", "Content-Type"],
    # Retry-After isn't in the browser's default CORS-safelisted response
    # header set -- without this, the Console's rate-limit UI couldn't
    # read it on a 429 even though the header is genuinely sent.
    expose_headers=["Retry-After"],
)


@app.exception_handler(ApiError)
async def _api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return _error_response(exc.status_code, exc.code, exc.message, headers=exc.headers)


@app.exception_handler(RequestValidationError)
async def _validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    # FastAPI's default is 422; the request/response contract here (and
    # Phase 3 STEP 10) calls for 400 on an invalid request body, with a
    # safe, generic message -- not the raw pydantic error internals.
    return _error_response(
        status.HTTP_400_BAD_REQUEST, "INVALID_REQUEST", "The request body or parameters were invalid."
    )


def _log_api_error(request: Request, exc: Exception) -> None:
    """Record safe API error metadata through the existing event logger."""
    route = request.scope.get("route")
    observability.log_event(
        "api_error",
        request_id=getattr(request.state, "request_id", None) or "unknown",
        thread_id=request.path_params.get("thread_id", "unknown"),
        error_type=type(exc).__name__,
        method=request.method,
        path_template=getattr(route, "path", "unmatched"),
    )


@app.exception_handler(Exception)
async def _unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    # Do not log exception args or a traceback.
    _log_api_error(request, exc)
    return _error_response(
        status.HTTP_500_INTERNAL_SERVER_ERROR, "INTERNAL_ERROR", "An unexpected error occurred."
    )


def _get_runtime(request: Request) -> nexus_runtime.NexusRuntime:
    return request.app.state.runtime


def _get_run_store(request: Request) -> run_store.RunStore:
    return request.app.state.run_store


def _get_pricing(request: Request) -> pricing_module.PricingTable:
    return request.app.state.pricing


def _get_evaluation_store(request: Request) -> evals_store_module.EvaluationStore:
    return request.app.state.evaluation_store


def _get_config(request: Request) -> config_module.NexusConfig:
    return request.app.state.config


def _get_rate_limiter(request: Request) -> rate_limit.RateLimiter:
    return request.app.state.rate_limiter


async def _require_thread_access(
    runtime: nexus_runtime.NexusRuntime, thread_id: str, principal_id: str
) -> None:
    try:
        await runtime.verify_access(principal_id, thread_id)
    except access.ThreadAccessDenied as exc:
        raise ApiError(
            status.HTTP_403_FORBIDDEN, "THREAD_ACCESS_DENIED", "The requested session cannot be accessed."
        ) from exc


# ---------------------------------------------------------------------------
# Authentication / authorization / rate-limiting dependencies (Phase 5).
#
#   HTTP request -> get_principal (authenticate) -> enforce_rate_limit
#                -> route handler (its own per-resource authorization,
#                   e.g. _require_thread_access, using principal.principal_id)
#
# Every route except /health, /ready, /docs, /openapi.json depends on
# `enforce_rate_limit` (which itself depends on `get_principal`), so
# authentication always runs before rate limiting, which always runs
# before the route body. See auth.py / rate_limit.py for each piece.
# ---------------------------------------------------------------------------


async def get_principal(request: Request) -> auth.Principal:
    app_config = _get_config(request)
    try:
        principal = auth.authenticate(
            request.headers.get("authorization"), configured_token=app_config.api_token
        )
    except auth.AuthenticationError as exc:
        raise ApiError(status.HTTP_401_UNAUTHORIZED, "UNAUTHENTICATED", exc.detail) from exc
    # Available to the observability middleware for request_id/... style
    # correlation if ever needed; never logged as-is elsewhere (only the
    # already-safe principal_id, never a header value -- see auth.py).
    request.state.principal_id = principal.principal_id
    return principal


async def enforce_rate_limit(
    request: Request, principal: auth.Principal = Depends(get_principal)
) -> auth.Principal:
    limiter = _get_rate_limiter(request)
    result = limiter.check(principal.principal_id)
    if not result.allowed:
        retry_after = max(1, int(result.retry_after_seconds or 0))
        raise ApiError(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "RATE_LIMITED",
            "Rate limit exceeded. Retry after the indicated number of seconds.",
            headers={"Retry-After": str(retry_after)},
        )
    return principal


# ---------------------------------------------------------------------------
# Health / readiness
# ---------------------------------------------------------------------------


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Basic process health",
    description="Confirms the API process is running. Does not call the LLM or the checkpointer.",
    tags=["health"],
)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", service="nexus-api")


@app.get(
    "/ready",
    response_model=ReadinessResponse,
    summary="Runtime readiness",
    description=(
        "Confirms NexusRuntime is initialized and its configured SQLite or PostgreSQL checkpointer "
        "is responsive, via a cheap read -- never an LLM call."
    ),
    tags=["health"],
    responses={503: {"model": ReadinessResponse, "description": "Runtime not ready"}},
)
async def ready(request: Request) -> JSONResponse:
    runtime: nexus_runtime.NexusRuntime | None = getattr(request.app.state, "runtime", None)
    if runtime is None:
        body = ReadinessResponse(status="not_ready", service="nexus-api", checkpointer="uninitialized")
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body.model_dump())
    try:
        await runtime.get_state(_READINESS_PROBE_THREAD_ID, principal_id=_READINESS_PRINCIPAL_ID)
    except Exception as exc:
        _log_api_error(request, exc)
        body = ReadinessResponse(status="not_ready", service="nexus-api", checkpointer="error")
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=body.model_dump())
    body = ReadinessResponse(status="ready", service="nexus-api", checkpointer="ok")
    return JSONResponse(status_code=status.HTTP_200_OK, content=body.model_dump())


# ---------------------------------------------------------------------------
# Tools (Phase 6.6)
#
# Registry metadata is static public capability information. Activity is
# projected only from retained runs owned by the authenticated principal.
# ---------------------------------------------------------------------------


_DEFAULT_TOOL_ACTIVITY_LIMIT = 50
_MAX_TOOL_ACTIVITY_LIMIT = 200
_VISIBLE_TOOL_ACTIVITY_TYPES = {"tool_completed", "tool_denied", "tool_failed"}


@app.get(
    "/v1/tools",
    response_model=list[tool_registry.ToolDefinition],
    summary="List registered tools",
    description=(
        "Returns safe, read-only metadata for tools bound to NEXUS agent graphs. Allowed agents "
        "are derived from the enforced tool policy. This static registry has no per-thread "
        "ownership scope."
    ),
    tags=["tools"],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def list_tools(
    principal: auth.Principal = Depends(enforce_rate_limit),
) -> list[tool_registry.ToolDefinition]:
    return tool_registry.list_tools()


@app.get(
    "/v1/tools/activity",
    response_model=ToolActivityResponse,
    summary="List recent retained tool activity",
    description=(
        "Returns completed, denied, and failed tool events from the bounded, process-local run "
        "store. Only events belonging to runs owned by the authenticated caller are included. "
        "This is not a durable or system-wide audit history."
    ),
    tags=["tools"],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def list_tool_activity(
    request: Request,
    limit: int = Query(default=_DEFAULT_TOOL_ACTIVITY_LIMIT, ge=1, le=_MAX_TOOL_ACTIVITY_LIMIT),
    principal: auth.Principal = Depends(enforce_rate_limit),
) -> ToolActivityResponse:
    runtime = _get_runtime(request)
    retained_events: list[tuple[str, str, int, ToolActivityEvent]] = []

    for record in _get_run_store(request).list_recent():
        if await runtime.owner_of(record.thread_id) != principal.principal_id:
            continue
        for index, event in enumerate(record.tool_events):
            if event.event_type not in _VISIBLE_TOOL_ACTIVITY_TYPES:
                continue
            retained_events.append((
                event.timestamp,
                record.request_id,
                index,
                ToolActivityEvent(
                    request_id=record.request_id,
                    tool=event.tool,
                    event_type=event.event_type,
                    agent=record.agent,
                    timestamp=event.timestamp,
                    duration_ms=event.duration_ms,
                    success=event.success,
                    reason=event.reason,
                    error_type=event.error_type,
                ),
            ))

    # ISO timestamps are UTC and sortable. Request ID and stored event index
    # make ties deterministic without changing the historical event format.
    retained_events.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
    visible = [item[3] for item in retained_events[:limit]]
    return ToolActivityResponse(items=visible, total=len(retained_events), limit=limit)


# ---------------------------------------------------------------------------
# Agents (Phase 6.2)
#
# Read-only metadata + capability discovery over the agents main.py
# already implements -- see agents.py's module docstring. Authenticated
# and rate-limited exactly like every other resource endpoint (not
# public/unauthenticated): "normal authenticated API access is
# sufficient" for the current single-token model.
# ---------------------------------------------------------------------------


@app.get(
    "/v1/agents",
    response_model=list[agents_module.AgentDefinition],
    summary="List registered agents",
    description=(
        "Returns the NEXUS agent registry -- typed metadata for every reference agent NEXUS "
        "implements (currently logical/math/coding/counselor), including live status, tool "
        "authorization (from the same tool_policy.AGENT_TOOL_POLICY the runtime itself enforces), "
        "and capabilities. This is the source of truth the Console's Agents page and Playground "
        "agent selector both consume -- never a hardcoded frontend list."
    ),
    tags=["agents"],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def list_agents(
    request: Request, principal: auth.Principal = Depends(enforce_rate_limit)
) -> list[agents_module.AgentDefinition]:
    return agents_module.list_agents()


@app.get(
    "/v1/agents/{agent_id}",
    response_model=agents_module.AgentDefinition,
    summary="Get one agent's metadata",
    description="Looks up a single registered agent by id. Note: an agent that exists but is "
    "currently unavailable still returns 200 with status='unavailable' -- 404 means the id isn't a "
    "registered agent at all.",
    tags=["agents"],
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse, "description": "No such agent is registered"},
        429: {"model": ErrorResponse},
    },
)
async def get_agent(
    agent_id: str, request: Request, principal: auth.Principal = Depends(enforce_rate_limit)
) -> agents_module.AgentDefinition:
    agent = agents_module.get_agent(agent_id)
    if agent is None:
        raise ApiError(
            status.HTTP_404_NOT_FOUND, "AGENT_NOT_FOUND", "No agent with this id is registered."
        )
    return agent


# ---------------------------------------------------------------------------
# Sessions
# ---------------------------------------------------------------------------


@app.post(
    "/v1/sessions",
    response_model=SessionCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new session",
    description=(
        "Creates a new NEXUS thread/session and registers it to the authenticated caller's "
        "principal (see auth.py, access.py). Returns only the thread_id; no conversation exists "
        "yet until a message is sent."
    ),
    tags=["sessions"],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def create_session(
    request: Request, principal: auth.Principal = Depends(enforce_rate_limit)
) -> SessionCreateResponse:
    runtime = _get_runtime(request)
    thread_id = await runtime.new_session(principal_id=principal.principal_id)
    return SessionCreateResponse(thread_id=thread_id)


def _extract_session_messages(raw_messages: list) -> list[SessionMessage]:
    """LangChain `BaseMessage` objects -> the safe `SessionMessage` shape.
    `role`/`content` only - never `additional_kwargs`, `response_metadata`,
    tool_calls, or any other LangChain-internal field, none of which are
    part of NEXUS's own API contract."""
    return [
        SessionMessage(role=getattr(m, "type", "unknown"), content=str(getattr(m, "content", "")))
        for m in raw_messages
    ]


_DEFAULT_SESSIONS_LIST_LIMIT = 50
_MAX_SESSIONS_LIST_LIMIT = 200


def _to_session_response(
    thread_id: str, values: dict, updated_at: str | None, *, include_messages: bool
) -> SessionResponse:
    raw_messages = values.get("messages", [])
    return SessionResponse(
        thread_id=thread_id,
        status="active",
        message_count=len(raw_messages),
        last_message_type=values.get("message_type"),
        last_route=values.get("route"),
        updated_at=updated_at,
        messages=_extract_session_messages(raw_messages) if include_messages else None,
    )


@app.get(
    "/v1/sessions",
    response_model=SessionListResponse,
    summary="List recent sessions",
    description=(
        "Lists this principal's sessions (threads with at least one persisted turn), most "
        "recently updated first, discovered directly from the LangGraph checkpointer's own state "
        "(see runtime.NexusRuntime.list_sessions) - not a separate session database. A session "
        "older than the checkpoint scan window won't appear; see README 'Known limitations'. "
        "List items never include full message content (see GET /v1/sessions/{thread_id})."
    ),
    tags=["sessions"],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def list_sessions(
    request: Request,
    limit: int = Query(default=_DEFAULT_SESSIONS_LIST_LIMIT, ge=1, le=_MAX_SESSIONS_LIST_LIMIT),
    principal: auth.Principal = Depends(enforce_rate_limit),
) -> SessionListResponse:
    runtime = _get_runtime(request)
    snapshots = await runtime.list_sessions(principal.principal_id, limit=limit)
    items = [
        _to_session_response(s.thread_id, s.values, s.updated_at, include_messages=False) for s in snapshots
    ]
    return SessionListResponse(items=items, limit=limit)


@app.get(
    "/v1/sessions/{thread_id}",
    response_model=SessionResponse,
    summary="Get session information",
    description=(
        "Returns session metadata (message count, last classification/route) plus the full "
        "message history (role/content only - no internal checkpoint structures, no tool "
        "payloads, no provider metadata)."
    ),
    tags=["sessions"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse, "description": "Thread not owned by this principal"},
        404: {"model": ErrorResponse, "description": "Session not found"},
        429: {"model": ErrorResponse},
    },
)
async def get_session(
    thread_id: str, request: Request, principal: auth.Principal = Depends(enforce_rate_limit)
) -> SessionResponse:
    runtime = _get_runtime(request)
    await _require_thread_access(runtime, thread_id, principal.principal_id)
    snapshot = await runtime.get_state(thread_id, principal_id=principal.principal_id)
    if not snapshot.values:
        raise ApiError(status.HTTP_404_NOT_FOUND, "SESSION_NOT_FOUND", "No session exists for this thread_id.")
    return _to_session_response(thread_id, snapshot.values, snapshot.created_at, include_messages=True)


# ---------------------------------------------------------------------------
# Messages -- the only endpoint that actually executes the agent graph.
# ---------------------------------------------------------------------------


@app.post(
    "/v1/sessions/{thread_id}/messages",
    response_model=MessageResponse,
    summary="Send a message and execute one turn",
    description=(
        "Runs one turn of the NEXUS agent graph via NexusRuntime.execute() -- classification, "
        "routing, and the selected specialist agent (with its tools, subject to Phase 2 policy). "
        "Always returns HTTP 200 with a safe reply, exactly as the CLI would show -- never a "
        "provider stack trace. status='completed' covers both a real answer AND a node-level "
        "failure absorbed into a safe fallback reply (Phase 0 behavior: the turn still completed). "
        "status='failed' is reserved for the rarer case of a failure outside any node's own "
        "handling (e.g. the checkpointer itself). See README 'API timeouts'."
    ),
    tags=["messages"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse, "description": "Thread not owned by this principal"},
        429: {"model": ErrorResponse},
    },
)
async def send_message(
    thread_id: str,
    body: MessageRequest,
    request: Request,
    principal: auth.Principal = Depends(enforce_rate_limit),
) -> MessageResponse:
    runtime = _get_runtime(request)
    await _require_thread_access(runtime, thread_id, principal.principal_id)

    # execute_and_record (run_store.py) captures this execution's structured
    # events and records a RunRecord -- the same helper the Phase 4
    # evaluation runner uses, so this endpoint and `evals/` never disagree
    # about what "what happened during a run" means.
    record = await run_store.execute_and_record(
        runtime,
        thread_id,
        body.message,
        principal_id=principal.principal_id,
        store=_get_run_store(request),
        pricing_table=_get_pricing(request),
        agent=body.agent,
    )
    request.state.request_id = record.request_id

    return MessageResponse(
        thread_id=record.thread_id,
        request_id=record.request_id,
        response=record.reply,
        route=record.route,
        status=record.status,
        duration_ms=record.duration_ms,
    )


# ---------------------------------------------------------------------------
# Streaming (Phase 5) -- Server-Sent Events over the SAME execution model
# and the SAME structured observability events as the synchronous endpoint
# above. Does not replace it: POST .../messages continues to work exactly
# as before, independent of this endpoint.
# ---------------------------------------------------------------------------


def _format_sse(event_type: str, payload: dict[str, Any]) -> str:
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


_TERMINAL_WORKFLOW_EVENTS = {"workflow_completed", "workflow_failed"}


async def _sse_event_source(
    runtime: nexus_runtime.NexusRuntime,
    thread_id: str,
    user_text: str,
    *,
    principal_id: str,
    store: run_store.RunStore,
    pricing_table: pricing_module.PricingTable,
    agent: str | None = None,
    replay_context_available: bool = False,
) -> AsyncIterator[str]:
    """Runs one turn while forwarding NEXUS's existing structured lifecycle
    events to the caller live, via `observability.stream_events`. Ends with
    one additional `run_completed` event carrying the actual reply (the
    same content the synchronous endpoint already returns in its JSON body
    -- observability events themselves deliberately never carry message
    content; see observability.py).

    Lifecycle handling (see ARCHITECTURE.md "SSE concurrency/lifecycle"):
    - Normal completion / workflow failure / a failed node absorbed into a
      safe fallback reply: all three surface via the normal
      `workflow_completed`/`workflow_failed` event NEXUS already emits
      (`NexusRuntime.execute` always emits exactly one of these before
      returning), which is what ends the loop below.
    - Client disconnect / cancellation: Starlette closes this generator
      (raising `GeneratorExit` at the current `await`), which the
      `finally` block below turns into cancelling the still-running
      `execute()` task -- nothing is left running in the background.
    - The turn's own timeouts are unchanged (`LLM_TIMEOUT_SECONDS` /
      `AGENT_TIMEOUT_SECONDS` / `FETCH_TIMEOUT_SECONDS`); this endpoint adds
      no separate timeout layer, exactly like the synchronous one.
    """
    request_id = nexus_runtime.new_request_id()
    started_at = run_store._now_iso()
    collected_events: list[dict[str, Any]] = []

    with observability.stream_events(request_id) as queue:
        task = asyncio.create_task(
            runtime.execute(
                thread_id, user_text, principal_id=principal_id, request_id=request_id, agent=agent
            ),
            name=f"nexus-sse-execute-{request_id}",
        )
        try:
            while True:
                event = await queue.get()
                collected_events.append(event)
                yield _format_sse(event.get("event_type", "unknown"), event)
                if event.get("event_type") in _TERMINAL_WORKFLOW_EVENTS:
                    break
            result = await task
        finally:
            if not task.done():
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task

    completed_at = run_store._now_iso()
    record = run_store.build_run_record(
        result,
        collected_events,
        started_at=started_at,
        completed_at=completed_at,
        pricing_table=pricing_table,
        original_input=user_text,
        requested_agent=agent,
        replay_context_available=replay_context_available,
    )
    store.record(record)

    yield _format_sse(
        "run_completed",
        {
            "request_id": record.request_id,
            "thread_id": record.thread_id,
            "status": record.status,
            "success": record.success,
            "route": record.route,
            "reply": record.reply,
            "duration_ms": record.duration_ms,
            "timestamp": completed_at,
        },
    )


@app.post(
    "/v1/sessions/{thread_id}/messages/stream",
    summary="Send a message and stream execution events live (SSE)",
    description=(
        "Runs the exact same NexusRuntime.execute() turn as POST .../messages, but streams "
        "NEXUS's existing structured lifecycle events (workflow_started, classifier_started, "
        "route_selected, agent_started, tool_started/completed/denied, agent_completed, "
        "workflow_completed/failed) live via Server-Sent Events as the turn progresses, ending "
        "with one additional 'run_completed' event carrying the reply. Each event includes "
        "request_id/thread_id for correlation and a timestamp. Does not replace the synchronous "
        "endpoint, which continues to work independently. See ARCHITECTURE.md 'SSE streaming'."
    ),
    tags=["messages"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse, "description": "Thread not owned by this principal"},
        429: {"model": ErrorResponse},
    },
)
async def stream_message(
    thread_id: str,
    body: MessageRequest,
    request: Request,
    principal: auth.Principal = Depends(enforce_rate_limit),
) -> StreamingResponse:
    runtime = _get_runtime(request)
    await _require_thread_access(runtime, thread_id, principal.principal_id)
    replay_context_available = not await run_store.thread_has_prior_state(
        runtime, thread_id, principal_id=principal.principal_id
    )

    return StreamingResponse(
        _sse_event_source(
            runtime,
            thread_id,
            body.message,
            principal_id=principal.principal_id,
            store=_get_run_store(request),
            pricing_table=_get_pricing(request),
            agent=body.agent,
            replay_context_available=replay_context_available,
        ),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


# ---------------------------------------------------------------------------
# Runs
# ---------------------------------------------------------------------------

_DEFAULT_RUNS_LIST_LIMIT = 50
_MAX_RUNS_LIST_LIMIT = 200


@app.get(
    "/v1/runs",
    response_model=RunListResponse,
    summary="List recent executions",
    description=(
        "Lists runs from the API's bounded, in-process run store (see run_store.py / "
        "NEXUS_RUN_REGISTRY_SIZE), most recent first. This is NOT a persistent audit log or a "
        "durable run database: it only reflects runs executed since this API process started, up "
        "to the store's capacity, and the list is empty again after a restart. Only runs whose "
        "thread this principal owns are ever included -- a caller can never discover another "
        "principal's runs, including their existence, through this endpoint. Optional "
        "limit/status/agent/route/thread_id (Phase 6.4) filters are all applied server-side."
    ),
    tags=["runs"],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def list_runs(
    request: Request,
    limit: int = Query(default=_DEFAULT_RUNS_LIST_LIMIT, ge=1, le=_MAX_RUNS_LIST_LIMIT),
    status_filter: str | None = Query(default=None, alias="status"),
    agent: str | None = Query(default=None),
    route: str | None = Query(default=None),
    thread_id: str | None = Query(
        default=None, description="Phase 6.4: restrict to runs on this thread - used by Session "
        "Detail's 'View Runs' link. Ownership is still checked per-record exactly as without "
        "this filter; a thread_id belonging to another principal simply matches nothing."
    ),
    principal: auth.Principal = Depends(enforce_rate_limit),
) -> RunListResponse:
    runtime = _get_runtime(request)
    matched: list[run_store.RunRecord] = []
    for record in _get_run_store(request).list_recent():
        if status_filter is not None and record.status != status_filter:
            continue
        if agent is not None and record.agent != agent:
            continue
        if route is not None and record.route != route:
            continue
        if thread_id is not None and record.thread_id != thread_id:
            continue
        # Ownership check last (the one call that can genuinely be slow
        # under the Postgres access backend) so it only runs for records
        # that already passed the cheap in-memory filters above.
        owner = await runtime.owner_of(record.thread_id)
        if owner != principal.principal_id:
            continue
        matched.append(record)

    return RunListResponse(
        items=[_to_run_response(record) for record in matched[:limit]],
        total=len(matched),
        limit=limit,
    )


@app.get(
    "/v1/runs/summary",
    response_model=RunSummaryListResponse,
    summary="List lightweight summaries of recent executions",
    description=(
        "Returns only summary fields for caller-owned runs in the bounded, process-local RunStore. "
        "It omits thread IDs, final responses, lifecycle traces, and tool event details so overview "
        "surfaces do not need to fetch full run records. History resets when this API process "
        "restarts and is not a durable analytics store."
    ),
    tags=["runs"],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def list_run_summaries(
    request: Request,
    limit: int = Query(default=10, ge=1, le=50),
    principal: auth.Principal = Depends(enforce_rate_limit),
) -> RunSummaryListResponse:
    runtime = _get_runtime(request)
    owned: list[run_store.RunRecord] = []
    for record in _get_run_store(request).list_recent():
        if await runtime.owner_of(record.thread_id) == principal.principal_id:
            owned.append(record)
    summaries = [
        RunListItemSummary(
            request_id=record.request_id,
            status=record.status,
            route=record.route,
            agent=record.agent,
            duration_ms=record.duration_ms,
            success=record.success,
            created_at=record.completed_at,
            started_at=record.started_at,
            completed_at=record.completed_at,
            usage=record.usage,
            cost_usd=record.cost_usd,
        )
        for record in owned[:limit]
    ]
    return RunSummaryListResponse(items=summaries, total=len(owned), limit=limit)


async def _get_owned_run_record_or_404(
    request: Request, request_id: str, principal_id: str
) -> run_store.RunRecord:
    """Read one owned run without revealing whether another principal owns it."""
    record = _get_run_store(request).get(request_id)
    if record is None or await _get_runtime(request).owner_of(record.thread_id) != principal_id:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "RUN_NOT_FOUND",
            "No run with this request_id is available.",
        )
    return record


@app.get(
    "/v1/runs/compare/{request_id_a}/{request_id_b}",
    response_model=RunComparisonResponse,
    summary="Compare two retained runs",
    description=(
        "Returns both caller-owned run records and factual B-minus-A deltas. Missing token or cost "
        "data produces null deltas. This endpoint is read-only and does not rank either run."
    ),
    tags=["runs"],
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse, "description": "A run is unavailable to this principal"},
        429: {"model": ErrorResponse},
    },
)
async def compare_runs(
    request_id_a: str,
    request_id_b: str,
    request: Request,
    principal: auth.Principal = Depends(enforce_rate_limit),
) -> RunComparisonResponse:
    if request_id_a == request_id_b:
        raise ApiError(status.HTTP_400_BAD_REQUEST, "SAME_RUN", "Choose two different runs to compare.")
    run_a = await _get_owned_run_record_or_404(request, request_id_a, principal.principal_id)
    run_b = await _get_owned_run_record_or_404(request, request_id_b, principal.principal_id)
    return RunComparisonResponse(
        run_a=_to_run_response(run_a),
        run_b=_to_run_response(run_b),
        deltas=run_store.compare_runs(run_a, run_b),
    )


@app.post(
    "/v1/runs/{request_id}/replay",
    response_model=RunResponse,
    summary="Re-run an eligible retained run",
    description=(
        "Executes the retained original input through NexusRuntime in a new owned session, creating "
        "a new request ID and run. Only first-turn runs with retained input are eligible; earlier "
        "conversation state is not reconstructed. The source run is unchanged. This is a fresh "
        "re-run, not deterministic replay."
    ),
    tags=["runs"],
    responses={
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse, "description": "Source run is unavailable to this principal"},
        409: {"model": ErrorResponse, "description": "The source run does not have safely replayable input/context"},
        429: {"model": ErrorResponse},
    },
)
async def replay_run(
    request_id: str,
    request: Request,
    principal: auth.Principal = Depends(enforce_rate_limit),
) -> RunResponse:
    source = await _get_owned_run_record_or_404(request, request_id, principal.principal_id)
    store = _get_run_store(request)
    if not source.replayable or source.original_input is None:
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "RUN_NOT_REPLAYABLE",
            "This run cannot be re-run because its input or original conversation context is unavailable.",
        )
    if not store.can_record_preserving(source.request_id):
        raise ApiError(
            status.HTTP_409_CONFLICT,
            "RUN_STORE_CAPACITY",
            "The bounded run store cannot retain both this source run and a new re-run.",
        )

    runtime = _get_runtime(request)
    replay_thread_id = await runtime.new_session(principal_id=principal.principal_id)
    replay = await run_store.execute_and_record(
        runtime,
        replay_thread_id,
        source.original_input,
        principal_id=principal.principal_id,
        store=store,
        pricing_table=_get_pricing(request),
        agent=source.requested_agent,
        replay_of=source.request_id,
        preserve_request_id=source.request_id,
    )
    request.state.request_id = replay.request_id
    return _to_run_response(replay)


@app.get(
    "/v1/runs/{request_id}",
    response_model=RunResponse,
    summary="Get information about a specific execution",
    description=(
        "Looks up a run in the API's bounded, in-process run store (see run_store.py / "
        "NEXUS_RUN_REGISTRY_SIZE). This is NOT a persistent audit log: it only has runs executed "
        "since this API process started, up to the store's capacity, and is lost on restart. "
        "Includes structured lifecycle events, tool activity, token usage, and cost when available "
        "-- all metadata, never message/tool content or secrets."
    ),
    tags=["runs"],
    responses={
        401: {"model": ErrorResponse},
        403: {"model": ErrorResponse, "description": "Run's thread not owned by this principal"},
        404: {"model": ErrorResponse, "description": "Run not found in the in-process registry"},
        429: {"model": ErrorResponse},
    },
)
async def get_run(
    request_id: str, request: Request, principal: auth.Principal = Depends(enforce_rate_limit)
) -> RunResponse:
    record = _get_run_store(request).get(request_id)
    if record is None:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "RUN_NOT_FOUND",
            "No run with this request_id is available (it may predate this API process or have "
            "been evicted from the bounded in-process registry).",
        )
    # A caller cannot retrieve another principal's run merely by knowing/
    # guessing its request_id -- ownership is checked via the SAME thread-
    # access boundary every other endpoint uses, keyed off the run's own
    # thread_id (every run, including evaluation-created ones, belongs to
    # exactly one thread owned by exactly one principal -- see access.py).
    await _require_thread_access(_get_runtime(request), record.thread_id, principal.principal_id)
    return _to_run_response(record)


# ---------------------------------------------------------------------------
# Evaluations (Phase 4)
#
# Synchronous by design: intended for small local evaluation suites (see
# evals/datasets/baseline.json). A future production implementation of
# larger/longer evaluations should use a background job/queue instead of
# blocking an HTTP request for the whole run -- not implemented here.
# ---------------------------------------------------------------------------

_DEFAULT_EVALUATIONS_LIST_LIMIT = 50
_MAX_EVALUATIONS_LIST_LIMIT = 200


@app.get(
    "/v1/evaluations",
    response_model=EvaluationListResponse,
    summary="List recent evaluations",
    description=(
        "Lists lightweight summaries from the bounded, process-local EvaluationStore, newest "
        "first. History is cleared on restart or eviction. Only evaluations owned by the caller "
        "are included; per-case results are available from the detail endpoints."
    ),
    tags=["evaluations"],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def list_evaluations(
    request: Request,
    limit: int = Query(default=_DEFAULT_EVALUATIONS_LIST_LIMIT, ge=1, le=_MAX_EVALUATIONS_LIST_LIMIT),
    principal: auth.Principal = Depends(enforce_rate_limit),
) -> EvaluationListResponse:
    owned = [
        evaluation.summary
        for evaluation in _get_evaluation_store(request).list_recent()
        if evaluation.owner_principal_id == principal.principal_id
    ]
    return EvaluationListResponse(items=owned[:limit], total=len(owned), limit=limit)


def _get_evaluation_or_404(request: Request, evaluation_id: str, principal: auth.Principal) -> EvaluationRun:
    run = _get_evaluation_store(request).get(evaluation_id)
    if run is None:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "EVALUATION_NOT_FOUND",
            "No evaluation with this evaluation_id is available (it may predate this API process "
            "or have been evicted from the bounded in-process store).",
        )
    # Ownership check (Phase 5): an authenticated caller must not retrieve
    # another caller's evaluation merely by knowing/guessing its
    # evaluation_id. `owner_principal_id` is set by `create_evaluation`
    # below to whichever principal triggered the run; `None` only occurs
    # for evaluations that never went through this API (see
    # evals/models.py's EvaluationRun docstring) and is treated as
    # "belongs to no one" -- not returned to anyone but 404, same as an
    # evaluation that doesn't exist, so a caller can't distinguish
    # "exists but isn't yours" from "never existed".
    if run.owner_principal_id != principal.principal_id:
        raise ApiError(
            status.HTTP_404_NOT_FOUND,
            "EVALUATION_NOT_FOUND",
            "No evaluation with this evaluation_id is available (it may predate this API process "
            "or have been evicted from the bounded in-process store).",
        )
    return run


@app.post(
    "/v1/evaluations",
    response_model=EvaluationSummary,
    status_code=status.HTTP_201_CREATED,
    summary="Run the baseline evaluation dataset",
    description=(
        "Synchronously executes every case in the checked-in baseline evaluation dataset "
        "(evals/datasets/baseline.json) against this API's live NexusRuntime -- one real agent "
        "turn per case, each on its own isolated eval-* thread, fully separate from normal "
        "sessions. Returns the summary; see the /results and /metrics endpoints for detail. "
        "Synchronous and intended for small suites -- see the section note above."
    ),
    tags=["evaluations"],
    responses={401: {"model": ErrorResponse}, 429: {"model": ErrorResponse}},
)
async def create_evaluation(
    request: Request, principal: auth.Principal = Depends(enforce_rate_limit)
) -> EvaluationSummary:
    try:
        dataset = dataset_module.load_dataset()
    except dataset_module.DatasetError as exc:
        raise ApiError(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "DATASET_ERROR",
            "The baseline evaluation dataset could not be loaded.",
        ) from exc

    # principal_id=principal.principal_id (the authenticated caller, not a
    # hardcoded constant): the API is the one asking the runtime for this
    # work, exactly as for sessions/messages -- so a later
    # GET /v1/runs/{request_id} for one of these runs is checked against,
    # and succeeds against, the same principal that owns it. See
    # evaluator.run_case's docstring.
    run = await evaluator_module.run_evaluation(
        _get_runtime(request),
        dataset,
        _get_run_store(request),
        pricing_table=_get_pricing(request),
        principal_id=principal.principal_id,
    )
    run.owner_principal_id = principal.principal_id
    _get_evaluation_store(request).record(run)
    return run.summary


@app.get(
    "/v1/evaluations/{evaluation_id}",
    response_model=EvaluationSummary,
    summary="Get an evaluation's summary",
    description="Aggregate pass/fail counts, routing/execution/tool rates, and latency/token/cost metrics for one evaluation run. Only the principal that triggered it may retrieve it.",
    tags=["evaluations"],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse, "description": "Evaluation not found, or not owned by this principal"}, 429: {"model": ErrorResponse}},
)
async def get_evaluation(
    evaluation_id: str, request: Request, principal: auth.Principal = Depends(enforce_rate_limit)
) -> EvaluationSummary:
    return _get_evaluation_or_404(request, evaluation_id, principal).summary


@app.get(
    "/v1/evaluations/{evaluation_id}/results",
    response_model=list[EvaluationResult],
    summary="Get an evaluation's per-case results",
    description="Every case's pass/fail outcome per dimension (routing/execution/tools/response/latency), plus its full captured run data. Only the principal that triggered it may retrieve it.",
    tags=["evaluations"],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse, "description": "Evaluation not found, or not owned by this principal"}, 429: {"model": ErrorResponse}},
)
async def get_evaluation_results(
    evaluation_id: str, request: Request, principal: auth.Principal = Depends(enforce_rate_limit)
) -> list[EvaluationResult]:
    return _get_evaluation_or_404(request, evaluation_id, principal).results


@app.get(
    "/v1/evaluations/{evaluation_id}/metrics",
    response_model=RunMetrics,
    summary="Get an evaluation's aggregate metrics",
    description="Latency (min/max/mean/p50/p95/p99) and token/cost totals for one evaluation run. Fields are null, never estimated, when the underlying data wasn't available.",
    tags=["evaluations"],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse, "description": "Evaluation not found, or not owned by this principal"}, 429: {"model": ErrorResponse}},
)
async def get_evaluation_metrics(
    evaluation_id: str, request: Request, principal: auth.Principal = Depends(enforce_rate_limit)
) -> RunMetrics:
    return _get_evaluation_or_404(request, evaluation_id, principal).summary.metrics


@app.get(
    "/v1/evaluations/compare/{evaluation_id_a}/{evaluation_id_b}",
    response_model=ComparisonResult,
    summary="Compare two evaluation runs",
    description=(
        "Measurable deltas (B minus A) between two evaluation runs' routing accuracy, execution "
        "success rate, tool success rate, p50/p95/p99 latency, and total cost. No subjective "
        "labels ('better'/'worse') -- deltas only; a metric missing from either run makes that "
        "delta null. Both evaluations must be owned by the calling principal."
    ),
    tags=["evaluations"],
    responses={401: {"model": ErrorResponse}, 404: {"model": ErrorResponse, "description": "One or both evaluations not found, or not owned by this principal"}, 429: {"model": ErrorResponse}},
)
async def compare_evaluations(
    evaluation_id_a: str,
    evaluation_id_b: str,
    request: Request,
    principal: auth.Principal = Depends(enforce_rate_limit),
) -> ComparisonResult:
    run_a = _get_evaluation_or_404(request, evaluation_id_a, principal)
    run_b = _get_evaluation_or_404(request, evaluation_id_b, principal)
    return eval_metrics_module.compare(run_a.summary, run_b.summary)
