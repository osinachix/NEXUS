# Multi-Agent Router

A LangGraph-based chatbot that reads each message you send, decides what *kind* of message it
is, and routes it to one of four specialist agents, each with its own personality and system
prompt, all backed by Anthropic's Claude. One of those specialists (the logical agent) can also
reach out to the live web through an [MCP](https://modelcontextprotocol.io/) tool server instead
of relying only on what the model already knows.

## Table of contents

- [Overview](#overview)
- [How it works](#how-it-works)
- [What is MCP, and why does this project use it?](#what-is-mcp-and-why-does-this-project-use-it)
- [Prerequisites](#prerequisites)
- [Dependencies](#dependencies)
- [Setup](#setup)
- [Running the project](#running-the-project)
- [Project layout](#project-layout)
- [Troubleshooting](#troubleshooting)

## Overview

This is a small, self-contained example of a **multi-agent router** built with
[LangGraph](https://langchain-ai.github.io/langgraph/): a graph of nodes where a message flows
in, gets classified, and is handed off to whichever specialist node is best suited to answer it.
It's meant to be easy to read end to end in `main.py` and to demonstrate two ideas together:

1. **Routing**: using an LLM's structured output as a switch to pick the next step in a graph,
   instead of hard-coding logic or asking the user to choose a mode.
2. **Tool use via MCP**: giving one agent the ability to call an external tool (fetching a web
   page) through the Model Context Protocol, rather than hand-rolling a custom integration.

## How it works

```
START → classifier → router ─┬─ emotional → counselor ─┐
                              ├─ logical   → logical    ├─→ END
                              ├─ math      → math       │
                              └─ coding    → coding    ─┘
```

1. **classifier**: sends the latest user message to Claude with structured output, labeling it
   as `emotional`, `logical`, `math`, or `coding`. This is the only place classification happens.
2. **router**: plain Python (no LLM call), picks the next node based on that label.
3. One of four specialist agents replies, each with its own system prompt:
   - **counselor**: empathetic, validates feelings, asks reflective questions
   - **logical**: direct, fact-based, no emotional framing; can fetch live web pages via an MCP
     tool server (see below) when that would make its answer more accurate
   - **math**: solves problems step by step and states the final answer
   - **coding**: writes, explains, debugs, or reviews code
4. Every reply ends the graph run (`END`). The next message you type starts a fresh pass through
   `classifier → router → agent`, with the full conversation history carried forward in state.

![graph](graph.png)

## What is MCP, and why does this project use it?

[MCP (Model Context Protocol)](https://modelcontextprotocol.io/) is an open standard that lets an
LLM application connect to external tools and data sources (web fetchers, file systems,
databases, and so on) through a common protocol, instead of writing a bespoke integration for
every tool. An MCP *server* exposes one or more tools; any MCP-compatible client (this app, via
LangChain) can discover and call them.

In this project, three of the four specialist agents (counselor, math, coding) are plain LLM
calls: a system prompt plus the user's message, nothing more. The **logical** agent is different:
it's a tool-calling agent (`langchain.agents.create_agent`) wired to the official
[`mcp-server-fetch`](https://github.com/modelcontextprotocol/servers/tree/main/src/fetch) MCP
server via [`langchain-mcp-adapters`](https://github.com/langchain-ai/langchain-mcp-adapters).
That gives it a real `fetch` tool it can call mid-conversation to pull in a live web page, rather
than answering purely from what Claude already learned during training.

How it's wired together, concretely:

- `main.py` starts the fetch server as a **local subprocess over stdio**
  (`python -m mcp_server_fetch`, using the same Python interpreter that's running `main.py`).
- `MultiServerMCPClient` (from `langchain-mcp-adapters`) connects to that subprocess and loads its
  tools as regular LangChain `BaseTool` objects.
- Those tools are passed to `create_agent(...)`, which builds a small ReAct-style agent: Claude
  decides whether to call the `fetch` tool, reads the result, and then answers.
- Because loading MCP tools and calling them both require an async connection, the whole graph
  runs via `graph.ainvoke(...)` inside an `asyncio` event loop, instead of the synchronous
  `graph.invoke(...)` a tool-free version of this app could use.

The other three agents don't touch MCP at all: they're intentionally left as simple, no-tool LLM
calls so it's easy to compare "agent with a tool" against "agent without one" in the same file.

## Prerequisites

- Python **3.13** or newer
- An [Anthropic API key](https://console.anthropic.com/) with available credits
- Internet access at runtime (the `fetch` MCP tool makes outbound HTTP requests, and Claude calls
  go over the network too)

## Dependencies

Listed in [requirements.txt](requirements.txt) and [pyproject.toml](pyproject.toml):

| Package | Version | Why it's needed |
|---|---|---|
| `langchain[anthropic]` | >=0.3.24 | provides `init_chat_model` and `create_agent`, used to call Claude and build the tool-calling logical agent |
| `langgraph` | >=0.3.34 | the state-graph framework that defines and runs the classifier → router → agent flow |
| `langchain-mcp-adapters` | >=0.3.2 | connects to MCP servers over stdio and exposes their tools as LangChain tools |
| `mcp-server-fetch` | >=2026.8.18 | the official MCP server that gives the logical agent a `fetch` (web page) tool |
| `python-dotenv` | >=1.1.0 | loads `ANTHROPIC_API_KEY` from a local `.env` file into the environment |
| `ipykernel` | >=6.29.5 | lets this project be explored in a Jupyter/IPython notebook, if desired |

`langchain-mcp-adapters` and `mcp-server-fetch` pull in the official
[`mcp`](https://pypi.org/project/mcp/) SDK as a transitive dependency; you don't install it
directly.

## Setup

```bash
# 1. Clone and enter the project
git clone <this-repo-url>
cd "LangGraph Multi-Agent Router"

# 2. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt
```

Create a `.env` file in the project root with your Anthropic API key:

```
ANTHROPIC_API_KEY=your-key-here
```

`.env` is listed in [.gitignore](.gitignore) and will never be committed.

No separate MCP setup step is needed: `mcp-server-fetch` is a Python package installed by
`pip install -r requirements.txt` above, and `main.py` launches it automatically as a subprocess
when the app starts, so there's nothing extra to run or configure.

## Running the project

```bash
python main.py
```

On startup, `main.py` connects to the `fetch` MCP server and builds the logical agent before
opening the prompt, so the first `Message:` prompt may take a moment to appear.

Example session:

```
Message: I'm feeling really overwhelmed with work lately
Assistant: That sounds really difficult...

Message: what's 15% of 340?
Assistant: 15% of 340 = 51...

Message: what does the homepage at example.com say?
Assistant: [fetches https://example.com, then answers based on the page content]

Message: exit
Bye
```

Type `exit` at any prompt to quit.

## Project layout

- `main.py`: the router graph, the MCP-backed logical agent, and the chat loop (the actual app)
- `simple.py`: a minimal single-node LangGraph example with no routing or tools, kept as a
  standalone reference for the smallest possible LangGraph app
- `graph.png`: rendered diagram of the graph in `main.py`
- `requirements.txt`: pip dependency list
- `pyproject.toml`: project metadata (name, version, description, dependencies)

## Troubleshooting

- **`ModuleNotFoundError`**: the virtual environment isn't activated, or
  `pip install -r requirements.txt` wasn't run inside it.
- **Authentication / API errors** (`anthropic.AuthenticationError`, 401): check that `.env` exists
  in the project root and `ANTHROPIC_API_KEY` is set to a valid key with available credits.
- **Wrong Python version**: this project requires Python 3.13+; check with `python --version`.
- **`mcp.shared.exceptions.McpError: Connection closed`** or the logical agent hangs/fails on
  startup: this means the `fetch` MCP subprocess couldn't start. Confirm
  `pip install -r requirements.txt` completed successfully inside the *same* virtual environment
  you're using to run `python main.py` (a `python -m mcp_server_fetch --help` from that same venv
  should print its usage text).
- **Logical agent answers seem to ignore a URL you gave it**: the `fetch` tool is only called when
  Claude decides it's needed; try being explicit, e.g. "fetch https://example.com and summarize
  it."
