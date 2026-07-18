# Multi-Agent Router

A LangGraph-based chatbot that classifies each incoming message and routes it to
one of four specialist agents, all backed by Anthropic's Claude.

## How it works

```
START → classifier → router ─┬─ emotional → counselor ─┐
                              ├─ logical   → logical    ├─→ END
                              ├─ math      → math       │
                              └─ coding    → coding    ─┘
```

1. **classifier** — sends the latest user message to Claude with structured output,
   labeling it as `emotional`, `logical`, `math`, or `coding`.
2. **router** — plain Python (no LLM call) — picks the next node based on that label.
3. One of four specialist agents replies, each with its own system prompt:
   - **counselor** — empathetic, validates feelings, asks reflective questions
   - **logical** — direct, fact-based, no emotional framing
   - **math** — solves problems step by step and states the final answer
   - **coding** — writes, explains, debugs, or reviews code

![graph](graph.png)

## Prerequisites

- Python **3.13** or newer
- An [Anthropic API key](https://console.anthropic.com/) with available credits

## Dependencies

Listed in [requirements.txt](requirements.txt):

| Package | Why it's needed |
|---|---|
| `langchain[anthropic]` | provides `init_chat_model`, the chat-model wrapper used to call Claude |
| `langgraph` | the state-graph framework that defines and runs the classifier → router → agent flow |
| `python-dotenv` | loads `ANTHROPIC_API_KEY` from a local `.env` file into the environment |
| `ipykernel` | lets this project be explored in a Jupyter/IPython notebook, if desired |

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

## Usage

```bash
python main.py
```

Example session:

```
Message: I'm feeling really overwhelmed with work lately
Assistant: That sounds really difficult...

Message: what's 15% of 340?
Assistant: 15% of 340 = 51...

Message: exit
Bye
```

Type `exit` at any prompt to quit.

## Project layout

- `main.py` — the router graph and chat loop (the actual app)
- `simple.py` — a minimal single-node LangGraph example, kept as a standalone reference
- `graph.png` — rendered diagram of the graph in `main.py`
- `requirements.txt` — pip dependency list
- `pyproject.toml` — project metadata (name, version, description)

## Troubleshooting

- **`ModuleNotFoundError`** — the virtual environment isn't activated, or
  `pip install -r requirements.txt` wasn't run inside it.
- **Authentication / API errors** — check that `.env` exists in the project root and
  `ANTHROPIC_API_KEY` is set to a valid key with available credits.
- **Wrong Python version** — this project requires Python 3.13+; check with `python --version`.
