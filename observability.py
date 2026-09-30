"""Structured observability for NEXUS runtime executions.

One JSON-shaped log record per lifecycle event (workflow/classifier/router/
agent/tool started-completed-failed), always keyed by `request_id` and
`thread_id` so a single execution's events can be correlated end to end.

Design rules, deliberately simple and enforced at every call site in
`main.py` / `runtime.py`:

- Log metadata (ids, node names, routes, durations, success/failure, error
  *types*), never content (message text, tool arguments/results, prompts).
- Never let a logging failure crash the agent runtime - `log_event` catches
  and reports its own failures instead of propagating them.
- Don't fabricate data (e.g. token usage) that the provider didn't return.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Iterator

logger = logging.getLogger("nexus.observability")
# Set explicitly rather than relying on main.py's logging.basicConfig(INFO)
# having already run: without this, this logger's *effective* level falls
# through to the root logger's default (WARNING), and every log_event()
# call -- an .info() call -- is dropped before any handler (including
# capture_events() below) ever sees it. That was a real, import-order-
# dependent bug: it happened to work in the existing test suite only
# because nearly every test module imports main.py first. This makes the
# module correct on its own.
logger.setLevel(logging.INFO)

# Belt-and-suspenders: even though every call site is expected to pass only
# metadata, strip any field whose *name* suggests it might carry a secret or
# raw content, so a future mistake at a call site can't leak it.
_FORBIDDEN_KEYS = {
    "api_key",
    "anthropic_api_key",
    "authorization",
    "auth",
    "password",
    "secret",
    "token",
    "content",
    "messages",
    "prompt",
    "response_body",
    "headers",
}


def _sanitize(extra: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in extra.items() if key.lower() not in _FORBIDDEN_KEYS}


def log_event(
    event_type: str,
    *,
    request_id: str,
    thread_id: str,
    node: str | None = None,
    duration_ms: float | None = None,
    success: bool | None = None,
    error_type: str | None = None,
    **extra: Any,
) -> None:
    """Emit one structured observability record.

    Never raises: an observability failure must not take down the agent
    runtime, so any error while building/emitting the record is logged as a
    warning (not swallowed silently) and otherwise ignored.
    """
    try:
        record: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "request_id": request_id,
            "thread_id": thread_id,
            "event_type": event_type,
        }
        if node is not None:
            record["node"] = node
        if duration_ms is not None:
            record["duration_ms"] = round(duration_ms, 2)
        if success is not None:
            record["success"] = success
        if error_type is not None:
            record["error_type"] = error_type
        record.update(_sanitize(extra))
        logger.info(json.dumps(record, default=str))
    except Exception as exc:
        # This is the logger's own failure path, so it cannot report through
        # log_event again. Emit only safe structured metadata, never the
        # exception text or traceback.
        logger.warning(json.dumps({
            "event_type": "observability_emit_failed",
            "source_event_type": event_type,
            "error_type": type(exc).__name__,
        }))


def elapsed_ms(start: float) -> float:
    """Milliseconds since `start` (a `time.perf_counter()` reading).

    A plain function rather than a context manager: call sites need the
    duration both on the success path and from inside an `except` block
    (to report `tool_failed`/`*_completed(success=False)` timing), which a
    `with`-block timer that only finalizes on `__exit__` can't give cleanly.
    """
    return (time.perf_counter() - start) * 1000


class _CaptureHandler(logging.Handler):
    """Collects every structured event emitted while attached, in addition
    to (never instead of) whatever normal handlers already do. See
    `capture_events` below for why this doesn't filter by request_id up
    front."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.records: list[dict[str, Any]] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = json.loads(record.getMessage())
        except (TypeError, ValueError):
            return
        if isinstance(payload, dict) and "event_type" in payload:
            self.records.append(payload)


@contextlib.contextmanager
def capture_events() -> Iterator[list[dict[str, Any]]]:
    """Temporarily capture every structured event emitted via `log_event`
    during this `with` block, as an additional listener on top of normal
    logging (nothing is silenced or replaced).

    Used by `run_store.py` (and, through it, the API's run tracking and the
    Phase 4 evaluation framework) to inspect what actually happened during
    one `NexusRuntime.execute()` call using the SAME event stream nodes
    already emit -- not a second event system. The returned list is NOT
    pre-filtered by request_id: a request_id isn't known until `execute()`
    returns, and under concurrent use multiple captures may briefly overlap
    in time. Callers must filter the returned list by their own
    `request_id` afterward -- that post-filter, not exclusivity of the raw
    list, is what makes this safe under concurrent requests (see
    `run_store.execute_and_record`).
    """
    handler = _CaptureHandler()
    logger.addHandler(handler)
    try:
        yield handler.records
    finally:
        logger.removeHandler(handler)


class _StreamingHandler(logging.Handler):
    """Pushes every event matching one specific `request_id` onto an
    `asyncio.Queue` the instant it's emitted -- for the Phase 5 SSE
    endpoint (api.py). Distinct from `_CaptureHandler`/`capture_events()`
    above, which only let a caller read the full list back *after* the
    whole execution finishes: here, a consumer reads the queue
    concurrently with the execution that's producing events, which is
    exactly what "live" streaming needs.

    Filtered by `request_id` at emit time (not after, unlike
    `capture_events()`) because `request_id` IS known up front for this use
    case -- the SSE endpoint generates it itself and passes it into
    `NexusRuntime.execute(..., request_id=...)` specifically so this
    filtering is possible before the first event of the turn is even
    emitted. This is what keeps concurrent SSE streams from crossing wires
    with each other, the same way `capture_events()`'s later post-filter
    keeps concurrent `execute_and_record()` calls safe.
    """

    def __init__(self, request_id: str, queue: "asyncio.Queue[dict[str, Any]]") -> None:
        super().__init__(level=logging.INFO)
        self._request_id = request_id
        self._queue = queue

    def emit(self, record: logging.LogRecord) -> None:
        try:
            payload = json.loads(record.getMessage())
        except (TypeError, ValueError):
            return
        if isinstance(payload, dict) and payload.get("request_id") == self._request_id:
            # put_nowait is safe here: log_event() is always called from
            # code running on the same asyncio event loop that owns this
            # queue (LangGraph nodes execute on that loop, not a separate
            # thread), so this never crosses an event-loop boundary.
            self._queue.put_nowait(payload)


@contextlib.contextmanager
def stream_events(request_id: str) -> Iterator["asyncio.Queue[dict[str, Any]]"]:
    """Like `capture_events()`, but pushes each event for `request_id` onto
    a freshly created `asyncio.Queue` the instant it's emitted, instead of
    only being readable after the `with` block exits.

    Used by the Phase 5 SSE endpoint (api.py) to forward NEXUS's existing
    structured lifecycle events to an HTTP client turn-by-turn, live --
    reusing the exact same `log_event` calls every other observability
    consumer already relies on, not a second event system.
    """
    queue: "asyncio.Queue[dict[str, Any]]" = asyncio.Queue()
    handler = _StreamingHandler(request_id, queue)
    logger.addHandler(handler)
    try:
        yield queue
    finally:
        logger.removeHandler(handler)


def extract_usage(message: Any) -> dict[str, int] | None:
    """Best-effort provider token usage from a LangChain AIMessage.

    Returns None (never a fabricated/zeroed dict) if the provider response
    doesn't carry usage metadata.
    """
    usage = getattr(message, "usage_metadata", None)
    if not usage:
        return None
    cleaned = {k: v for k, v in dict(usage).items() if v is not None}
    return cleaned or None
