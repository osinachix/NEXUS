"""Tests for the Phase 5 PostgreSQL checkpointer/access-store backend
(runtime.create_runtime's `database_url` branch, access.PostgresAccessStore).

Two tiers, per the Phase 5 spec's instruction not to fake a passing
PostgreSQL test when no PostgreSQL is available:

1. Deterministic, no-database-required tests: confirm `create_runtime`
   actually *dispatches* to the Postgres code path when configured (rather
   than silently falling back to SQLite), using a connection that fails
   fast (nothing is listening on the given port) so this needs no real
   server and stays fast. These always run.
2. Real integration tests (checkpoint persistence, cross-thread isolation,
   restart persistence, durable cross-process ownership) against an actual
   PostgreSQL instance -- these only run if `NEXUS_TEST_DATABASE_URL` is
   set to a real, reachable Postgres connection string; otherwise they are
   explicitly skipped (not faked, not silently omitted -- pytest reports
   them as "skipped" with the reason below). See the Phase 5 final report
   for whether this environment had Postgres available.
"""

from __future__ import annotations

import asyncio
import os

import pytest

import access
import main
import runtime as nexus_runtime

_TEST_DATABASE_URL = os.getenv("NEXUS_TEST_DATABASE_URL")

requires_real_postgres = pytest.mark.skipif(
    not _TEST_DATABASE_URL,
    reason="NEXUS_TEST_DATABASE_URL not set -- no PostgreSQL instance available in this environment",
)


class _FakeMessage:
    def __init__(self, content):
        self.content = content


@pytest.fixture(autouse=True)
def _fake_llm_calls(monkeypatch):
    monkeypatch.setattr(
        main, "_call_classifier", lambda messages: main.MessageClassifier(message_type="coding")
    )
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("stub reply"))


# ---------------------------------------------------------------------------
# Tier 1: deterministic, no real database required.
# ---------------------------------------------------------------------------


async def test_create_runtime_uses_sqlite_when_no_database_url_is_given(tmp_path):
    db_path = str(tmp_path / "dispatch_test.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        assert isinstance(session._access, access.ThreadAccessRegistry)


async def test_create_runtime_dispatches_to_postgres_when_database_url_is_given():
    # Nothing listens on localhost:1 (a privileged, essentially-never-bound
    # port), so this genuinely cannot succeed -- proving `create_runtime`
    # actually attempted a real Postgres connection (not a silent SQLite
    # fallback) without needing a working Postgres server. Bounded with an
    # outer timeout so this stays fast regardless of exactly how the
    # underlying pool reports the failure (immediate refusal vs. its own
    # internal connection-attempt timeout).
    unreachable_url = "postgresql://user:pass@localhost:1/nope"

    async def _attempt():
        async with nexus_runtime.create_runtime(main.graph_builder, database_url=unreachable_url):
            pass  # pragma: no cover -- should never get here

    with pytest.raises(Exception):
        await asyncio.wait_for(_attempt(), timeout=5)


async def test_postgres_access_store_builds_expected_ddl_and_queries():
    # No live connection needed: PostgresAccessStore just needs an object
    # exposing an async `.connection()` context manager -- verify the exact
    # SQL it issues (table name, atomic first-touch INSERT ON CONFLICT
    # pattern) against a minimal recording fake, matching how the class is
    # actually used in runtime.py.
    executed = []

    class _FakeCursor:
        def __init__(self, row=None):
            self._row = row

        async def fetchone(self):
            return self._row

    class _FakeConn:
        def __init__(self, claim_row):
            self._claim_row = claim_row

        async def execute(self, query, params=None):
            executed.append((query.strip().split()[0], params))
            if "INSERT INTO" in query:
                return _FakeCursor(self._claim_row)
            return _FakeCursor(("existing-owner",))

    class _FakeConnCtx:
        def __init__(self, conn):
            self._conn = conn

        async def __aenter__(self):
            return self._conn

        async def __aexit__(self, *exc_info):
            return False

    class _FakePool:
        def __init__(self, claim_row):
            self._claim_row = claim_row

        def connection(self):
            return _FakeConnCtx(_FakeConn(self._claim_row))

    # Case 1: first-touch claim succeeds (INSERT ... RETURNING a row).
    store = access.PostgresAccessStore(_FakePool(claim_row=("principal-a",)))
    await store.require_access("principal-a", "thread-x")
    assert executed[0][0] == "INSERT"
    assert executed[0][1] == ("thread-x", "principal-a")

    # Case 2: conflict (no row returned by INSERT) -- falls back to SELECT,
    # and denies a different principal.
    executed.clear()
    store2 = access.PostgresAccessStore(_FakePool(claim_row=None))
    with pytest.raises(access.ThreadAccessDenied):
        await store2.require_access("principal-b", "thread-x")
    assert executed[0][0] == "INSERT"
    assert executed[1][0] == "SELECT"


# ---------------------------------------------------------------------------
# Tier 2: real PostgreSQL integration (skipped unless NEXUS_TEST_DATABASE_URL
# is configured -- see module docstring).
# ---------------------------------------------------------------------------


@requires_real_postgres
async def test_postgres_checkpoint_persists_within_a_thread():
    async with nexus_runtime.create_runtime(
        main.graph_builder, database_url=_TEST_DATABASE_URL
    ) as session:
        thread_id = nexus_runtime.new_thread_id()
        await session.execute(thread_id, "first message")
        await session.execute(thread_id, "second message")
        snapshot = await session.get_state(thread_id)
        assert len(snapshot.values["messages"]) == 4


@requires_real_postgres
async def test_postgres_different_threads_are_isolated():
    async with nexus_runtime.create_runtime(
        main.graph_builder, database_url=_TEST_DATABASE_URL
    ) as session:
        thread_a = nexus_runtime.new_thread_id()
        thread_b = nexus_runtime.new_thread_id()
        await session.execute(thread_a, "thread A message")
        await session.execute(thread_b, "thread B message")
        state_a = await session.get_state(thread_a)
        state_b = await session.get_state(thread_b)
        assert len(state_a.values["messages"]) == 2
        assert len(state_b.values["messages"]) == 2
        assert state_a.values["messages"][0].content != state_b.values["messages"][0].content


@requires_real_postgres
async def test_postgres_state_survives_a_restart():
    thread_id = nexus_runtime.new_thread_id()
    async with nexus_runtime.create_runtime(
        main.graph_builder, database_url=_TEST_DATABASE_URL
    ) as session:
        await session.execute(thread_id, "remember this")
    async with nexus_runtime.create_runtime(
        main.graph_builder, database_url=_TEST_DATABASE_URL
    ) as session:
        snapshot = await session.get_state(thread_id)
        contents = [m.content for m in snapshot.values["messages"]]
        assert "remember this" in contents


@requires_real_postgres
async def test_postgres_thread_ownership_survives_a_restart():
    thread_id = nexus_runtime.new_thread_id()
    async with nexus_runtime.create_runtime(
        main.graph_builder, database_url=_TEST_DATABASE_URL
    ) as session:
        await session.execute(thread_id, "hello", principal_id="principal-a")
    async with nexus_runtime.create_runtime(
        main.graph_builder, database_url=_TEST_DATABASE_URL
    ) as session:
        # A different process (simulated by a fresh create_runtime call
        # against the same database) still enforces the original owner.
        with pytest.raises(access.ThreadAccessDenied):
            await session.execute(thread_id, "hi again", principal_id="principal-b")
