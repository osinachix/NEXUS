"""The NEXUS Agent Registry (Phase 6.2, agents.py): metadata + capability
discovery over the agents main.py actually implements. Pure module-level
tests; API-level tests (auth, 404, execution mapping) live in
tests/test_api_agents.py.
"""

import pytest

import agents
import main
import tool_policy


def test_list_agents_returns_all_four_reference_agents():
    ids = {agent.id for agent in agents.list_agents()}
    assert ids == {"logical", "math", "coding", "counselor"}


def test_list_agents_ids_exactly_match_direct_agent_graph_builders():
    # The registry must never drift from the actual backend-implemented
    # set of direct-agent graphs -- if a future agent is added to one but
    # not the other, this test catches it immediately.
    registry_ids = {agent.id for agent in agents.list_agents()}
    assert registry_ids == set(main.DIRECT_AGENT_GRAPH_BUILDERS.keys())


def test_get_agent_returns_none_for_unknown_id():
    assert agents.get_agent("not-a-real-agent") is None


@pytest.mark.parametrize("agent_id", ["logical", "math", "coding", "counselor"])
def test_get_agent_returns_stable_metadata(agent_id):
    agent = agents.get_agent(agent_id)
    assert agent is not None
    assert agent.id == agent_id
    assert agent.name
    assert agent.description


def test_logical_agent_lists_its_real_tool_authorization():
    agent = agents.get_agent("logical")
    assert agent.tools == sorted(tool_policy.AGENT_TOOL_POLICY["logical"])
    assert "fetch" in agent.tools


@pytest.mark.parametrize("agent_id", ["math", "coding", "counselor"])
def test_non_tool_agents_report_no_tools(agent_id):
    agent = agents.get_agent(agent_id)
    assert agent.tools == []


def test_capabilities_are_present_and_conservative():
    logical = agents.get_agent("logical")
    assert "reasoning" in logical.capabilities
    math = agents.get_agent("math")
    assert "mathematical_reasoning" in math.capabilities
    coding = agents.get_agent("coding")
    assert "coding" in coding.capabilities
    counselor = agents.get_agent("counselor")
    assert "conversational_support" in counselor.capabilities


def test_no_agent_metadata_leaks_internal_details():
    # Defensive check: nothing in the public AgentDefinition shape should
    # ever be able to carry a system prompt, credential, or similar --
    # this test would catch a future field added carelessly.
    for agent in agents.list_agents():
        dumped = agent.model_dump()
        assert set(dumped.keys()) == {
            "id", "name", "description", "status", "execution_mode", "tools", "capabilities", "tags", "version",
        }


def test_execution_mode_includes_both_auto_route_and_direct_for_every_agent():
    for agent in agents.list_agents():
        assert set(agent.execution_mode) == {"auto_route", "direct"}


class TestStatus:
    def test_math_coding_counselor_are_always_active(self):
        for agent_id in ("math", "coding", "counselor"):
            assert agents.get_agent(agent_id).status == "active"

    def test_logical_is_active_when_constructed(self, monkeypatch):
        monkeypatch.setattr(main, "logical_react_agent", object())
        assert agents.get_agent("logical").status == "active"

    def test_logical_is_unavailable_when_not_constructed(self, monkeypatch):
        monkeypatch.setattr(main, "logical_react_agent", None)
        assert agents.get_agent("logical").status == "unavailable"


class TestIsExecutable:
    def test_unknown_agent_is_not_executable(self):
        assert agents.is_executable("not-a-real-agent") is False

    def test_active_agent_is_executable(self, monkeypatch):
        monkeypatch.setattr(main, "logical_react_agent", object())
        assert agents.is_executable("logical") is True

    def test_unavailable_agent_is_not_executable(self, monkeypatch):
        monkeypatch.setattr(main, "logical_react_agent", None)
        assert agents.is_executable("logical") is False

    def test_always_active_agents_are_executable(self):
        assert agents.is_executable("math") is True
        assert agents.is_executable("coding") is True
        assert agents.is_executable("counselor") is True
