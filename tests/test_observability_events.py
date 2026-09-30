"""Structured lifecycle events: the required event types are emitted, they
share one request_id/thread_id per execution, and failures at the node
level still produce a *_completed event with success=False rather than
silently vanishing or crashing the workflow.
"""

import json

import pytest

import main
import runtime as nexus_runtime


class _FakeMessage:
    def __init__(self, content):
        self.content = content


def _events_from(caplog):
    events = []
    for record in caplog.records:
        if record.name != "nexus.observability":
            continue
        try:
            events.append(json.loads(record.getMessage()))
        except (TypeError, ValueError):
            continue
    return events


def _boom(*args, **kwargs):
    raise RuntimeError("provider unavailable")


@pytest.fixture(autouse=True)
def _fake_llm_calls(monkeypatch):
    monkeypatch.setattr(
        main, "_call_classifier", lambda messages: main.MessageClassifier(message_type="coding")
    )
    monkeypatch.setattr(main, "_call_llm", lambda messages: _FakeMessage("stub reply"))


async def test_successful_execution_emits_the_full_required_lifecycle(tmp_path, caplog):
    caplog.set_level("INFO", logger="nexus.observability")
    db_path = str(tmp_path / "obs.sqlite")

    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        result = await session.execute(nexus_runtime.new_thread_id(), "write a function")

    events = _events_from(caplog)
    event_types = [e["event_type"] for e in events]

    for expected in (
        "workflow_started",
        "classifier_started",
        "classifier_completed",
        "route_selected",
        "agent_started",
        "agent_completed",
        "workflow_completed",
    ):
        assert expected in event_types, f"missing {expected} in {event_types}"

    # Every event from this one execution is correlated by request_id.
    assert {e["request_id"] for e in events} == {result.request_id}
    assert {e["thread_id"] for e in events} == {result.thread_id}


async def test_route_selected_records_the_chosen_route(tmp_path, caplog):
    caplog.set_level("INFO", logger="nexus.observability")
    db_path = str(tmp_path / "obs.sqlite")

    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        await session.execute(nexus_runtime.new_thread_id(), "write a function")

    routed = [e for e in _events_from(caplog) if e["event_type"] == "route_selected"]
    assert routed
    assert routed[0]["route"] == "coding"
    assert routed[0]["node"] == "router"


async def test_classifier_failure_emits_classifier_completed_with_failure(
    tmp_path, caplog, monkeypatch
):
    monkeypatch.setattr(main, "_call_classifier", _boom)
    caplog.set_level("INFO", logger="nexus.observability")
    db_path = str(tmp_path / "obs.sqlite")

    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        await session.execute(nexus_runtime.new_thread_id(), "hello")

    classifier_completed = [
        e for e in _events_from(caplog) if e["event_type"] == "classifier_completed"
    ]
    assert classifier_completed
    assert classifier_completed[0]["success"] is False
    assert classifier_completed[0]["error_type"] == "RuntimeError"


async def test_agent_failure_emits_agent_completed_failure_but_workflow_still_completes(
    tmp_path, caplog, monkeypatch
):
    monkeypatch.setattr(main, "_call_llm", _boom)
    caplog.set_level("INFO", logger="nexus.observability")
    db_path = str(tmp_path / "obs.sqlite")

    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        result = await session.execute(nexus_runtime.new_thread_id(), "write a function")

    events = _events_from(caplog)
    event_types = [e["event_type"] for e in events]
    agent_completed = [e for e in events if e["event_type"] == "agent_completed"]

    assert agent_completed
    assert agent_completed[0]["success"] is False
    assert agent_completed[0]["error_type"] == "RuntimeError"

    # Phase 0's resilience contract still holds: node-level failure -> safe
    # fallback reply, not a crashed/failed workflow.
    assert result.success is True
    assert result.reply == main.GENERIC_FAILURE_MESSAGE
    assert "workflow_completed" in event_types
    assert "workflow_failed" not in event_types


async def test_workflow_level_failure_emits_workflow_failed(tmp_path, caplog):
    caplog.set_level("INFO", logger="nexus.observability")
    db_path = str(tmp_path / "obs.sqlite")

    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=db_path) as session:
        # Simulate a failure outside any node's own try/except (e.g. the
        # checkpointer itself), which is what workflow_failed exists for.
        async def _graph_boom(*args, **kwargs):
            raise RuntimeError("checkpointer exploded")

        session._graph.ainvoke = _graph_boom

        result = await session.execute(nexus_runtime.new_thread_id(), "hi")

    assert result.success is False
    assert result.reply == nexus_runtime.DEFAULT_FALLBACK_MESSAGE

    events = _events_from(caplog)
    event_types = [e["event_type"] for e in events]
    assert "workflow_failed" in event_types
    assert "workflow_completed" not in event_types

    failed = [e for e in events if e["event_type"] == "workflow_failed"][0]
    assert failed["success"] is False
    assert failed["error_type"] == "RuntimeError"
