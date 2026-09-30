"""Latency aggregation, token/cost totals, and comparison (Phase 4)."""

import run_store
from evals import metrics
from evals.cases import evaluate_case
from evals.models import EvaluationCase, EvaluationDataset, EvaluationSummary, RunMetrics


def _record(request_id, *, duration_ms, usage=None, cost_usd=None, route="math", success=True):
    return run_store.RunRecord(
        request_id=request_id,
        thread_id=f"thread-{request_id}",
        status="completed" if success else "failed",
        success=success,
        route=route,
        message_type=route,
        reply="ok",
        started_at="t0",
        completed_at="t1",
        duration_ms=duration_ms,
        events=[],
        tool_events=[],
        usage=usage,
        cost_usd=cost_usd,
        error_type=None,
    )


def _result(request_id, **kwargs):
    case = EvaluationCase(id=request_id, name=request_id, input="x")
    return evaluate_case(case, _record(request_id, **kwargs))


# --- latency aggregation -----------------------------------------------------------


def test_latency_min_max_mean():
    results = [_result(f"r{i}", duration_ms=v) for i, v in enumerate([100, 200, 300])]
    agg = metrics.aggregate_metrics(results)
    assert agg.latency_min_ms == 100
    assert agg.latency_max_ms == 300
    assert agg.latency_mean_ms == 200


def test_percentiles_on_known_distribution():
    # 0..100 in steps of 10 (11 values): p50 is the median (index 5 -> 50),
    # matching numpy's default linear-interpolation percentile method.
    values = list(range(0, 101, 10))
    results = [_result(f"r{i}", duration_ms=float(v)) for i, v in enumerate(values)]
    agg = metrics.aggregate_metrics(results)
    assert agg.latency_p50_ms == 50.0
    assert agg.latency_p95_ms == 95.0
    assert agg.latency_p99_ms == 99.0


def test_single_result_percentiles_equal_that_value():
    results = [_result("r0", duration_ms=42.0)]
    agg = metrics.aggregate_metrics(results)
    assert agg.latency_p50_ms == agg.latency_p95_ms == agg.latency_p99_ms == 42.0


def test_empty_results_has_no_metrics():
    agg = metrics.aggregate_metrics([])
    assert agg.count == 0
    assert agg.latency_p50_ms is None


# --- token / cost aggregation -----------------------------------------------------------


def test_token_totals_aggregate_across_runs():
    usage_a = run_store.TokenUsage(input_tokens=10, output_tokens=20, total_tokens=30)
    usage_b = run_store.TokenUsage(input_tokens=5, output_tokens=15, total_tokens=20)
    results = [
        _result("r0", duration_ms=1, usage=usage_a),
        _result("r1", duration_ms=1, usage=usage_b),
    ]
    agg = metrics.aggregate_metrics(results)
    assert agg.total_input_tokens == 15
    assert agg.total_output_tokens == 35
    assert agg.total_tokens == 50


def test_usage_unavailable_yields_none_not_zero():
    results = [_result("r0", duration_ms=1, usage=None)]
    agg = metrics.aggregate_metrics(results)
    assert agg.total_input_tokens is None
    assert agg.total_output_tokens is None
    assert agg.total_tokens is None


def test_cost_totals_aggregate_when_available():
    results = [
        _result("r0", duration_ms=1, cost_usd=0.01),
        _result("r1", duration_ms=1, cost_usd=0.02),
    ]
    agg = metrics.aggregate_metrics(results)
    assert round(agg.total_cost_usd, 4) == 0.03


def test_cost_unavailable_yields_none():
    results = [_result("r0", duration_ms=1, cost_usd=None)]
    agg = metrics.aggregate_metrics(results)
    assert agg.total_cost_usd is None


def test_partial_cost_availability_only_sums_whats_known():
    # One run has cost, one doesn't (e.g. pricing added mid-set) -- sum
    # what's known rather than discarding everything to None.
    results = [
        _result("r0", duration_ms=1, cost_usd=0.01),
        _result("r1", duration_ms=1, cost_usd=None),
    ]
    agg = metrics.aggregate_metrics(results)
    assert round(agg.total_cost_usd, 4) == 0.01


# --- summary -----------------------------------------------------------


def test_summarize_computes_rates():
    dataset = EvaluationDataset(name="d", version="1.0.0", cases=[])
    results = [
        _result("r0", duration_ms=1, route="math", success=True),
        _result("r1", duration_ms=1, route="coding", success=False),
    ]
    summary = metrics.summarize(dataset, results, evaluation_id="eval-x")
    assert summary.evaluation_id == "eval-x"
    assert summary.total_cases == 2
    assert summary.passed_cases == 1  # r1 failed execution
    assert summary.failed_cases == 1
    assert summary.execution_success_rate == 0.5


# --- comparison -----------------------------------------------------------


def _summary(evaluation_id, *, routing=None, exec_rate=1.0, p95=None, cost=None):
    return EvaluationSummary(
        evaluation_id=evaluation_id,
        dataset_name="d",
        dataset_version="1.0.0",
        created_at="t",
        total_cases=5,
        passed_cases=4,
        failed_cases=1,
        routing_accuracy=routing,
        execution_success_rate=exec_rate,
        tool_success_rate=None,
        metrics=RunMetrics(count=5, latency_p95_ms=p95, total_cost_usd=cost),
    )


def test_compare_computes_deltas():
    a = _summary("eval-a", routing=0.8, exec_rate=1.0, p95=200, cost=0.05)
    b = _summary("eval-b", routing=1.0, exec_rate=0.8, p95=150, cost=0.10)
    result = metrics.compare(a, b)
    assert round(result.routing_accuracy_delta, 4) == 0.2
    assert round(result.execution_success_rate_delta, 4) == -0.2
    assert result.latency_p95_delta_ms == -50
    assert round(result.total_cost_usd_delta, 4) == 0.05


def test_compare_handles_missing_metrics_safely():
    a = _summary("eval-a", routing=None, p95=None, cost=None)
    b = _summary("eval-b", routing=1.0, p95=150, cost=0.10)
    result = metrics.compare(a, b)
    assert result.routing_accuracy_delta is None
    assert result.latency_p95_delta_ms is None
    assert result.total_cost_usd_delta is None


def test_compare_never_assigns_subjective_labels():
    a = _summary("eval-a")
    b = _summary("eval-b")
    result = metrics.compare(a, b)
    dumped = str(result.model_dump())
    for banned in ("better", "worse", "best", "excellent", "poor"):
        assert banned not in dumped.lower()
