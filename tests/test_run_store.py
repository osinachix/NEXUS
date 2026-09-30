"""run_store.py: event capture, RunRecord construction, and the bounded
RunStore. Uses the real graph/runtime with the LLM mocked (same pattern as
tests/test_runtime_threads.py) so these tests prove the real integration,
not a hand-rolled fake.
"""

import pytest

import access
import main
import observability
import pricing
import run_store
import runtime as nexus_runtime


class _FakeMessage:
    def __init__(self, content, usage=None):
        self.content = content
        self.usage_metadata = usage


@pytest.fixture(autouse=True)
def _fake_llm_calls(monkeypatch):
    monkeypatch.setattr(
        main, "_call_classifier", lambda messages: main.MessageClassifier(message_type="coding")
    )
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("stub reply"))


# --- observability.capture_events -----------------------------------------------------------


def test_capture_events_collects_events_emitted_inside_the_block():
    with observability.capture_events() as captured:
        observability.log_event("workflow_started", request_id="r1", thread_id="t1")
        observability.log_event("workflow_completed", request_id="r1", thread_id="t1", success=True)
    assert len(captured) == 2
    assert captured[0]["event_type"] == "workflow_started"


def test_capture_events_does_not_capture_outside_the_block():
    with observability.capture_events() as captured:
        observability.log_event("workflow_started", request_id="r1", thread_id="t1")
    observability.log_event("workflow_started", request_id="r2", thread_id="t2")
    assert len(captured) == 1  # the second event, emitted after the block closed, isn't in it


def test_capture_events_does_not_silence_normal_logging(caplog):
    caplog.set_level("INFO", logger="nexus.observability")
    with observability.capture_events():
        observability.log_event("workflow_started", request_id="r1", thread_id="t1")
    assert "workflow_started" in caplog.text  # normal handlers still saw it


# --- execute_and_record -----------------------------------------------------------


async def test_execute_and_record_builds_a_complete_run_record(tmp_path):
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        store = run_store.RunStore()
        record = await run_store.execute_and_record(
            rt, nexus_runtime.new_thread_id(), "write a function",
            principal_id=access.LOCAL_EVAL_PRINCIPAL, store=store,
        )

    assert record.status == "completed"
    assert record.success is True
    assert record.route == "coding"
    assert record.agent == "coding"
    assert record.message_type == "coding"
    assert record.reply == "stub reply"
    assert record.original_input == "write a function"
    assert record.replayable is True
    assert record.requested_agent is None
    assert "original_input" not in record.model_dump()
    assert record.duration_ms >= 0
    assert record.started_at and record.completed_at
    event_types = [e.event_type for e in record.events]
    assert "workflow_started" in event_types
    assert "workflow_completed" in event_types
    assert "route_selected" in event_types

    route_event = next(e for e in record.events if e.event_type == "route_selected")
    assert route_event.route == "coding"
    other_event = next(e for e in record.events if e.event_type == "workflow_started")
    assert other_event.route is None


async def test_execute_and_record_populates_agent_for_direct_agent_runs_with_no_route(tmp_path):
    # A direct-agent run never emits route_selected, so `route` stays None
    # -- but `agent` (Phase 6.3) must still identify which specialist ran,
    # from the agent_started event's node, not from `route`.
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(
        main.graph_builder, checkpoint_db=db_path, direct_agent_builders=main.DIRECT_AGENT_GRAPH_BUILDERS
    ) as rt:
        store = run_store.RunStore()
        record = await run_store.execute_and_record(
            rt, nexus_runtime.new_thread_id(), "hi",
            principal_id=access.LOCAL_EVAL_PRINCIPAL, store=store, agent="math",
        )

    assert record.route is None
    assert record.agent == "math"
    assert record.requested_agent == "math"


async def test_execute_and_record_aggregates_usage_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(
        main,
        "_call_llm",
        lambda messages: _FakeMessage(
            "stub reply", usage={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30}
        ),
    )
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        store = run_store.RunStore()
        record = await run_store.execute_and_record(
            rt, nexus_runtime.new_thread_id(), "write a function",
            principal_id=access.LOCAL_EVAL_PRINCIPAL, store=store,
        )

    assert record.usage is not None
    assert record.usage.input_tokens == 10
    assert record.usage.output_tokens == 20


async def test_execute_and_record_usage_is_none_when_provider_did_not_return_it(tmp_path):
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        store = run_store.RunStore()
        record = await run_store.execute_and_record(
            rt, nexus_runtime.new_thread_id(), "write a function",
            principal_id=access.LOCAL_EVAL_PRINCIPAL, store=store,
        )
    assert record.usage is None
    assert record.cost_usd is None


async def test_execute_and_record_computes_cost_when_pricing_and_usage_available(tmp_path, monkeypatch):
    monkeypatch.setattr(
        main,
        "_call_llm",
        lambda messages: _FakeMessage(
            "stub reply", usage={"input_tokens": 1_000_000, "output_tokens": 1_000_000, "total_tokens": 2_000_000}
        ),
    )
    table = {main.MODEL_NAME: pricing.ModelPricing(input_cost_per_1m_tokens=3.0, output_cost_per_1m_tokens=15.0)}
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        store = run_store.RunStore()
        record = await run_store.execute_and_record(
            rt, nexus_runtime.new_thread_id(), "write a function",
            principal_id=access.LOCAL_EVAL_PRINCIPAL, store=store, pricing_table=table,
        )

    assert record.cost_usd == 18.0


async def test_run_stored_and_retrieved(tmp_path):
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        store = run_store.RunStore()
        record = await run_store.execute_and_record(
            rt, nexus_runtime.new_thread_id(), "hello",
            principal_id=access.LOCAL_EVAL_PRINCIPAL, store=store,
        )
        fetched = store.get(record.request_id)
        assert fetched is not None
        assert fetched.request_id == record.request_id


async def test_only_first_turn_records_are_marked_replayable(tmp_path):
    db_path = str(tmp_path / "t.sqlite")
    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as rt:
        store = run_store.RunStore()
        thread_id = nexus_runtime.new_thread_id()
        first = await run_store.execute_and_record(
            rt, thread_id, "first turn", principal_id=access.LOCAL_EVAL_PRINCIPAL, store=store
        )
        second = await run_store.execute_and_record(
            rt, thread_id, "second turn", principal_id=access.LOCAL_EVAL_PRINCIPAL, store=store
        )

    assert first.replayable is True
    assert first.replay_unavailable_reason is None
    assert second.replayable is False
    assert second.replay_unavailable_reason == "thread_has_prior_state"


def test_run_store_missing_run_returns_none():
    store = run_store.RunStore()
    assert store.get("req-does-not-exist") is None


def test_run_store_is_bounded():
    store = run_store.RunStore(max_size=3)

    def make(i):
        return run_store.RunRecord(
            request_id=f"req-{i}", thread_id="t", status="completed", success=True,
            route=None, message_type=None, reply="x", started_at="t0", completed_at="t1",
            duration_ms=1.0,
        )

    for i in range(5):
        store.record(make(i))

    assert store.get("req-0") is None  # evicted (oldest)
    assert store.get("req-1") is None  # evicted (oldest)
    assert store.get("req-4") is not None  # newest still present


def test_run_store_can_preserve_replay_source_while_evicting_an_older_run():
    store = run_store.RunStore(max_size=2)
    store.record(_make_record("req-old"))
    store.record(_make_record("req-source"))

    assert store.can_record_preserving("req-source") is True
    store.record(_make_record("req-replay", replay_of="req-source"), preserve_request_id="req-source")

    assert store.get("req-source") is not None
    assert store.get("req-replay") is not None
    assert store.get("req-old") is None


def test_run_store_refuses_replay_when_source_cannot_be_retained_within_bound():
    store = run_store.RunStore(max_size=1)
    store.record(_make_record("req-source"))

    assert store.can_record_preserving("req-source") is False
    with pytest.raises(ValueError, match="protected source"):
        store.record(_make_record("req-replay"), preserve_request_id="req-source")
    assert [run.request_id for run in store.list_recent()] == ["req-source"]


def _make_record(request_id: str, **overrides) -> run_store.RunRecord:
    defaults = dict(
        request_id=request_id, thread_id="t", status="completed", success=True,
        route=None, agent=None, message_type=None, reply="x", started_at="t0", completed_at="t1",
        duration_ms=1.0,
    )
    defaults.update(overrides)
    return run_store.RunRecord(**defaults)


def test_list_recent_returns_most_recently_recorded_first():
    store = run_store.RunStore()
    for i in range(3):
        store.record(_make_record(f"req-{i}"))

    ids = [r.request_id for r in store.list_recent()]
    assert ids == ["req-2", "req-1", "req-0"]


def test_list_recent_moves_a_re_recorded_run_to_the_front():
    store = run_store.RunStore()
    store.record(_make_record("req-a"))
    store.record(_make_record("req-b"))
    store.record(_make_record("req-a"))  # re-recording moves it to the front

    ids = [r.request_id for r in store.list_recent()]
    assert ids == ["req-a", "req-b"]


def test_list_recent_on_empty_store_returns_empty_list():
    store = run_store.RunStore()
    assert store.list_recent() == []


def test_compare_runs_returns_b_minus_a_deltas_and_null_for_missing_metrics():
    run_a = _make_record(
        "req-a",
        duration_ms=12.5,
        usage=run_store.TokenUsage(input_tokens=10, output_tokens=4, total_tokens=14),
        cost_usd=0.02,
        tool_events=[run_store.ToolEvent(tool="fetch", event_type="tool_completed", timestamp="t")],
    )
    run_b = _make_record("req-b", duration_ms=15.0, usage=None, cost_usd=None, tool_events=[])

    before_a = run_a.model_dump()
    before_b = run_b.model_dump()
    delta = run_store.compare_runs(run_a, run_b)

    assert delta.duration_ms == 2.5
    assert delta.input_tokens is None
    assert delta.output_tokens is None
    assert delta.total_tokens is None
    assert delta.cost_usd is None
    assert delta.tool_event_count == -1
    assert run_a.model_dump() == before_a
    assert run_b.model_dump() == before_b


def test_list_recent_respects_the_bound():
    store = run_store.RunStore(max_size=2)
    for i in range(4):
        store.record(_make_record(f"req-{i}"))
    assert [r.request_id for r in store.list_recent()] == ["req-3", "req-2"]
