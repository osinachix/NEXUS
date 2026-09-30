"""Live evaluation entrypoint: `python -m evals.run` (or `python -m evals`).

Runs the deterministic evaluation framework against a REAL NexusRuntime --
a real LLM provider call for every case, and, for cases that route to the
logical agent, potentially a real outbound HTTPS fetch (still subject to
Phase 2's full security policy). This is explicitly separate from the
pytest suite (tests/test_eval_*.py), which never imports this module and
always uses a fake/stub runtime -- CI and `pytest` never require a
provider credential because of this separation.

Requires a working `ANTHROPIC_API_KEY` (see README "Setup") -- there is no
separate flag to "enable" live mode beyond having real credentials
configured, since that's the same requirement the CLI/API already have.
Never prints or logs the key itself.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

import main
import pricing as pricing_module
import run_store
import runtime as nexus_runtime
from evals import dataset as dataset_module
from evals import evaluator
from evals.models import EvaluationSummary


def _print_summary(summary: EvaluationSummary) -> None:
    print(f"\nEvaluation {summary.evaluation_id}  (dataset: {summary.dataset_name} v{summary.dataset_version})")
    print(f"  cases:              {summary.total_cases}")
    print(f"  passed:             {summary.passed_cases}")
    print(f"  failed:             {summary.failed_cases}")
    print(f"  routing accuracy:   {_fmt(summary.routing_accuracy)}")
    print(f"  execution success:  {_fmt(summary.execution_success_rate)}")
    print(f"  tool success:       {_fmt(summary.tool_success_rate)}")
    metrics = summary.metrics
    print(f"  latency p50/p95/p99 (ms): {_fmt_ms(metrics.latency_p50_ms)} / "
          f"{_fmt_ms(metrics.latency_p95_ms)} / {_fmt_ms(metrics.latency_p99_ms)}")
    print(f"  total tokens:       {metrics.total_tokens if metrics.total_tokens is not None else 'unavailable'}")
    print(f"  total cost (USD):   {_fmt_cost(metrics.total_cost_usd)}")


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _fmt_ms(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1f}"


def _fmt_cost(value: float | None) -> str:
    return "unavailable (no pricing configured)" if value is None else f"${value:.4f}"


async def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m evals.run", description="Run a NEXUS evaluation dataset against a LIVE runtime."
    )
    parser.add_argument("--dataset", default=str(dataset_module.DEFAULT_DATASET_PATH), help="Path to an evaluation dataset JSON file.")
    parser.add_argument(
        "--checkpoint-db",
        default=":memory:",
        help="SQLite path for evaluation thread state. Defaults to ':memory:' so live evaluation runs "
        "never touch (or pollute) the normal NEXUS_CHECKPOINT_DB used by the CLI/API.",
    )
    args = parser.parse_args(argv)

    print("Running LIVE NEXUS evaluation. This calls the configured LLM provider for every case.")
    try:
        ds = dataset_module.load_dataset(args.dataset)
    except dataset_module.DatasetError as exc:
        print(f"Dataset error: {exc}", file=sys.stderr)
        return 2
    print(f"Loaded dataset {ds.name!r} v{ds.version} ({len(ds.cases)} cases) from {args.dataset}")

    main.logical_react_agent = main.build_logical_agent()
    pricing_table = pricing_module.load_pricing_config()
    if not pricing_table:
        print("No NEXUS_PRICING_FILE configured -- cost will be reported as unavailable, not estimated.")

    async with nexus_runtime.create_runtime(main.graph_builder, checkpoint_db=args.checkpoint_db) as runtime:
        store = run_store.RunStore()
        result = await evaluator.run_evaluation(runtime, ds, store, pricing_table=pricing_table)

    _print_summary(result.summary)
    for case_result in result.results:
        if not case_result.passed:
            failed_dims = ", ".join(d.dimension for d in case_result.dimensions if not d.passed)
            print(f"  FAILED: {case_result.case_id} ({failed_dims})")

    return 0 if result.summary.failed_cases == 0 else 1


def main_cli() -> None:
    sys.exit(asyncio.run(_main()))


if __name__ == "__main__":
    main_cli()
