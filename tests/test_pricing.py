"""Configurable pricing (Phase 4): never invents a price or a cost."""

import json

import pricing


def test_no_configured_file_yields_empty_table(monkeypatch):
    monkeypatch.delenv("NEXUS_PRICING_FILE", raising=False)
    assert pricing.load_pricing_config() == {}


def test_nonexistent_file_yields_empty_table_not_an_error(tmp_path):
    assert pricing.load_pricing_config(tmp_path / "missing.json") == {}


def test_valid_pricing_file_loads(tmp_path):
    file_path = tmp_path / "pricing.json"
    file_path.write_text(
        json.dumps({"model-a": {"input_cost_per_1m_tokens": 3.0, "output_cost_per_1m_tokens": 15.0}}),
        encoding="utf-8",
    )
    table = pricing.load_pricing_config(file_path)
    assert table["model-a"].input_cost_per_1m_tokens == 3.0
    assert table["model-a"].output_cost_per_1m_tokens == 15.0


def test_calculate_cost_requires_usage_and_pricing():
    table = {"model-a": pricing.ModelPricing(input_cost_per_1m_tokens=3.0, output_cost_per_1m_tokens=15.0)}

    # No usage -> None.
    assert pricing.calculate_cost_usd(model_name="model-a", input_tokens=None, output_tokens=None, pricing=table) is None
    # No pricing for this model -> None.
    assert pricing.calculate_cost_usd(model_name="unpriced-model", input_tokens=100, output_tokens=100, pricing=table) is None
    # No model name -> None.
    assert pricing.calculate_cost_usd(model_name=None, input_tokens=100, output_tokens=100, pricing=table) is None
    # Empty pricing table entirely -> None.
    assert pricing.calculate_cost_usd(model_name="model-a", input_tokens=100, output_tokens=100, pricing={}) is None


def test_calculate_cost_is_correct_arithmetic():
    table = {"model-a": pricing.ModelPricing(input_cost_per_1m_tokens=3.0, output_cost_per_1m_tokens=15.0)}
    cost = pricing.calculate_cost_usd(
        model_name="model-a", input_tokens=1_000_000, output_tokens=1_000_000, pricing=table
    )
    assert cost == 18.0


def test_calculate_cost_never_estimates_a_fabricated_number():
    # Even with pricing configured, missing token counts must not silently
    # become 0-cost or any other estimate.
    table = {"model-a": pricing.ModelPricing(input_cost_per_1m_tokens=3.0, output_cost_per_1m_tokens=15.0)}
    cost = pricing.calculate_cost_usd(model_name="model-a", input_tokens=100, output_tokens=None, pricing=table)
    assert cost is None
