"""Thread-based durable state: same-thread persistence, cross-thread
isolation, and state surviving a full close/reopen of the checkpointer
(simulating a process restart) against the same SQLite file.

The classifier/LLM are mocked so these tests never touch the network or
need a real API key; what's under test here is the checkpointer/thread
wiring in runtime.py, not model behavior (already covered in Phase 0).
"""

import pytest

import main
import runtime as nexus_runtime


class _FakeMessage:
    def __init__(self, content):
        self.content = content


@pytest.fixture(autouse=True)
def _fake_llm_calls(monkeypatch):
    # "coding" routes to coding_agent, a plain _call_llm node -- avoids the
    # logical agent's dependency on a real (or MCP-backed) tool-calling
    # agent, which isn't built outside of run_chatbot().
    monkeypatch.setattr(
        main, "_call_classifier", lambda messages: main.MessageClassifier(message_type="coding")
    )
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("stub reply"))


async def test_same_thread_preserves_state_across_turns(tmp_path):
    db_path = str(tmp_path / "threads.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        thread_id = nexus_runtime.new_thread_id()

        await session.execute(thread_id, "first message")
        await session.execute(thread_id, "second message")

        snapshot = await session.get_state(thread_id)
        messages = snapshot.values["messages"]

        # 2 user turns + 2 assistant replies, in order, all on one thread.
        assert len(messages) == 4
        assert messages[0].content == "first message"
        assert messages[2].content == "second message"


async def test_different_threads_are_isolated(tmp_path):
    db_path = str(tmp_path / "threads.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        thread_a = nexus_runtime.new_thread_id()
        thread_b = nexus_runtime.new_thread_id()

        await session.execute(thread_a, "thread A message 1")
        await session.execute(thread_a, "thread A message 2")
        await session.execute(thread_b, "thread B message 1")

        state_a = await session.get_state(thread_a)
        state_b = await session.get_state(thread_b)

        assert len(state_a.values["messages"]) == 4  # 2 turns x (user + assistant)
        assert len(state_b.values["messages"]) == 2  # 1 turn x (user + assistant)

        b_contents = [m.content for m in state_b.values["messages"]]
        assert "thread A message 1" not in b_contents
        assert "thread A message 2" not in b_contents


async def test_restarting_with_same_thread_loads_persisted_state(tmp_path):
    db_path = str(tmp_path / "threads.sqlite")
    thread_id = nexus_runtime.new_thread_id()

    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        await session.execute(thread_id, "remember this")
    # The checkpointer's connection is fully closed here (context manager
    # exit), then reopened against the same file -- this is what a real
    # process restart looks like from the checkpointer's point of view.
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        snapshot = await session.get_state(thread_id)
        contents = [m.content for m in snapshot.values["messages"]]
        assert "remember this" in contents

        # A new turn on the resumed thread appends, it doesn't replace.
        await session.execute(thread_id, "second turn after restart")
        snapshot_after = await session.get_state(thread_id)
        assert len(snapshot_after.values["messages"]) == 4


async def test_unknown_thread_has_no_persisted_state(tmp_path):
    db_path = str(tmp_path / "threads.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        snapshot = await session.get_state(nexus_runtime.new_thread_id())
        assert not snapshot.values


# --- list_sessions (Phase 6.4) -----------------------------------------------------------


async def test_list_sessions_returns_most_recently_updated_first(tmp_path):
    db_path = str(tmp_path / "threads.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        thread_a = nexus_runtime.new_thread_id()
        thread_b = nexus_runtime.new_thread_id()
        await session.execute(thread_a, "first", principal_id="p1")
        await session.execute(thread_b, "second", principal_id="p1")

        sessions = await session.list_sessions("p1")
        assert [s.thread_id for s in sessions] == [thread_b, thread_a]


async def test_list_sessions_only_returns_the_calling_principals_sessions(tmp_path):
    db_path = str(tmp_path / "threads.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        thread_a = nexus_runtime.new_thread_id()
        thread_b = nexus_runtime.new_thread_id()
        await session.execute(thread_a, "mine", principal_id="p1")
        await session.execute(thread_b, "not mine", principal_id="p2")

        sessions_p1 = await session.list_sessions("p1")
        assert [s.thread_id for s in sessions_p1] == [thread_a]

        sessions_p2 = await session.list_sessions("p2")
        assert [s.thread_id for s in sessions_p2] == [thread_b]


async def test_list_sessions_values_match_get_state(tmp_path):
    db_path = str(tmp_path / "threads.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        thread_id = nexus_runtime.new_thread_id()
        await session.execute(thread_id, "hello", principal_id="p1")

        [snapshot] = await session.list_sessions("p1")
        state = await session.get_state(thread_id, principal_id="p1")

        assert snapshot.updated_at == state.created_at
        assert len(snapshot.values["messages"]) == len(state.values["messages"])
        assert snapshot.values["messages"][0].content == state.values["messages"][0].content


async def test_list_sessions_respects_limit(tmp_path):
    db_path = str(tmp_path / "threads.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        for i in range(3):
            await session.execute(nexus_runtime.new_thread_id(), f"turn {i}", principal_id="p1")

        sessions = await session.list_sessions("p1", limit=2)
        assert len(sessions) == 2


async def test_list_sessions_on_empty_checkpointer_returns_empty_list(tmp_path):
    db_path = str(tmp_path / "threads.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        assert await session.list_sessions("p1") == []


async def test_list_sessions_never_claims_ownership_of_a_thread_it_scans_past(tmp_path):
    # list_sessions must use the read-only owner_of, never verify_access/
    # require_access -- scanning past another principal's thread must not
    # silently grant the caller ownership of it.
    db_path = str(tmp_path / "threads.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        other_thread = nexus_runtime.new_thread_id()
        await session.execute(other_thread, "belongs to p2", principal_id="p2")

        await session.list_sessions("p1")

        assert await session.owner_of(other_thread) == "p2"
