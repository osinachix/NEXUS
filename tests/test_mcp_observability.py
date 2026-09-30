"""Tool observability: `_instrument_tool` wraps a tool so calls emit
tool_started/tool_completed/tool_failed with metadata only -- never the raw
arguments or result, which for the real `fetch` tool could be a sensitive
URL or page content.

Uses a fake tool *named* "fetch" (matching main.tool_policy's
AGENT_TOOL_POLICY for the "logical" agent) so these tests exercise the real
authorization gate rather than needing to special-case it away.
"""

import json

import pytest
from langchain_core.tools import tool

import main


@tool("fetch")
async def _fake_fetch(url: str) -> str:
    """Fake fetch tool standing in for the real `fetch` tool."""
    if url == "fail":
        raise RuntimeError("connection refused")
    return f"content of {url}"


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


async def test_tool_started_and_completed_emitted_on_success(caplog):
    caplog.set_level("INFO", logger="nexus.observability")
    instrumented = main._instrument_tool(_fake_fetch, agent_name="logical")

    result = await instrumented.ainvoke(
        {"url": "https://example.com"},
        config={"configurable": {"request_id": "req-1", "thread_id": "thread-1"}},
    )

    assert result == "content of https://example.com"

    events = _events_from(caplog)
    event_types = [e["event_type"] for e in events]
    assert "tool_started" in event_types
    assert "tool_completed" in event_types
    assert all(e["request_id"] == "req-1" and e["thread_id"] == "thread-1" for e in events)
    assert all(e["tool"] == "fetch" for e in events)

    completed = [e for e in events if e["event_type"] == "tool_completed"][0]
    assert completed["success"] is True
    assert "duration_ms" in completed


async def test_tool_failed_emitted_on_exception_and_not_tool_completed(caplog):
    caplog.set_level("INFO", logger="nexus.observability")
    instrumented = main._instrument_tool(_fake_fetch, agent_name="logical")

    with pytest.raises(RuntimeError):
        await instrumented.ainvoke(
            {"url": "fail"},
            config={"configurable": {"request_id": "req-2", "thread_id": "thread-2"}},
        )

    events = _events_from(caplog)
    event_types = [e["event_type"] for e in events]
    assert "tool_started" in event_types
    assert "tool_failed" in event_types
    assert "tool_completed" not in event_types

    failed = [e for e in events if e["event_type"] == "tool_failed"][0]
    assert failed["success"] is False
    assert failed["error_type"] == "RuntimeError"


async def test_instrumented_tool_preserves_name_description_and_schema():
    instrumented = main._instrument_tool(_fake_fetch, agent_name="logical")
    assert instrumented.name == _fake_fetch.name
    assert instrumented.description == _fake_fetch.description
    # The model-visible schema is untouched: no `config` leaks into it.
    assert list(instrumented.args_schema.model_fields.keys()) == ["url"]


async def test_tool_event_does_not_include_raw_url_or_result(caplog):
    caplog.set_level("INFO", logger="nexus.observability")
    instrumented = main._instrument_tool(_fake_fetch, agent_name="logical")

    await instrumented.ainvoke(
        {"url": "https://secret-internal-host.example/private"},
        config={"configurable": {"request_id": "req-3", "thread_id": "thread-3"}},
    )

    # Only metadata (ids, tool name, timing, success) is logged -- the tool
    # wrapper never passes the call's args/result into log_event.
    assert "secret-internal-host" not in caplog.text
    assert "content of https://secret-internal-host.example/private" not in caplog.text
