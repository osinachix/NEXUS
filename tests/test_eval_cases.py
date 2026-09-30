"""Per-dimension evaluators (Phase 4). Uses synthetic `run_store.RunRecord`
objects directly -- these test the pure evaluation logic, independent of
NexusRuntime/LangGraph (which is covered separately in
tests/test_evaluator.py).
"""

import run_store
from evals import cases
from evals.models import EvaluationCase


def _record(
    *,
    route="math",
    success=True,
    reply="the answer is 391",
    duration_ms=100.0,
    tool_events=None,
    error_type=None,
) -> run_store.RunRecord:
    return run_store.RunRecord(
        request_id="req-1",
        thread_id="thread-1",
        status="completed" if success else "failed",
        success=success,
        route=route,
        message_type=route,
        reply=reply,
        started_at="t0",
        completed_at="t1",
        duration_ms=duration_ms,
        events=[],
        tool_events=tool_events or [],
        usage=None,
        cost_usd=None,
        error_type=error_type,
    )


def _tool_event(tool: str, event_type: str) -> run_store.ToolEvent:
    return run_store.ToolEvent(tool=tool, event_type=event_type, timestamp="t")


# --- routing -----------------------------------------------------------


def test_expected_route_match_passes():
    case = EvaluationCase(id="c1", name="C1", input="x", expected_route="math")
    result = cases.evaluate_routing(case, _record(route="math"))
    assert result.passed is True


def test_expected_route_mismatch_fails():
    case = EvaluationCase(id="c1", name="C1", input="x", expected_route="math")
    result = cases.evaluate_routing(case, _record(route="coding"))
    assert result.passed is False


def test_no_expected_route_is_not_evaluated():
    case = EvaluationCase(id="c1", name="C1", input="x")
    assert cases.evaluate_routing(case, _record(route="math")) is None


# --- execution -----------------------------------------------------------


def test_execution_success_passes():
    case = EvaluationCase(id="c1", name="C1", input="x")
    result = cases.evaluate_execution(case, _record(success=True))
    assert result.passed is True


def test_execution_failure_is_detected():
    case = EvaluationCase(id="c1", name="C1", input="x")
    result = cases.evaluate_execution(case, _record(success=False, error_type="RuntimeError"))
    assert result.passed is False
    assert "RuntimeError" in result.detail


# --- tools -----------------------------------------------------------


def test_expected_tool_invocation_detected():
    case = EvaluationCase(id="c1", name="C1", input="x", expected_tools=["fetch"])
    record = _record(tool_events=[_tool_event("fetch", "tool_completed")])
    results = cases.evaluate_tools(case, record)
    assert len(results) == 1
    assert results[0].passed is True


def test_expected_tool_missing_is_detected():
    case = EvaluationCase(id="c1", name="C1", input="x", expected_tools=["fetch"])
    record = _record(tool_events=[])
    results = cases.evaluate_tools(case, record)
    assert results[0].passed is False


def test_forbidden_tool_invocation_detected():
    case = EvaluationCase(id="c1", name="C1", input="x", forbidden_tools=["fetch"])
    record = _record(tool_events=[_tool_event("fetch", "tool_started")])
    results = cases.evaluate_tools(case, record)
    assert results[0].passed is False


def test_forbidden_tool_correctly_absent_passes():
    case = EvaluationCase(id="c1", name="C1", input="x", forbidden_tools=["fetch"])
    record = _record(tool_events=[])
    results = cases.evaluate_tools(case, record)
    assert results[0].passed is True


def test_tool_denied_still_counts_as_invoked_attempt():
    # A tool that was proposed and then denied by Phase 2 policy was still
    # "invoked" in the sense expected_tools/forbidden_tools care about --
    # the model tried to use it, regardless of the policy outcome.
    case = EvaluationCase(id="c1", name="C1", input="x", expected_tools=["fetch"])
    record = _record(tool_events=[_tool_event("fetch", "tool_denied")])
    results = cases.evaluate_tools(case, record)
    assert results[0].passed is True


def test_tool_usage_is_never_inferred_from_response_text():
    # The reply text claims fetch was used, but no tool_events say so --
    # must fail, proving this doesn't parse natural language.
    case = EvaluationCase(id="c1", name="C1", input="x", expected_tools=["fetch"])
    record = _record(reply="I used the fetch tool to look this up.", tool_events=[])
    results = cases.evaluate_tools(case, record)
    assert results[0].passed is False


# --- response checks -----------------------------------------------------------


def test_response_contains_passes():
    case = EvaluationCase(id="c1", name="C1", input="x", response_contains=["391"])
    results = cases.evaluate_response(case, _record(reply="the answer is 391"))
    assert results[0].passed is True


def test_response_contains_failure_detected():
    case = EvaluationCase(id="c1", name="C1", input="x", response_contains=["999"])
    results = cases.evaluate_response(case, _record(reply="the answer is 391"))
    assert results[0].passed is False


def test_response_not_contains_passes_when_absent():
    case = EvaluationCase(id="c1", name="C1", input="x", response_not_contains=["error"])
    results = cases.evaluate_response(case, _record(reply="the answer is 391"))
    assert results[0].passed is True


def test_response_not_contains_fails_when_present():
    case = EvaluationCase(id="c1", name="C1", input="x", response_not_contains=["391"])
    results = cases.evaluate_response(case, _record(reply="the answer is 391"))
    assert results[0].passed is False


# --- latency -----------------------------------------------------------


def test_latency_within_budget_passes():
    case = EvaluationCase(id="c1", name="C1", input="x", max_latency_ms=1000)
    result = cases.evaluate_latency(case, _record(duration_ms=500))
    assert result.passed is True


def test_latency_over_budget_fails():
    case = EvaluationCase(id="c1", name="C1", input="x", max_latency_ms=100)
    result = cases.evaluate_latency(case, _record(duration_ms=500))
    assert result.passed is False


def test_no_latency_budget_is_not_evaluated():
    case = EvaluationCase(id="c1", name="C1", input="x")
    assert cases.evaluate_latency(case, _record(duration_ms=99999)) is None


# --- full case combination -----------------------------------------------------------


def test_evaluate_case_combines_all_dimensions_with_and_semantics():
    case = EvaluationCase(
        id="c1", name="C1", input="x", expected_route="math", response_contains=["391"]
    )
    good = cases.evaluate_case(case, _record(route="math", reply="391"))
    assert good.passed is True

    bad_route = cases.evaluate_case(case, _record(route="coding", reply="391"))
    assert bad_route.passed is False

    bad_response = cases.evaluate_case(case, _record(route="math", reply="wrong answer"))
    assert bad_response.passed is False


def test_evaluate_case_with_only_routing_is_sufficient_for_counselor_style_cases():
    # Matches README/task guidance: for the counselor agent, routing +
    # successful execution alone should be enough to pass.
    case = EvaluationCase(id="c1", name="Emotional", input="I feel overwhelmed", expected_route="counselor")
    result = cases.evaluate_case(case, _record(route="counselor", success=True, reply="anything"))
    assert result.passed is True
    assert {d.dimension for d in result.dimensions} == {"routing", "execution"}
