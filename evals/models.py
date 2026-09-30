"""Typed models for the NEXUS evaluation framework (Phase 4).

Kept separate from LangGraph nodes, API routing, CLI presentation, and
provider-specific code (`main.py`) on purpose -- this package only knows
about `NexusRuntime`'s public interface (`execute`/`get_state`, via
`run_store.execute_and_record`) and `run_store.RunRecord`, the same
structured run data the API's `GET /v1/runs/{request_id}` exposes.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

import run_store

RouteName = Literal["counselor", "logical", "math", "coding"]


class EvaluationCase(BaseModel):
    """One evaluation case. Only `id`, `name`, and `input` are required --
    every check is optional, so a case can evaluate routing alone, or
    routing plus tool usage plus response content, etc. See
    `evals/datasets/baseline.json` for real examples.
    """

    id: str
    name: str
    input: str
    expected_route: RouteName | None = None
    expected_tools: list[str] = Field(default_factory=list)
    forbidden_tools: list[str] = Field(default_factory=list)
    response_contains: list[str] = Field(default_factory=list)
    response_not_contains: list[str] = Field(default_factory=list)
    max_latency_ms: float | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class EvaluationDataset(BaseModel):
    name: str
    version: str
    description: str = ""
    cases: list[EvaluationCase]


class DimensionResult(BaseModel):
    """The outcome of one check (one dimension) for one case. A case
    produces one or more of these; `EvaluationResult.passed` is the AND of
    all of them for that case."""

    dimension: Literal["routing", "execution", "tools", "response", "latency"]
    passed: bool
    detail: str = ""


class EvaluationResult(BaseModel):
    case_id: str
    case_name: str
    request_id: str
    thread_id: str
    passed: bool
    dimensions: list[DimensionResult]
    run: run_store.RunRecord = Field(
        ..., description="The full structured run data this result was evaluated against."
    )


class RunMetrics(BaseModel):
    """Aggregate latency/token/cost metrics over a set of evaluation
    results. Every field is `None` when the underlying data wasn't
    available for any run in the set -- never a fabricated 0 or estimate.
    """

    count: int
    latency_min_ms: float | None = None
    latency_max_ms: float | None = None
    latency_mean_ms: float | None = None
    latency_p50_ms: float | None = None
    latency_p95_ms: float | None = None
    latency_p99_ms: float | None = None
    total_input_tokens: int | None = None
    total_output_tokens: int | None = None
    total_tokens: int | None = None
    total_cost_usd: float | None = None


class EvaluationSummary(BaseModel):
    evaluation_id: str
    dataset_name: str
    dataset_version: str
    created_at: str
    total_cases: int
    passed_cases: int
    failed_cases: int
    routing_accuracy: float | None = Field(
        None, description="Fraction of cases with an expected_route that routed correctly. Null if no case specified expected_route."
    )
    execution_success_rate: float = Field(
        ..., description="Fraction of cases whose workflow execution completed successfully."
    )
    tool_success_rate: float | None = Field(
        None, description="Fraction of expected_tools/forbidden_tools checks that passed. Null if no case specified either."
    )
    metrics: RunMetrics


class EvaluationListResponse(BaseModel):
    """Lightweight, ownership-filtered view of the bounded EvaluationStore."""

    items: list[EvaluationSummary]
    total: int
    limit: int


class EvaluationRun(BaseModel):
    """The full record of one evaluation execution: summary plus every
    per-case result. What `evals/store.py` keeps, keyed by evaluation_id."""

    evaluation_id: str
    summary: EvaluationSummary
    results: list[EvaluationResult]
    owner_principal_id: str | None = Field(
        None,
        description="The authenticated principal that triggered this evaluation, set by api.py "
        "(Phase 5) so GET /v1/evaluations/* can enforce that a caller only ever retrieves their "
        "own evaluations. Null for evaluations run outside the API (e.g. the standalone "
        "evals/run.py CLI), which has no HTTP caller to attribute ownership to.",
    )


class ComparisonResult(BaseModel):
    """A measurable diff between two evaluation runs. Deliberately no
    subjective labels ("better"/"worse") -- only deltas. `b - a` for every
    field; a positive routing/execution/tool delta means B was higher, a
    positive latency delta means B was SLOWER (higher ms) -- read the sign
    against what the metric means, this does not editorialize which
    direction is desirable.
    """

    evaluation_id_a: str
    evaluation_id_b: str
    summary_a: EvaluationSummary
    summary_b: EvaluationSummary
    total_cases_a: int
    total_cases_b: int
    passed_cases_delta: int
    routing_accuracy_delta: float | None = None
    execution_success_rate_delta: float | None = None
    tool_success_rate_delta: float | None = None
    latency_p50_delta_ms: float | None = None
    latency_p95_delta_ms: float | None = None
    latency_p99_delta_ms: float | None = None
    total_cost_usd_delta: float | None = None
