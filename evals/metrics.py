"""Aggregation and comparison for NEXUS evaluation results (Phase 4).

Latency percentiles use linear interpolation between closest ranks (the
same method NumPy's default `percentile` uses) -- deterministic, and exact
for the small local datasets this framework targets. Token/cost totals are
`None` whenever no run in the set carried that data; they are never
partially estimated or defaulted to 0 (a 0 would falsely claim "zero cost,"
not "unknown cost").
"""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from .models import (
    ComparisonResult,
    DimensionResult,
    EvaluationDataset,
    EvaluationResult,
    EvaluationSummary,
    RunMetrics,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Linear-interpolation percentile of an already-sorted list. `pct` in
    [0, 100]. Requires a non-empty list."""
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * (pct / 100)
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return sorted_values[int(rank)]
    lower_value = sorted_values[int(lower)] * (upper - rank)
    upper_value = sorted_values[int(upper)] * (rank - lower)
    return lower_value + upper_value


def _dimension_pass_rate(results: list[EvaluationResult], dimension: str) -> float | None:
    matching: list[DimensionResult] = [
        d for result in results for d in result.dimensions if d.dimension == dimension
    ]
    if not matching:
        return None
    return sum(1 for d in matching if d.passed) / len(matching)


def aggregate_metrics(results: list[EvaluationResult]) -> RunMetrics:
    """Latency/token/cost metrics aggregated across a set of evaluation
    results. Never fabricates a value: a metric with no underlying data
    across every run in `results` comes back `None`."""
    if not results:
        return RunMetrics(count=0)

    durations = sorted(result.run.duration_ms for result in results)

    usages = [result.run.usage for result in results if result.run.usage is not None]
    total_input = sum(u.input_tokens for u in usages if u.input_tokens is not None) if usages else None
    total_output = sum(u.output_tokens for u in usages if u.output_tokens is not None) if usages else None
    total_tokens = sum(u.total_tokens for u in usages if u.total_tokens is not None) if usages else None

    costs = [result.run.cost_usd for result in results if result.run.cost_usd is not None]
    total_cost = sum(costs) if costs else None

    return RunMetrics(
        count=len(results),
        latency_min_ms=durations[0],
        latency_max_ms=durations[-1],
        latency_mean_ms=sum(durations) / len(durations),
        latency_p50_ms=_percentile(durations, 50),
        latency_p95_ms=_percentile(durations, 95),
        latency_p99_ms=_percentile(durations, 99),
        total_input_tokens=total_input,
        total_output_tokens=total_output,
        total_tokens=total_tokens,
        total_cost_usd=total_cost,
    )


def summarize(
    dataset: EvaluationDataset, results: list[EvaluationResult], evaluation_id: str | None = None
) -> EvaluationSummary:
    evaluation_id = evaluation_id or uuid.uuid4().hex[:12]
    total = len(results)
    passed = sum(1 for result in results if result.passed)
    execution_rate = _dimension_pass_rate(results, "execution")
    return EvaluationSummary(
        evaluation_id=evaluation_id,
        dataset_name=dataset.name,
        dataset_version=dataset.version,
        created_at=_now_iso(),
        total_cases=total,
        passed_cases=passed,
        failed_cases=total - passed,
        routing_accuracy=_dimension_pass_rate(results, "routing"),
        execution_success_rate=execution_rate if execution_rate is not None else 0.0,
        tool_success_rate=_dimension_pass_rate(results, "tools"),
        metrics=aggregate_metrics(results),
    )


def _delta(a: float | None, b: float | None) -> float | None:
    """b - a, or None if either side is unavailable -- a missing metric on
    either evaluation makes the delta itself unavailable, not zero."""
    if a is None or b is None:
        return None
    return b - a


def compare(summary_a: EvaluationSummary, summary_b: EvaluationSummary) -> ComparisonResult:
    """A measurable diff between two evaluation summaries. No subjective
    labels -- see ComparisonResult's docstring for how to read the signs.
    """
    return ComparisonResult(
        evaluation_id_a=summary_a.evaluation_id,
        evaluation_id_b=summary_b.evaluation_id,
        summary_a=summary_a,
        summary_b=summary_b,
        total_cases_a=summary_a.total_cases,
        total_cases_b=summary_b.total_cases,
        passed_cases_delta=summary_b.passed_cases - summary_a.passed_cases,
        routing_accuracy_delta=_delta(summary_a.routing_accuracy, summary_b.routing_accuracy),
        execution_success_rate_delta=_delta(summary_a.execution_success_rate, summary_b.execution_success_rate),
        tool_success_rate_delta=_delta(summary_a.tool_success_rate, summary_b.tool_success_rate),
        latency_p50_delta_ms=_delta(summary_a.metrics.latency_p50_ms, summary_b.metrics.latency_p50_ms),
        latency_p95_delta_ms=_delta(summary_a.metrics.latency_p95_ms, summary_b.metrics.latency_p95_ms),
        latency_p99_delta_ms=_delta(summary_a.metrics.latency_p99_ms, summary_b.metrics.latency_p99_ms),
        total_cost_usd_delta=_delta(summary_a.metrics.total_cost_usd, summary_b.metrics.total_cost_usd),
    )
