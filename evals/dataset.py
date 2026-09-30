"""Loading and validating NEXUS evaluation datasets (Phase 4).

Datasets are small, checked-in JSON files (see evals/datasets/baseline.json)
-- easy to inspect by hand and, eventually, to edit from the future NEXUS
Console (not built yet). This module only loads and validates; it knows
nothing about running or evaluating cases.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from .models import EvaluationDataset

DEFAULT_DATASET_PATH = Path(__file__).parent / "datasets" / "baseline.json"


class DatasetError(ValueError):
    """A dataset file was missing, malformed, or otherwise invalid."""


def load_dataset(path: str | Path = DEFAULT_DATASET_PATH) -> EvaluationDataset:
    """Load and validate an evaluation dataset from a JSON file.

    Raises `DatasetError` for a missing file, malformed JSON, a JSON shape
    that doesn't match `EvaluationDataset`/`EvaluationCase`, or duplicate
    case ids within the dataset (each case id must be unique so results and
    thread ids stay unambiguous -- see `evals.evaluator.eval_thread_id`).
    """
    file_path = Path(path)
    if not file_path.exists():
        raise DatasetError(f"dataset file not found: {file_path}")

    try:
        raw = json.loads(file_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DatasetError(f"malformed JSON in dataset {file_path}: {exc}") from exc

    try:
        dataset = EvaluationDataset.model_validate(raw)
    except ValidationError as exc:
        raise DatasetError(f"invalid dataset shape in {file_path}: {exc}") from exc

    ids = [case.id for case in dataset.cases]
    duplicates = sorted({case_id for case_id in ids if ids.count(case_id) > 1})
    if duplicates:
        raise DatasetError(f"duplicate case ids in dataset {file_path}: {duplicates}")

    return dataset
