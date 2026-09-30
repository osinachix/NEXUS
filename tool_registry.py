"""Safe public metadata for the tool definitions bound to NEXUS agents.

The tool definitions come from ``main.LOGICAL_AGENT_TOOL_DEFINITIONS`` and
authorization comes from ``tool_policy.AGENT_TOOL_POLICY``. This module does
not introduce a second tool allowlist or expose runtime configuration.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

import agents
import main
import tool_policy

ToolStatus = Literal["active", "unavailable"]
ToolExecutionType = Literal["native"]


class ToolDefinition(BaseModel):
    """Safe, read-only metadata for one currently registered tool."""

    id: str
    name: str
    description: str
    status: ToolStatus = Field(
        description="Active means this tool is bound to at least one currently callable agent graph."
    )
    execution_type: ToolExecutionType
    allowed_agents: list[str]
    controls: list[str]


_SAFE_CONTROLS = {
    "fetch": [
        "HTTPS is required by default; HTTP can be enabled for local development.",
        "Validates URLs and rejects embedded credentials and unsupported schemes.",
        "Applies an optional exact-host allowlist and blocks private or reserved destinations.",
        "Revalidates every redirect before following it.",
        "Limits response size and request duration.",
        "Pins each connection to its validated destination.",
        "Marks fetched content as untrusted data.",
    ],
}


def _public_allowed_agents(tool_name: str) -> list[str]:
    public_agent_ids = {agent.id for agent in agents.list_agents()}
    return sorted(
        agent_id
        for agent_id, allowed_tools in tool_policy.AGENT_TOOL_POLICY.items()
        if agent_id in public_agent_ids and tool_name in allowed_tools
    )


def _is_callable(tool_name: str, allowed_agents: list[str]) -> bool:
    if not allowed_agents:
        return False
    # The current tool binding is deliberately explicit. Logical is the only
    # agent with a tool-capable graph, and build_logical_agent binds every
    # definition in this same tuple.
    return (
        "logical" in allowed_agents
        and main.logical_react_agent is not None
        and any(tool.name == tool_name for tool in main.LOGICAL_AGENT_TOOL_DEFINITIONS)
    )


def list_tools() -> list[ToolDefinition]:
    """Return public metadata derived from actual definitions and policy."""
    definitions: list[ToolDefinition] = []
    for tool in main.LOGICAL_AGENT_TOOL_DEFINITIONS:
        allowed_agents = _public_allowed_agents(tool.name)
        definitions.append(
            ToolDefinition(
                id=tool.name,
                name=tool.name,
                description=tool.description,
                status="active" if _is_callable(tool.name, allowed_agents) else "unavailable",
                execution_type="native",
                allowed_agents=allowed_agents,
                controls=list(_SAFE_CONTROLS.get(tool.name, [])),
            )
        )
    return definitions
