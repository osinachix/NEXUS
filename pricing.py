"""Configurable model pricing for NEXUS cost tracking (Phase 4).

NEXUS never invents prices. There is no built-in price list for any
model -- pricing changes over time and by provider agreement, and a wrong
hardcoded number would be worse than none. Cost is only ever calculated
when BOTH of these are true:

1. The provider actually returned token usage for a call (see
   `observability.extract_usage` -- never fabricated).
2. An operator has explicitly configured pricing for the model in use, via
   `NEXUS_PRICING_FILE` (a path to a small JSON file) or a pricing dict
   passed in directly.

If either is missing, cost is `None` -- never an estimate presented as if
it were a real provider-reported cost. See `run_store.py`, which is the
only other module that calls into this one.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, Field


class ModelPricing(BaseModel):
    """Cost per 1,000,000 tokens, in USD, for one model. Whatever currency/
    unit an operator's pricing file uses is on them to keep consistent;
    NEXUS just multiplies."""

    input_cost_per_1m_tokens: float = Field(..., ge=0)
    output_cost_per_1m_tokens: float = Field(..., ge=0)


PricingTable = dict[str, ModelPricing]


def load_pricing_config(path: str | os.PathLike[str] | None = None) -> PricingTable:
    """Load a pricing table from a JSON file shaped like:

        {
          "anthropic:claude-3-5-sonnet-20241022": {
            "input_cost_per_1m_tokens": 3.00,
            "output_cost_per_1m_tokens": 15.00
          }
        }

    `path` defaults to the `NEXUS_PRICING_FILE` env var. Returns an empty
    table (meaning: cost is always unavailable) if no path is configured or
    the file doesn't exist -- this is the expected, documented default, not
    an error.
    """
    resolved = path if path is not None else os.getenv("NEXUS_PRICING_FILE")
    if not resolved:
        return {}
    file_path = Path(resolved)
    if not file_path.exists():
        return {}
    raw = json.loads(file_path.read_text(encoding="utf-8"))
    return {model: ModelPricing.model_validate(entry) for model, entry in raw.items()}


def calculate_cost_usd(
    *,
    model_name: str | None,
    input_tokens: int | None,
    output_tokens: int | None,
    pricing: PricingTable,
) -> float | None:
    """Cost in USD for one run, or None if usage or pricing is unavailable.

    Deliberately conservative: any missing piece (no model name, no token
    counts, no configured price for that exact model name) yields None
    rather than a partial/estimated figure.
    """
    if not model_name or input_tokens is None or output_tokens is None:
        return None
    model_pricing = pricing.get(model_name)
    if model_pricing is None:
        return None
    return (
        input_tokens / 1_000_000 * model_pricing.input_cost_per_1m_tokens
        + output_tokens / 1_000_000 * model_pricing.output_cost_per_1m_tokens
    )
