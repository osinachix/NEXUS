"""NEXUS run/trace store (Phase 4).

Captures structured execution information for a single `NexusRuntime.execute()`
call, built entirely from the SAME observability event stream `main.py`'s
nodes already emit (via `observability.capture_events()`) -- not a second
logging or event system, and nothing here is inferred from natural-language
response text (see the module docstring in `evals/cases.py` for why that
matters for tool-usage checks specifically).

Bounded, in-process, NOT a database, NOT durable across restarts (see
`RunStore`). Both `api.py` (live HTTP traffic) and `evals/evaluator.py`
(the evaluation runner) call `execute_and_record` -- the one place this
capture-then-build logic lives, so neither reimplements it. The public
shape (`RunRecord`) is a stable Pydantic model specifically so a future
persistent backend could replace `RunStore` without changing what callers
of `api.py`/`evals` read.
"""

from __future__ import annotations

import os
from collections import OrderedDict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

import observability
import pricing as pricing_module

if TYPE_CHECKING:
    from runtime import ExecutionResult, NexusRuntime

DEFAULT_MAX_SIZE = int(os.getenv("NEXUS_RUN_REGISTRY_SIZE", "500"))

_TOOL_EVENT_TYPES = {"tool_started", "tool_completed", "tool_denied", "tool_failed"}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RunEvent(BaseModel):
    """A safe, typed projection of one captured observability event --
    metadata only, exactly what observability.py already guarantees never
    contains message content, secrets, or credentials (see SECURITY.md)."""

    event_type: str
    node: str | None = None
    duration_ms: float | None = None
    success: bool | None = None
    error_type: str | None = None
    route: str | None = Field(
        None, description="Only present on a route_selected event -- the classifier's chosen route."
    )
    timestamp: str


class ToolEvent(BaseModel):
    tool: str
    event_type: str
    duration_ms: float | None = None
    success: bool | None = None
    reason: str | None = Field(None, description="Stable denial reason code, if this was a tool_denied event.")
    error_type: str | None = None
    timestamp: str


class TokenUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class RunRecord(BaseModel):
    """Everything NEXUS can honestly report about one execution. Every
    field is either a direct pass-through of real, already-safe
    observability data or explicitly `None` when unavailable -- nothing is
    inferred or estimated silently (see pricing.py for cost specifically).
    """

    request_id: str
    thread_id: str
    status: str = Field(..., description="'completed' or 'failed' -- see NexusRuntime.execute().")
    success: bool
    route: str | None = None
    agent: str | None = Field(
        None, description="Which specialist agent actually ran, from the agent_started event's node "
        "-- unlike `route`, this is populated for BOTH auto-route AND direct-agent runs (a "
        "direct-agent turn has no route_selected event, so `route` alone can't identify the agent)."
    )
    message_type: str | None = None
    reply: str
    started_at: str
    completed_at: str
    duration_ms: float
    events: list[RunEvent] = Field(default_factory=list)
    tool_events: list[ToolEvent] = Field(default_factory=list)
    usage: TokenUsage | None = None
    cost_usd: float | None = Field(
        None, description="USD cost, or null if usage or pricing wasn't available -- see pricing.py."
    )
    error_type: str | None = Field(
        None, description="From workflow_failed if the run failed outright, else the last node-level "
        "failure's error_type if any (the run can still be status='completed' -- see Phase 0's "
        "node-level fallback behavior)."
    )
    # The input is retained only in the bounded process-local store so an
    # eligible first-turn run can be re-executed. Pydantic excludes it from
    # serialization by default; api.py also never maps it into RunResponse.
    original_input: str | None = Field(default=None, exclude=True, repr=False)
    requested_agent: str | None = Field(default=None, exclude=True, repr=False)
    replayable: bool = False
    replay_unavailable_reason: str | None = None
    replay_of: str | None = None


class RunComparisonDeltas(BaseModel):
    """Measurable B-minus-A differences; null means an input metric was unavailable."""

    duration_ms: float | None
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cost_usd: float | None
    tool_event_count: int


def _delta(value_a: float | int | None, value_b: float | int | None) -> float | int | None:
    if value_a is None or value_b is None:
        return None
    return value_b - value_a


def compare_runs(run_a: RunRecord, run_b: RunRecord) -> RunComparisonDeltas:
    """Return factual B-minus-A deltas without ranking or mutating either run."""
    usage_a = run_a.usage
    usage_b = run_b.usage
    return RunComparisonDeltas(
        duration_ms=_delta(run_a.duration_ms, run_b.duration_ms),
        input_tokens=_delta(usage_a.input_tokens if usage_a else None, usage_b.input_tokens if usage_b else None),
        output_tokens=_delta(usage_a.output_tokens if usage_a else None, usage_b.output_tokens if usage_b else None),
        total_tokens=_delta(usage_a.total_tokens if usage_a else None, usage_b.total_tokens if usage_b else None),
        cost_usd=_delta(run_a.cost_usd, run_b.cost_usd),
        tool_event_count=len(run_b.tool_events) - len(run_a.tool_events),
    )


def _extract_route_and_message_type(events: list[dict[str, Any]]) -> tuple[str | None, str | None]:
    for event in events:
        if event.get("event_type") == "route_selected":
            return event.get("route"), event.get("message_type")
    return None, None


def _extract_agent(events: list[dict[str, Any]]) -> str | None:
    """Which specialist agent actually ran, from the one `agent_started`
    event's `node` field -- works uniformly for auto-route AND
    direct-agent runs (see `RunRecord.agent`'s docstring for why `route`
    alone isn't enough)."""
    for event in events:
        if event.get("event_type") == "agent_started" and event.get("node"):
            return event["node"]
    return None


def _extract_model_name(events: list[dict[str, Any]]) -> str | None:
    for event in reversed(events):
        if event.get("model_name"):
            return event["model_name"]
    return None


def _extract_tool_events(events: list[dict[str, Any]]) -> list[ToolEvent]:
    return [
        ToolEvent(
            tool=event.get("tool", "unknown"),
            event_type=event["event_type"],
            duration_ms=event.get("duration_ms"),
            success=event.get("success"),
            reason=event.get("reason"),
            error_type=event.get("error_type"),
            timestamp=event.get("timestamp", ""),
        )
        for event in events
        if event.get("event_type") in _TOOL_EVENT_TYPES
    ]


def _aggregate_usage(events: list[dict[str, Any]]) -> TokenUsage | None:
    totals: dict[str, int] = {}
    found = False
    for event in events:
        usage = event.get("usage")
        if not usage:
            continue
        found = True
        for key in ("input_tokens", "output_tokens", "total_tokens"):
            value = usage.get(key)
            if value is not None:
                totals[key] = totals.get(key, 0) + value
    if not found:
        return None
    return TokenUsage(
        input_tokens=totals.get("input_tokens"),
        output_tokens=totals.get("output_tokens"),
        total_tokens=totals.get("total_tokens"),
    )


def _extract_error_type(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        if event.get("event_type") == "workflow_failed" and event.get("error_type"):
            return event["error_type"]
    for event in reversed(events):
        if event.get("success") is False and event.get("error_type"):
            return event["error_type"]
    return None


class RunStore:
    """Bounded, in-process, oldest-evicted-first run registry. NOT a
    database and NOT durable -- resets on every process restart. See
    README "Known limitations". `max_size` defaults to the same
    `NEXUS_RUN_REGISTRY_SIZE` env var used since Phase 3.
    """

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE):
        self._max_size = max_size
        self._records: OrderedDict[str, RunRecord] = OrderedDict()

    def can_record_preserving(self, request_id: str) -> bool:
        """Whether another record can be added while retaining this source run."""
        if self._max_size < 2 and len(self._records) >= self._max_size:
            return False
        if len(self._records) < self._max_size:
            return True
        return any(existing_id != request_id for existing_id in self._records)

    def record(self, run: RunRecord, *, preserve_request_id: str | None = None) -> None:
        if preserve_request_id is not None and not self.can_record_preserving(preserve_request_id):
            raise ValueError("RunStore cannot retain the new run and its protected source run.")
        self._records[run.request_id] = run
        self._records.move_to_end(run.request_id)
        while len(self._records) > self._max_size:
            oldest_evictable = next(
                (request_id for request_id in self._records if request_id != preserve_request_id),
                None,
            )
            if oldest_evictable is None:
                raise ValueError("RunStore cannot retain the new run and its protected source run.")
            del self._records[oldest_evictable]

    def get(self, request_id: str) -> RunRecord | None:
        return self._records.get(request_id)

    def list_recent(self) -> list[RunRecord]:
        """Every currently-stored run, most-recently-recorded first (Phase
        6.3). Returns the full bounded set -- filtering by caller,
        status/agent/route, and any result limit is the API layer's job
        (api.py's `list_runs`), not this store's; keeping this method dumb
        is what keeps `RunStore` from growing into a query engine."""
        return list(reversed(self._records.values()))


def build_run_record(
    result: "ExecutionResult",
    events: list[dict[str, Any]],
    *,
    started_at: str,
    completed_at: str,
    pricing_table: pricing_module.PricingTable | None = None,
    original_input: str | None = None,
    requested_agent: str | None = None,
    replay_context_available: bool = False,
    replay_of: str | None = None,
) -> RunRecord:
    """Build a `RunRecord` from an already-completed `ExecutionResult` and
    its already-filtered (by request_id) list of captured structured
    events. Pulled out of `execute_and_record` below so a caller that
    can't use that helper directly -- specifically the Phase 5 SSE
    endpoint (api.py), which must consume events live via
    `observability.stream_events` rather than all-at-once via
    `observability.capture_events` -- can still build the exact same
    `RunRecord` shape from the events it collected while streaming, instead
    of duplicating this extraction logic.
    """
    pricing_table = pricing_table or {}
    route, message_type = _extract_route_and_message_type(events)
    model_name = _extract_model_name(events)
    usage = _aggregate_usage(events)
    cost_usd = pricing_module.calculate_cost_usd(
        model_name=model_name,
        input_tokens=usage.input_tokens if usage else None,
        output_tokens=usage.output_tokens if usage else None,
        pricing=pricing_table,
    )

    return RunRecord(
        request_id=result.request_id,
        thread_id=result.thread_id,
        status="completed" if result.success else "failed",
        success=result.success,
        route=route,
        agent=_extract_agent(events),
        message_type=message_type,
        reply=result.reply,
        started_at=started_at,
        completed_at=completed_at,
        duration_ms=result.duration_ms,
        events=[
            RunEvent(
                event_type=event["event_type"],
                node=event.get("node"),
                duration_ms=event.get("duration_ms"),
                success=event.get("success"),
                error_type=event.get("error_type"),
                route=event.get("route"),
                timestamp=event.get("timestamp", ""),
            )
            for event in events
        ],
        tool_events=_extract_tool_events(events),
        usage=usage,
        cost_usd=cost_usd,
        error_type=_extract_error_type(events),
        original_input=original_input,
        requested_agent=requested_agent,
        replayable=original_input is not None and replay_context_available,
        replay_unavailable_reason=(
            None
            if original_input is not None and replay_context_available
            else "input_not_retained"
            if original_input is None
            else "thread_has_prior_state"
        ),
        replay_of=replay_of,
    )


async def thread_has_prior_state(runtime: "NexusRuntime", thread_id: str, *, principal_id: str) -> bool:
    """Whether a run would need earlier conversation state to be repeated.

    Replay intentionally supports only a thread's first turn. The RunStore
    does not snapshot earlier messages, so later turns cannot be accurately
    re-created in an isolated new thread.
    """
    snapshot = await runtime.get_state(thread_id, principal_id=principal_id)
    return bool(getattr(snapshot, "values", None))


async def execute_and_record(
    runtime: "NexusRuntime",
    thread_id: str,
    user_text: str,
    *,
    principal_id: str,
    store: RunStore,
    pricing_table: pricing_module.PricingTable | None = None,
    agent: str | None = None,
    replay_of: str | None = None,
    preserve_request_id: str | None = None,
) -> RunRecord:
    """Run one turn via `NexusRuntime.execute()`, capture the structured
    events it emitted, build a `RunRecord`, store it, and return it. The
    one place both `api.py`'s synchronous message endpoint and
    `evals/evaluator.py` get "what actually happened" from -- see the
    module docstring.

    `agent` (Phase 6.1, default `None`): passed straight through to
    `NexusRuntime.execute()` -- see its docstring for direct-agent
    execution semantics.
    """
    has_prior_state = await thread_has_prior_state(runtime, thread_id, principal_id=principal_id)
    started_at = _now_iso()

    with observability.capture_events() as captured:
        result = await runtime.execute(thread_id, user_text, principal_id=principal_id, agent=agent)

    completed_at = _now_iso()

    # Post-filter by the now-known request_id -- see observability.capture_events()
    # for why this (not a live filter) is what makes this safe under concurrency.
    events = [event for event in captured if event.get("request_id") == result.request_id]

    record = build_run_record(
        result,
        events,
        started_at=started_at,
        completed_at=completed_at,
        pricing_table=pricing_table,
        original_input=user_text,
        requested_agent=agent,
        replay_context_available=not has_prior_state,
        replay_of=replay_of,
    )
    store.record(record, preserve_request_id=preserve_request_id)
    return record
