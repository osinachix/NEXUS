"""Per-dimension evaluators for NEXUS evaluation cases (Phase 4).

Each function checks one thing against a `run_store.RunRecord` -- the
structured data actually captured for that execution -- and never the
model's natural-language response text for anything except the explicit,
intentionally-basic `response_contains`/`response_not_contains` checks.
Tool usage in particular is verified from `run.tool_events` (real
`tool_started`/`tool_completed`/`tool_denied`/`tool_failed` observability
events), never inferred from what the reply text happens to say it did.

No LLM-as-judge here, by design -- see README "Evaluation" for why that's
explicitly out of scope for this phase.
"""

from __future__ import annotations

import run_store

from .models import DimensionResult, EvaluationCase, EvaluationResult

_TOOL_ATTEMPTED_EVENTS = {"tool_started", "tool_completed", "tool_denied", "tool_failed"}


def evaluate_routing(case: EvaluationCase, run: run_store.RunRecord) -> DimensionResult | None:
    """None (not evaluated) if the case doesn't specify expected_route --
    routing correctness is opt-in per case, not assumed."""
    if case.expected_route is None:
        return None
    passed = run.route == case.expected_route
    return DimensionResult(
        dimension="routing",
        passed=passed,
        detail=f"expected_route={case.expected_route!r} actual_route={run.route!r}",
    )


def evaluate_execution(case: EvaluationCase, run: run_store.RunRecord) -> DimensionResult:
    """Always evaluated: did the workflow complete successfully? This is
    `run.success` (NexusRuntime's own workflow-level outcome), not a guess
    based on response content."""
    detail = "" if run.success else f"error_type={run.error_type!r}"
    return DimensionResult(dimension="execution", passed=run.success, detail=detail)


def evaluate_tools(case: EvaluationCase, run: run_store.RunRecord) -> list[DimensionResult]:
    """One result per entry in expected_tools/forbidden_tools. Uses
    `run.tool_events` -- real observability events -- never the reply text.
    "Invoked" means the tool was at least attempted (tool_started or any
    outcome of it), matching what a human would mean by "did it try to use
    the tool," independent of whether the call was then denied by policy.
    """
    attempted = {event.tool for event in run.tool_events if event.event_type in _TOOL_ATTEMPTED_EVENTS}
    results: list[DimensionResult] = []
    for tool in case.expected_tools:
        passed = tool in attempted
        results.append(
            DimensionResult(dimension="tools", passed=passed, detail=f"expected tool {tool!r} invoked={passed}")
        )
    for tool in case.forbidden_tools:
        invoked = tool in attempted
        results.append(
            DimensionResult(
                dimension="tools", passed=not invoked, detail=f"forbidden tool {tool!r} invoked={invoked}"
            )
        )
    return results


def evaluate_response(case: EvaluationCase, run: run_store.RunRecord) -> list[DimensionResult]:
    """Simple, deterministic substring checks -- intentionally basic (no
    LLM-as-judge in this phase, see module docstring)."""
    results: list[DimensionResult] = []
    for substring in case.response_contains:
        passed = substring in run.reply
        results.append(
            DimensionResult(
                dimension="response", passed=passed, detail=f"expected substring {substring!r} present={passed}"
            )
        )
    for substring in case.response_not_contains:
        present = substring in run.reply
        results.append(
            DimensionResult(
                dimension="response",
                passed=not present,
                detail=f"forbidden substring {substring!r} present={present}",
            )
        )
    return results


def evaluate_latency(case: EvaluationCase, run: run_store.RunRecord) -> DimensionResult | None:
    if case.max_latency_ms is None:
        return None
    passed = run.duration_ms <= case.max_latency_ms
    return DimensionResult(
        dimension="latency",
        passed=passed,
        detail=f"max_latency_ms={case.max_latency_ms} actual_duration_ms={run.duration_ms:.1f}",
    )


def evaluate_case(case: EvaluationCase, run: run_store.RunRecord) -> EvaluationResult:
    """Run every applicable dimension for one case against its captured
    run and combine them into one EvaluationResult. `passed` is the AND of
    every dimension that was actually evaluated (opt-in dimensions that
    weren't requested by the case don't count against it)."""
    dimensions: list[DimensionResult] = []

    routing_result = evaluate_routing(case, run)
    if routing_result is not None:
        dimensions.append(routing_result)

    dimensions.append(evaluate_execution(case, run))
    dimensions.extend(evaluate_tools(case, run))
    dimensions.extend(evaluate_response(case, run))

    latency_result = evaluate_latency(case, run)
    if latency_result is not None:
        dimensions.append(latency_result)

    return EvaluationResult(
        case_id=case.id,
        case_name=case.name,
        request_id=run.request_id,
        thread_id=run.thread_id,
        passed=all(dimension.passed for dimension in dimensions),
        dimensions=dimensions,
        run=run,
    )
