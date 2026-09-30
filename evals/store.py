"""Bounded, in-process storage for completed evaluation runs (Phase 4).

Same pattern as `run_store.RunStore`: an in-memory, capped, oldest-evicted
registry -- NOT a database, NOT durable across restarts. Used by the API's
evaluation endpoints (`api.py`) so `GET /v1/evaluations/{evaluation_id}`
and friends can look up a previously-run evaluation. A future persistent
backend could replace this without changing the API contract, since it
only reads/writes `EvaluationRun` objects through `record`/`get`.
"""

from __future__ import annotations

import os
from collections import OrderedDict

from .models import EvaluationRun

DEFAULT_MAX_SIZE = int(os.getenv("NEXUS_EVALUATION_STORE_SIZE", "100"))


class EvaluationStore:
    def __init__(self, max_size: int = DEFAULT_MAX_SIZE):
        self._max_size = max_size
        self._runs: OrderedDict[str, EvaluationRun] = OrderedDict()

    def record(self, run: EvaluationRun) -> None:
        self._runs[run.evaluation_id] = run
        self._runs.move_to_end(run.evaluation_id)
        while len(self._runs) > self._max_size:
            self._runs.popitem(last=False)

    def get(self, evaluation_id: str) -> EvaluationRun | None:
        return self._runs.get(evaluation_id)

    def list_recent(self) -> list[EvaluationRun]:
        """Return the bounded history, newest recorded evaluation first."""
        return list(reversed(self._runs.values()))
