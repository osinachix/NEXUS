"""NEXUS evaluation framework (Phase 4).

Evaluation Dataset -> Evaluation Runner -> NexusRuntime -> Agent Execution
-> Structured Run Data (run_store.RunRecord) -> Evaluators (evals.cases)
-> Evaluation Result -> Metrics / Comparison (evals.metrics)

Deliberately separate from LangGraph nodes, API routing, CLI presentation,
and provider-specific code -- see each module's docstring for how.

The deterministic test suite (tests/test_eval_*.py) never imports
`evals.run` and never requires a real LLM provider or network access; only
`python -m evals.run` (or `python -m evals`) does that, explicitly, as a
separate "live evaluation" entrypoint. See evals/run.py.
"""
