"""NEXUS Agent Registry (Phase 6.2).

Turns the four reference agents NEXUS already implements
(`main.py`'s `counselor_agent`/`logical_agent`/`math_agent`/`coding_agent`,
wired into both the automatic-routing graph and
`main.DIRECT_AGENT_GRAPH_BUILDERS`'s direct-agent graphs) into typed,
API-exposed platform resources -- so the Console (and any future client)
discovers agents via `GET /v1/agents` instead of hardcoding a list:

    agent metadata -> API -> Console

not

    hardcoded frontend agent list

This module is metadata and capability discovery only. It does not
implement or duplicate agent execution -- `main.py` remains the one
place agent behavior lives; this module only describes what's already
there. It is also the authoritative allowlist for direct-agent
execution: `api.py`'s `MessageRequest.agent` validator calls
`is_executable()` here, so an unknown or unavailable agent id can never
reach `NexusRuntime.execute()` / graph construction -- see
`is_executable`'s docstring.

Deliberately excluded from `AgentDefinition` (see SECURITY.md): system
prompts, model/provider configuration, API keys, and any other internal
implementation detail. Capabilities and tags below are hand-authored and
conservative -- never inferred from model output, never claiming
something main.py doesn't actually implement (see each entry's comment
for what backs it).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

import main
import tool_policy

AgentId = Literal["logical", "math", "coding", "counselor"]
AgentStatus = Literal["active", "unavailable"]
AgentExecutionMode = Literal["auto_route", "direct"]

# Both are always true today: every reference agent participates in the
# automatic-routing graph AND has a direct-agent graph in
# main.DIRECT_AGENT_GRAPH_BUILDERS. Not hardcoded per-agent below because
# there is currently no agent for which this varies -- if one is ever
# added, this becomes a per-agent field instead of a shared constant.
_EXECUTION_MODES: list[AgentExecutionMode] = ["auto_route", "direct"]

# Display order for the registry's list endpoint / the Console's Agents
# page -- matches the order the Phase 6.1 Playground already used.
_REGISTRY_ORDER: tuple[AgentId, ...] = ("logical", "math", "coding", "counselor")


class AgentDefinition(BaseModel):
    """Public, safe agent metadata -- crosses the API boundary as-is.
    Never includes a system prompt, model/provider configuration,
    credentials, or any other internal detail; see this module's
    docstring and SECURITY.md."""

    id: AgentId
    name: str
    description: str = Field(..., description="Concise, user-facing description of what this agent does.")
    status: AgentStatus = Field(
        ..., description="'active' if this agent's execution path is actually constructed and usable "
        "right now, 'unavailable' otherwise. Never hardcoded true -- see _logical_status()."
    )
    execution_mode: list[AgentExecutionMode] = Field(
        default_factory=lambda: list(_EXECUTION_MODES),
        description="How this agent can be invoked: 'auto_route' (the classifier may select it) and/or "
        "'direct' (MessageRequest.agent may name it directly).",
    )
    tools: list[str] = Field(
        default_factory=list, description="Tool names this agent is authorized to use, from the same "
        "tool_policy.AGENT_TOOL_POLICY the runtime itself enforces -- never a separate, driftable list."
    )
    capabilities: list[str] = Field(
        default_factory=list, description="Conservative, hand-authored capability tags. Omitted rather "
        "than guessed when uncertain -- never inferred from model output."
    )
    tags: list[str] = Field(default_factory=list)
    version: str = "1.0.0"


def _logical_status() -> AgentStatus:
    """The one agent with real, checkable construction state: `main.
    logical_react_agent` is built once at API/CLI startup
    (`main.build_logical_agent()`) and is `None` only before that has
    happened -- exactly the condition `main.logical_agent()` itself
    already checks before executing a turn (see main.py). The other
    three agents are plain LLM calls against the always-present, module-
    level `main.llm` with no analogous fallible construction step, so
    they have no equivalent "unavailable" state to detect.
    """
    return "active" if main.logical_react_agent is not None else "unavailable"


def _tools_for(agent_id: str) -> list[str]:
    return sorted(tool_policy.AGENT_TOOL_POLICY.get(agent_id, frozenset()))


def _build_registry() -> dict[AgentId, AgentDefinition]:
    # Rebuilt on every call (cheap: four small Pydantic models) rather
    # than cached at import time, specifically so `status` always
    # reflects `main.logical_react_agent`'s CURRENT value -- constructed
    # after this module is first imported (see api.py's `lifespan`) -- not
    # whatever it was at import time.
    return {
        "logical": AgentDefinition(
            id="logical",
            name="Logical",
            description="Fact-based reasoning and information retrieval. Can fetch live web pages via a "
            "policy-gated tool.",
            status=_logical_status(),
            tools=_tools_for("logical"),
            capabilities=["reasoning", "web_retrieval"],
            tags=["reference"],
        ),
        "math": AgentDefinition(
            id="math",
            name="Math",
            description="Solves problems step by step and states the final answer.",
            status="active",
            tools=_tools_for("math"),
            capabilities=["mathematical_reasoning"],
            tags=["reference"],
        ),
        "coding": AgentDefinition(
            id="coding",
            name="Coding",
            description="Writes, explains, debugs, and reviews code.",
            status="active",
            tools=_tools_for("coding"),
            capabilities=["coding", "software_reasoning"],
            tags=["reference"],
        ),
        "counselor": AgentDefinition(
            id="counselor",
            name="Counselor",
            description="Empathetic, reflective responses to emotional messages.",
            status="active",
            tools=_tools_for("counselor"),
            capabilities=["conversational_support"],
            tags=["reference"],
        ),
    }


def list_agents() -> list[AgentDefinition]:
    """All registered agents, in a stable display order."""
    registry = _build_registry()
    return [registry[agent_id] for agent_id in _REGISTRY_ORDER]


def get_agent(agent_id: str) -> AgentDefinition | None:
    """The named agent's current metadata, or `None` if `agent_id` isn't
    a registered agent at all (distinct from a registered-but-unavailable
    agent, which returns a normal AgentDefinition with status=
    'unavailable' -- see api.py's 404 vs. 400 handling)."""
    return _build_registry().get(agent_id)


def is_executable(agent_id: str) -> bool:
    """The single check gating whether `NexusRuntime.execute(agent=...)`
    may ever be called with this id: `agent_id` must be a known,
    registered agent AND currently 'active'. Used by api.py's
    `MessageRequest.agent` validator so an unknown or unavailable agent
    id can never reach graph construction -- the registry is the
    authoritative allowlist, not `main.DIRECT_AGENT_GRAPH_BUILDERS`'s
    keys directly (though today the two are required to match exactly;
    see tests/test_agent_registry.py).
    """
    agent = get_agent(agent_id)
    return agent is not None and agent.status == "active"
