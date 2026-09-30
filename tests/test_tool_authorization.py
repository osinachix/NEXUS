"""Tool authorization: a deterministic agent -> allowed-tool-names policy
that runs BEFORE a tool is ever invoked. The model proposing a tool call is
not sufficient for it to run -- `_instrument_tool`'s wrapper checks this
regardless of what the underlying tool call would have done, so there is no
code path by which the model's request alone executes a tool.
"""

import json

import pytest
from langchain_core.tools import tool

import main
import tool_policy as tp


@tool("fetch")
async def _fake_fetch(url: str) -> str:
    """Fake fetch tool for authorization tests."""
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


def test_policy_authorizes_logical_agent_for_fetch():
    assert tp.check_tool_authorized("logical", "fetch").allowed


def test_policy_denies_agents_with_no_tool_access():
    for agent_name in ("counselor", "math", "coding"):
        decision = tp.check_tool_authorized(agent_name, "fetch")
        assert not decision.allowed
        assert decision.reason_code == tp.DenyReason.TOOL_NOT_AUTHORIZED


def test_policy_denies_a_tool_name_not_in_the_agents_allowlist():
    decision = tp.check_tool_authorized("logical", "some_other_tool")
    assert not decision.allowed
    assert decision.reason_code == tp.DenyReason.TOOL_NOT_AUTHORIZED


async def test_authorized_agent_tool_call_succeeds():
    instrumented = main._instrument_tool(_fake_fetch, agent_name="logical")
    result = await instrumented.ainvoke(
        {"url": "https://example.com"},
        config={"configurable": {"request_id": "r1", "thread_id": "t1"}},
    )
    assert result == "content of https://example.com"


async def test_unauthorized_agent_is_denied_without_ever_calling_the_tool(monkeypatch):
    calls = []

    @tool("fetch")
    async def _tracking_fetch(url: str) -> str:
        """Fake fetch tool that records whether it was ever actually called."""
        calls.append(url)
        return "should never happen"

    # "future_agent" has no entry in AGENT_TOOL_POLICY at all -- exactly
    # the "future_agent: fetch -> denied" example from the Phase 2 spec.
    instrumented = main._instrument_tool(_tracking_fetch, agent_name="future_agent")
    result = await instrumented.ainvoke(
        {"url": "https://example.com"},
        config={"configurable": {"request_id": "r2", "thread_id": "t2"}},
    )

    assert calls == []  # the underlying tool body never ran
    payload = json.loads(result)
    assert payload["trust"] == "untrusted"
    assert "TOOL_NOT_AUTHORIZED" in payload["content"]


async def test_model_cannot_bypass_authorization_by_requesting_the_call_directly(caplog):
    # "The model proposes; the model cannot decide" -- simulate the model
    # requesting the call exactly as the ReAct loop would (no special
    # cooperation from the caller), and confirm the deterministic policy
    # still wins regardless.
    caplog.set_level("INFO", logger="nexus.observability")
    instrumented = main._instrument_tool(_fake_fetch, agent_name="counselor")

    result = await instrumented.ainvoke(
        {"url": "https://example.com/anything-the-model-wants"},
        config={"configurable": {"request_id": "r3", "thread_id": "t3"}},
    )

    payload = json.loads(result)
    assert "example.com" not in payload["content"]  # never actually fetched
    events = _events_from(caplog)
    denied = [e for e in events if e["event_type"] == "tool_denied"]
    assert denied
    assert denied[0]["reason"] == "TOOL_NOT_AUTHORIZED"
    assert "tool_started" not in [e["event_type"] for e in events]
