"""The NEXUS evaluation runner (Phase 4).

    Evaluation Dataset -> Evaluation Runner -> NexusRuntime -> Agent
    Execution -> Structured Run Data -> Evaluators -> Evaluation Result
    -> Metrics / Comparison

This module operates only against `NexusRuntime`'s public interface
(`execute`/`get_state`, via `run_store.execute_and_record`) -- it knows
nothing about LangGraph nodes, `main.py`, or the API layer. Whether the
runtime passed in is the real one (a live LLM provider, via
`evals/run.py`) or a fully deterministic fake (as in the test suite) is
invisible to this module; that's the whole point of depending only on
`NexusRuntime`'s interface.

Terminology (see README "Evaluation" / ARCHITECTURE.md for the fuller
version): a "run" is one execution of one case. Calling `run_evaluation`
again with a NEW `evaluation_id` (the default, unless one is explicitly
reused) is a "re-run" of the same cases against fresh, isolated threads --
NOT a deterministic replay. A true replay would require recording and
substituting the exact model/tool inputs and outputs, which this phase
does not implement -- see `rerun_case` below and README "Known limitations".
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

import access
import run_store
from . import cases as case_evaluators
from . import metrics as metrics_module
from .models import EvaluationCase, EvaluationDataset, EvaluationResult, EvaluationRun

if TYPE_CHECKING:
    from runtime import NexusRuntime

# A fourth development principal, alongside the CLI/API/... ones in
# access.py -- see that module's docstring. Still not authentication.
EVAL_PRINCIPAL_ID = access.LOCAL_EVAL_PRINCIPAL


def eval_thread_id(evaluation_id: str, case_id: str) -> str:
    """Deterministic, immediately-recognizable thread id for one case
    within one evaluation run -- never a random UUID. This is how
    evaluation traffic stays visually distinguishable from, and isolated
    from, normal CLI/API sessions (which use `thread-<random>` ids)."""
    return f"eval-{evaluation_id}-{case_id}"


async def run_case(
    runtime: "NexusRuntime",
    evaluation_id: str,
    case: EvaluationCase,
    store: run_store.RunStore,
    pricing_table: dict | None = None,
    *,
    principal_id: str = EVAL_PRINCIPAL_ID,
) -> EvaluationResult:
    """Execute one case on its own isolated evaluation thread and evaluate
    the result. Exposed separately from `run_evaluation` so a caller (or a
    future `evals eval rerun` command) can re-execute a single case.

    `principal_id` defaults to the standalone evaluation CLI's principal
    (`evals/run.py`) but callers that already have their own identity in
    NEXUS's access model -- e.g. `api.py`'s evaluation endpoints -- should
    pass their own, so a later `GET /v1/runs/{request_id}` lookup (checked
    against that same principal) succeeds instead of being denied for
    belonging to a thread a different principal owns. See access.py.
    """
    thread_id = eval_thread_id(evaluation_id, case.id)
    record = await run_store.execute_and_record(
        runtime,
        thread_id,
        case.input,
        principal_id=principal_id,
        store=store,
        pricing_table=pricing_table,
    )
    return case_evaluators.evaluate_case(case, record)


async def run_evaluation(
    runtime: "NexusRuntime",
    dataset: EvaluationDataset,
    store: run_store.RunStore,
    *,
    evaluation_id: str | None = None,
    pricing_table: dict | None = None,
    principal_id: str = EVAL_PRINCIPAL_ID,
) -> EvaluationRun:
    """Run every case in `dataset` against `runtime`, each on its own
    isolated thread, and return the full evaluation record (summary + all
    per-case results).

    `evaluation_id` defaults to a fresh random id, which is what gives two
    separate calls to `run_evaluation` (even with the identical dataset)
    fully isolated threads -- see `eval_thread_id`. Pass the same
    `evaluation_id` back in deliberately if you want a "re-run" to reuse
    the same threads (continuing prior conversation state rather than
    starting fresh); that is still not deterministic replay -- see the
    module docstring. See `run_case` for `principal_id`.
    """
    evaluation_id = evaluation_id or uuid.uuid4().hex[:12]
    results: list[EvaluationResult] = [
        await run_case(runtime, evaluation_id, case, store, pricing_table, principal_id=principal_id)
        for case in dataset.cases
    ]
    summary = metrics_module.summarize(dataset, results, evaluation_id=evaluation_id)
    return EvaluationRun(evaluation_id=evaluation_id, summary=summary, results=results)


async def rerun_case(
    runtime: "NexusRuntime",
    case: EvaluationCase,
    store: run_store.RunStore,
    *,
    evaluation_id: str | None = None,
    pricing_table: dict | None = None,
    principal_id: str = EVAL_PRINCIPAL_ID,
) -> EvaluationResult:
    """Execute `case`'s input again as an independent, fresh execution --
    a "re-run," not a replay (see module docstring). A fresh
    `evaluation_id` is generated by default, so this gets its own isolated
    thread rather than continuing any prior conversation. NEXUS does not
    record or substitute model/tool inputs and outputs, so this will call
    the real provider/tools again if `runtime` is live -- it is not free
    and not guaranteed to produce an identical result.
    """
    evaluation_id = evaluation_id or uuid.uuid4().hex[:12]
    return await run_case(runtime, evaluation_id, case, store, pricing_table, principal_id=principal_id)
