"""Direct-agent execution (Phase 6.1): NexusRuntime.execute(..., agent=...)
bypasses the classifier/router entirely and runs one specific agent graph
directly -- the backend capability the NEXUS Console's Playground "Direct
Agent" mode depends on. See main.py's DIRECT_AGENT_GRAPH_BUILDERS module
docstring for why this uses separate compiled graphs instead of a state
field (checkpoint staleness across turns).
"""

import pytest

import main
import runtime as nexus_runtime
from observability import capture_events


class _FakeMessage:
    def __init__(self, content):
        self.content = content


@pytest.fixture(autouse=True)
def _fake_llm_calls(monkeypatch):
    monkeypatch.setattr(
        main, "_call_classifier", lambda messages: main.MessageClassifier(message_type="coding")
    )
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("stub reply"))


def _runtime(tmp_path, db_name="direct_agent.sqlite"):
    db_path = str(tmp_path / db_name)
    return nexus_runtime.create_runtime(
        main.graph_builder,
        checkpoint_db=db_path,
        direct_agent_builders=main.DIRECT_AGENT_GRAPH_BUILDERS,
    )


async def test_direct_agent_runs_the_requested_agent(tmp_path):
    async with _runtime(tmp_path) as session:
        result = await session.execute(
            nexus_runtime.new_thread_id(), "explain big-o notation", agent="coding"
        )
        assert result.success is True
        assert result.reply == "stub reply"


async def test_direct_agent_emits_no_classifier_or_route_events(tmp_path):
    async with _runtime(tmp_path) as session:
        thread_id = nexus_runtime.new_thread_id()
        with capture_events() as events:
            result = await session.execute(thread_id, "explain big-o notation", agent="coding")

        own_events = [e for e in events if e.get("request_id") == result.request_id]
        event_types = {e["event_type"] for e in own_events}

        assert "classifier_started" not in event_types
        assert "classifier_completed" not in event_types
        assert "route_selected" not in event_types
        assert "workflow_started" in event_types
        assert "agent_started" in event_types
        assert "agent_completed" in event_types
        assert "workflow_completed" in event_types


async def test_auto_route_still_emits_classifier_and_route_events(tmp_path):
    # Regression guard: direct-agent graphs must not affect the default
    # (agent=None) path at all.
    async with _runtime(tmp_path) as session:
        thread_id = nexus_runtime.new_thread_id()
        with capture_events() as events:
            result = await session.execute(thread_id, "write a function")

        own_events = [e for e in events if e.get("request_id") == result.request_id]
        event_types = {e["event_type"] for e in own_events}
        assert "classifier_started" in event_types
        assert "route_selected" in event_types


@pytest.mark.parametrize("agent_name", ["counselor", "logical", "math", "coding"])
async def test_each_known_direct_agent_executes_successfully(tmp_path, agent_name, monkeypatch):
    # "logical" normally drives the real ReAct tool-calling agent; stub it
    # out exactly like the rest of the suite does so this stays offline.
    async def fake_logical_agent(user_text, config=None):
        return {"messages": [_FakeMessage("stub reply")]}

    monkeypatch.setattr(main, "_call_logical_agent", fake_logical_agent)
    monkeypatch.setattr(main, "logical_react_agent", object())

    async with _runtime(tmp_path, f"direct_{agent_name}.sqlite") as session:
        result = await session.execute(
            nexus_runtime.new_thread_id(), "hello", agent=agent_name
        )
        assert result.success is True


async def test_unknown_direct_agent_raises_value_error(tmp_path):
    async with _runtime(tmp_path) as session:
        with pytest.raises(ValueError):
            await session.execute(nexus_runtime.new_thread_id(), "hello", agent="not-a-real-agent")


async def test_direct_agent_without_configured_graphs_raises(tmp_path):
    # A runtime built the plain way (no direct_agent_builders, e.g. the CLI)
    # must fail clearly rather than silently falling back to auto-routing.
    db_path = str(tmp_path / "no_direct_graphs.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        with pytest.raises(ValueError):
            await session.execute(nexus_runtime.new_thread_id(), "hello", agent="math")


async def test_direct_and_auto_modes_share_checkpoint_state_on_the_same_thread(tmp_path):
    # The core safety property motivating separate compiled graphs (see
    # module docstring): interleaving direct-agent and auto-route turns on
    # ONE thread_id must accumulate shared message history correctly, and
    # a later auto-route turn must still classify normally -- proving no
    # state field is used as a "skip classification" signal that could
    # leak across turns.
    async with _runtime(tmp_path) as session:
        thread_id = nexus_runtime.new_thread_id()

        first = await session.execute(thread_id, "direct turn", agent="coding")
        assert first.success is True

        second = await session.execute(thread_id, "auto turn")
        assert second.success is True

        snapshot = await session.get_state(thread_id)
        messages = snapshot.values["messages"]
        # 2 user turns + 2 assistant replies, all on the one shared thread.
        assert len(messages) == 4
        assert messages[0].content == "direct turn"
        assert messages[2].content == "auto turn"


async def test_direct_agent_run_record_has_no_route_but_records_agent_activity(tmp_path):
    import run_store

    async with _runtime(tmp_path) as session:
        store = run_store.RunStore()
        record = await run_store.execute_and_record(
            session,
            nexus_runtime.new_thread_id(),
            "hello",
            principal_id="test-principal",
            store=store,
            agent="math",
        )
        assert record.route is None  # no route_selected event was ever emitted
        assert record.status == "completed"
        event_types = {e.event_type for e in record.events}
        assert "agent_started" in event_types
        assert "classifier_started" not in event_types
