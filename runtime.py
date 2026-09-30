"""NEXUS Runtime: execution identity, durable state, and workflow-level
observability for a compiled LangGraph graph.

This module is deliberately agent-agnostic: it knows nothing about the
classifier/router/specialist nodes defined in `main.py`. It only knows how
to take an *uncompiled* `StateGraph` builder, attach a checkpointer to it,
and run turns against named threads. That separation is what lets a future
API layer reuse the exact same execution model as the CLI, and what lets a
Phase 5 PostgreSQL checkpointer replace the SQLite one here without
touching agent logic in `main.py` at all - only `create_runtime` below
changes.

Identity model:
- `thread_id`: a conversation/session. Its LangGraph state (messages,
  classification, routing) persists across executions via the checkpointer.
  Callers choose/reuse thread ids; different threads never share state.
- `request_id`: one per `execute()` call (one user turn). Generated here by
  default, not by the agent nodes - nodes only read it (via
  `config["configurable"]`) to tag their observability events. Phase 5's
  SSE endpoint (api.py) is the one caller that generates it itself and
  passes it in explicitly, so it can attach a live event listener (see
  `observability.stream_events`) *before* execution starts - see the
  `request_id` parameter below.
- `principal_id`: who is making the call. As of Phase 5 this is populated
  from a real authenticated `auth.Principal` at the API boundary (see
  auth.py); the runtime itself still only ever sees the plain string, not
  an HTTP header or a `Principal` object - it does not know or care how a
  caller decided this value. Every `execute()`/`get_state()`/`new_session()`
  call is checked against an `access.AccessStore` (in-memory or
  Postgres-backed - see access.py and `create_runtime` below), so a caller
  (CLI, API, evaluation runner) cannot bypass the check by forgetting to
  call it; it's inside the one code path everything uses.
"""

from __future__ import annotations

import inspect
import os
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import StateGraph
from langgraph.graph.state import CompiledStateGraph

import access
import observability

DEFAULT_CHECKPOINT_DB = "nexus_checkpoints.sqlite"

# Phase 6.4: how many raw checkpoint entries `list_sessions` will scan (via
# the checkpointer's own `alist`) while discovering distinct thread ids.
# One user turn writes several checkpoints (one per graph super-step, not
# one per turn -- see list_sessions' docstring), so this needs to be
# generous relative to NEXUS_RUN_REGISTRY_SIZE. A session created earlier
# than this scan window simply won't appear -- an honest, bounded
# limitation, not a bug (same spirit as RunStore's own bound).
DEFAULT_SESSION_SCAN_LIMIT = int(os.getenv("NEXUS_SESSION_SCAN_LIMIT", "2000"))

DEFAULT_FALLBACK_MESSAGE = (
    "Sorry, I couldn't complete that request due to a runtime error. "
    "Please try again in a moment."
)


def new_thread_id() -> str:
    return f"thread-{uuid.uuid4().hex[:12]}"


def new_request_id() -> str:
    return f"req-{uuid.uuid4().hex[:12]}"


@dataclass
class ExecutionResult:
    request_id: str
    thread_id: str
    reply: str
    duration_ms: float
    success: bool


@dataclass
class SessionSnapshot:
    """One session's latest persisted state, as discovered by
    `NexusRuntime.list_sessions` (Phase 6.4). `values` has the exact same
    shape `get_state()`'s `StateSnapshot.values` does (`messages`,
    `message_type`, `route`) -- both are read from the same checkpointer,
    just via different LangGraph calls (`alist` vs. `aget_state`)."""

    thread_id: str
    values: dict
    updated_at: str


class NexusRuntime:
    """Runs single-turn executions against a checkpointer-backed graph.

    One `NexusRuntime` wraps one already-compiled graph. Construct it via
    `create_runtime()` below, which owns the checkpointer's lifecycle.
    """

    def __init__(
        self,
        graph: CompiledStateGraph,
        fallback_message: str = DEFAULT_FALLBACK_MESSAGE,
        access_store: "access.AccessStore | None" = None,
        direct_agent_graphs: "dict[str, CompiledStateGraph] | None" = None,
    ):
        self._graph = graph
        self._fallback_message = fallback_message
        self._access = access_store or access.ThreadAccessRegistry()
        # Phase 6.1: alternate compiled graphs for "direct agent" execution
        # (bypasses the classifier/router entirely) -- see `execute`'s
        # `agent` parameter and main.py's `DIRECT_AGENT_GRAPH_BUILDERS`.
        # Empty by default so every existing caller (CLI, evals, tests) that
        # never passes `direct_agent_graphs` is completely unaffected.
        self._direct_agent_graphs = direct_agent_graphs or {}

    async def verify_access(self, principal_id: str, thread_id: str) -> None:
        """Raise `access.ThreadAccessDenied` if `principal_id` doesn't own
        `thread_id` (first-touch bookkeeping - see access.py). A thin public
        wrapper so callers outside this module (e.g. the API layer) can
        check ownership without reaching into a private attribute or
        re-implementing the check themselves.

        Always `async` regardless of which backing store is configured: the
        default (`access.ThreadAccessRegistry`) is a synchronous in-memory
        dict check, while the Phase 5 Postgres-backed store
        (`access.PostgresAccessStore`) genuinely awaits a database round
        trip. This method adapts to either transparently (via
        `inspect.isawaitable`) so every caller can simply `await` it without
        needing to know which store is in use.
        """
        result = self._access.require_access(principal_id, thread_id)
        if inspect.isawaitable(result):
            await result

    async def owner_of(self, thread_id: str) -> str | None:
        """Read-only ownership lookup for `thread_id`, or `None` if nobody
        has ever touched it. Unlike `verify_access` (which claims
        first-touch ownership for an unclaimed thread as a side effect),
        this never mutates the access store -- see `access.AccessStore.
        owner_of`. Added for Phase 6.3's run-list endpoint, which needs to
        check "is this run mine?" for many already-recorded runs without
        risking an accidental first-touch claim on any of them.
        """
        result = self._access.owner_of(thread_id)
        if inspect.isawaitable(result):
            return await result
        return result

    async def new_session(self, principal_id: str = access.LOCAL_CLI_PRINCIPAL) -> str:
        """Generate a new thread_id and register `principal_id` as its
        owner, up front. A convenience for callers (e.g. an API's session
        creation endpoint) that want a thread to unambiguously belong to a
        principal from the moment it's created, rather than relying on
        first-touch ownership from a later `execute()`/`get_state()` call.
        """
        thread_id = new_thread_id()
        await self.verify_access(principal_id, thread_id)
        return thread_id

    async def execute(
        self,
        thread_id: str,
        user_text: str,
        principal_id: str = access.LOCAL_CLI_PRINCIPAL,
        request_id: str | None = None,
        agent: str | None = None,
    ) -> ExecutionResult:
        """Run one user turn on `thread_id` and return the assistant reply.

        Only the new user message is passed as input - prior turns are not
        resent. The checkpointer supplies the rest of the persisted thread
        state, and LangGraph's `add_messages` reducer appends this turn to
        it. See `main._latest_user_text` for why nodes still only look at
        the latest turn even though full history is now durably persisted.

        `principal_id` is checked against the thread access store before
        anything else runs - see `access.py`. This is ownership bookkeeping,
        not authentication (see auth.py for the Phase 5 credential check
        that produces a `principal_id` in the first place).

        `request_id` defaults to a freshly generated id, exactly as before.
        Phase 5's SSE endpoint (api.py) is the one caller that passes one in
        explicitly, generated *before* calling `execute()`, so it can attach
        a live event listener (`observability.stream_events`) filtered to
        that exact id before this turn's first event is even emitted.

        `agent` (Phase 6.1, default `None`): when `None`, runs the normal
        classifier -> router -> specialist graph, exactly as before. When
        set to a known agent name (see `main.DIRECT_AGENT_GRAPH_BUILDERS`),
        runs that agent directly instead -- no classifier, no router, no
        `classifier_*`/`route_selected` events. Raises `ValueError` for an
        unrecognized agent name (the API layer validates this first via a
        Pydantic `Literal`, so this is a defensive check, not the primary
        validation).
        """
        request_id = request_id or new_request_id()

        target_graph = self._graph
        if agent is not None:
            try:
                target_graph = self._direct_agent_graphs[agent]
            except KeyError:
                raise ValueError(f"unknown direct agent: {agent!r}") from None

        try:
            await self.verify_access(principal_id, thread_id)
        except access.ThreadAccessDenied:
            observability.log_event(
                "thread_access_denied",
                request_id=request_id,
                thread_id=thread_id,
                reason="THREAD_NOT_OWNED",
            )
            return ExecutionResult(
                request_id=request_id,
                thread_id=thread_id,
                reply=self._fallback_message,
                duration_ms=0.0,
                success=False,
            )

        config = {"configurable": {"thread_id": thread_id, "request_id": request_id}}

        observability.log_event("workflow_started", request_id=request_id, thread_id=thread_id)
        start = time.perf_counter()
        try:
            result_state = await target_graph.ainvoke(
                {"messages": [{"role": "user", "content": user_text}]},
                config=config,
            )
        except Exception as exc:
            duration_ms = observability.elapsed_ms(start)
            observability.log_event(
                "workflow_failed",
                request_id=request_id,
                thread_id=thread_id,
                duration_ms=duration_ms,
                success=False,
                error_type=type(exc).__name__,
            )
            # Mirrors Phase 0's node-level behavior (safe fallback reply,
            # nothing swallowed silently): a workflow-level exception means
            # something failed outside a node's own try/except (e.g. the
            # checkpointer itself), so the runtime is the last line of
            # defense against crashing the caller.
            return ExecutionResult(
                request_id=request_id,
                thread_id=thread_id,
                reply=self._fallback_message,
                duration_ms=duration_ms,
                success=False,
            )

        duration_ms = observability.elapsed_ms(start)
        reply = result_state["messages"][-1].content
        observability.log_event(
            "workflow_completed",
            request_id=request_id,
            thread_id=thread_id,
            duration_ms=duration_ms,
            success=True,
        )
        return ExecutionResult(
            request_id=request_id,
            thread_id=thread_id,
            reply=reply,
            duration_ms=duration_ms,
            success=True,
        )

    async def get_state(
        self, thread_id: str, principal_id: str = access.LOCAL_CLI_PRINCIPAL
    ) -> Any:
        """Return the persisted LangGraph state snapshot for a thread (or
        an empty snapshot if the thread has never been executed).

        Also checked against the access store - reading another principal's
        thread state is exactly the kind of accidental exposure this
        boundary exists to make structurally hard, not just execution.
        """
        await self.verify_access(principal_id, thread_id)
        config = {"configurable": {"thread_id": thread_id}}
        return await self._graph.aget_state(config)

    async def list_sessions(
        self, principal_id: str, *, limit: int = 50, scan_limit: int = DEFAULT_SESSION_SCAN_LIMIT
    ) -> list[SessionSnapshot]:
        """This principal's sessions (threads with at least one persisted
        checkpoint), most-recently-updated first, up to `limit`.

        Built entirely from the checkpointer's own native `alist(None)` --
        no second persistence layer, no session database, and (Phase 6.4's
        explicit requirement) no duplication of LangGraph persistence.
        `alist(None)` yields checkpoint entries across ALL threads, newest
        first; the first entry seen for a given `thread_id` is therefore
        that thread's latest state, exactly the state `get_state()` would
        return for it (`checkpoint["channel_values"]` and
        `checkpoint["ts"]` are the same underlying data `StateSnapshot.
        values`/`.created_at` are built from) -- so this method reads the
        raw checkpoint directly instead of making a second `aget_state()`
        round trip per candidate thread.

        Ownership is checked via the same read-only `owner_of()` used by
        the Phase 6.3 run-list endpoint, for the same reason: this method
        must never have `verify_access`'s first-touch claiming side effect
        merely from enumerating threads it happens to scan past.

        `scan_limit` bounds how many raw checkpoint entries are examined
        while discovering distinct thread ids -- see
        `DEFAULT_SESSION_SCAN_LIMIT`'s docstring for why this is necessary
        and what it honestly means for very old sessions.
        """
        checkpointer = self._graph.checkpointer
        seen: set[str] = set()
        results: list[SessionSnapshot] = []
        async for checkpoint_tuple in checkpointer.alist(None, limit=scan_limit):
            thread_id = checkpoint_tuple.config["configurable"]["thread_id"]
            if thread_id in seen:
                continue
            seen.add(thread_id)

            channel_values = checkpoint_tuple.checkpoint.get("channel_values") or {}
            if not channel_values.get("messages"):
                continue  # a checkpoint that predates any real turn (rare, defensive)

            owner = self._access.owner_of(thread_id)
            if inspect.isawaitable(owner):
                owner = await owner
            if owner != principal_id:
                continue

            results.append(
                SessionSnapshot(
                    thread_id=thread_id,
                    values=channel_values,
                    updated_at=checkpoint_tuple.checkpoint.get("ts", ""),
                )
            )
            if len(results) >= limit:
                break
        return results


@asynccontextmanager
async def create_runtime(
    graph_builder: StateGraph,
    checkpoint_db: str | None = None,
    fallback_message: str = DEFAULT_FALLBACK_MESSAGE,
    database_url: str | None = None,
    direct_agent_builders: "dict[str, StateGraph] | None" = None,
) -> AsyncIterator[NexusRuntime]:
    """Open a checkpointer-backed NexusRuntime as an async context manager.

    Two backends, chosen by whether a Postgres URL is available:

    - `database_url` (or, if not passed, the `NEXUS_DATABASE_URL` env var)
      set: durable, cross-process-safe Postgres checkpointing
      (`AsyncPostgresSaver`) plus a durable, cross-process-safe thread
      ownership store (`access.PostgresAccessStore`). The checkpointer and
      ownership store each use their own connection pool, opened and closed
      within this runtime context. This is the "production-like" backend -
      see ARCHITECTURE.md.
    - Otherwise: the original SQLite checkpointer (`AsyncSqliteSaver`) plus
      the original in-memory, process-local `access.ThreadAccessRegistry` -
      unchanged local-development default since Phase 1/2.

    `checkpoint_db` defaults to the `NEXUS_CHECKPOINT_DB` env var, then
    `DEFAULT_CHECKPOINT_DB`, and is only used for the SQLite path.

    `direct_agent_builders` (Phase 6.1, optional): uncompiled per-agent
    graph builders (see `main.DIRECT_AGENT_GRAPH_BUILDERS`), compiled here
    against the SAME checkpointer as `graph_builder` so a thread's state is
    identical and shared no matter which graph a given turn runs against --
    see `NexusRuntime.execute`'s `agent` parameter. Omitted entirely
    (`None`, the default) by every caller that doesn't need direct-agent
    execution (CLI, evals, most tests), in which case `NexusRuntime` simply
    has no direct-agent graphs available and `execute(..., agent=...)`
    raises `ValueError` if ever called with a non-`None` agent.
    """
    resolved_database_url = database_url or os.getenv("NEXUS_DATABASE_URL") or None

    if resolved_database_url:
        # Lazy import: langgraph.checkpoint.postgres / psycopg_pool are an
        # optional dependency (pyproject.toml's `postgres` extra) -- this
        # module must stay importable without them for the SQLite/default
        # path, which is the common case for local development and for the
        # existing test suite.
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
        from psycopg_pool import AsyncConnectionPool

        access_pool = AsyncConnectionPool(resolved_database_url, open=False)
        await access_pool.open()
        try:
            access_store = access.PostgresAccessStore(access_pool)
            await access_store.setup()
            async with AsyncPostgresSaver.from_conn_string(resolved_database_url) as checkpointer:
                await checkpointer.setup()
                compiled = graph_builder.compile(checkpointer=checkpointer)
                direct_compiled = {
                    name: builder.compile(checkpointer=checkpointer)
                    for name, builder in (direct_agent_builders or {}).items()
                }
                yield NexusRuntime(
                    compiled,
                    fallback_message=fallback_message,
                    access_store=access_store,
                    direct_agent_graphs=direct_compiled,
                )
        finally:
            await access_pool.close()
        return

    db_path = checkpoint_db or os.getenv("NEXUS_CHECKPOINT_DB", DEFAULT_CHECKPOINT_DB)
    async with AsyncSqliteSaver.from_conn_string(db_path) as checkpointer:
        await checkpointer.setup()
        compiled = graph_builder.compile(checkpointer=checkpointer)
        direct_compiled = {
            name: builder.compile(checkpointer=checkpointer)
            for name, builder in (direct_agent_builders or {}).items()
        }
        yield NexusRuntime(
            compiled,
            fallback_message=fallback_message,
            access_store=access.ThreadAccessRegistry(),
            direct_agent_graphs=direct_compiled,
        )
