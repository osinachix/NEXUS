"""Evaluation dataset loading and validation (Phase 4)."""

import json

import pytest

from evals import dataset


def test_baseline_dataset_loads():
    ds = dataset.load_dataset()
    assert ds.name == "baseline"
    assert ds.version
    assert len(ds.cases) >= 4  # emotional, logical, math, coding all covered


def test_baseline_dataset_covers_all_four_routes():
    ds = dataset.load_dataset()
    routes = {case.expected_route for case in ds.cases if case.expected_route is not None}
    assert routes == {"counselor", "logical", "math", "coding"}


def test_missing_file_is_a_dataset_error(tmp_path):
    with pytest.raises(dataset.DatasetError):
        dataset.load_dataset(tmp_path / "does-not-exist.json")


def test_malformed_json_is_a_dataset_error(tmp_path):
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(dataset.DatasetError):
        dataset.load_dataset(bad_file)


def test_wrong_shape_is_a_dataset_error(tmp_path):
    bad_file = tmp_path / "wrong_shape.json"
    bad_file.write_text(json.dumps({"totally": "wrong"}), encoding="utf-8")
    with pytest.raises(dataset.DatasetError):
        dataset.load_dataset(bad_file)


def test_duplicate_case_ids_are_rejected(tmp_path):
    payload = {
        "name": "dupes",
        "version": "1.0.0",
        "cases": [
            {"id": "case-1", "name": "A", "input": "hi"},
            {"id": "case-1", "name": "B", "input": "hello"},
        ],
    }
    bad_file = tmp_path / "dupes.json"
    bad_file.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(dataset.DatasetError, match="duplicate"):
        dataset.load_dataset(bad_file)


def test_a_case_with_only_expected_route_is_valid(tmp_path):
    # Cases don't need every field -- routing-only evaluation must work.
    payload = {
        "name": "minimal",
        "version": "1.0.0",
        "cases": [{"id": "case-1", "name": "Minimal", "input": "hi", "expected_route": "math"}],
    }
    file_path = tmp_path / "minimal.json"
    file_path.write_text(json.dumps(payload), encoding="utf-8")
    ds = dataset.load_dataset(file_path)
    case = ds.cases[0]
    assert case.expected_route == "math"
    assert case.expected_tools == []
    assert case.forbidden_tools == []
    assert case.response_contains == []
    assert case.max_latency_ms is None
