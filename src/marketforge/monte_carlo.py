from __future__ import annotations

import hashlib
import inspect
import json
import math
import random
from statistics import fmean, median
from typing import Any


def _draw(rng: random.Random, specification: dict[str, Any]) -> float:
    if specification.get("distribution") != "normal":
        raise ValueError("only normal distributions are currently supported")
    value = rng.normalvariate(float(specification["mean"]), float(specification["std"]))
    return max(float(specification["min"]), min(float(specification["max"]), value))


def _percentile(sorted_values: list[float], probability: float) -> float:
    position = (len(sorted_values) - 1) * probability
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def _one_dcf_value(assumptions: dict[str, Any], rng: random.Random) -> float:
    base_fcf = float(assumptions["base_fcf"])
    base_margin = float(assumptions["fcf_margin"]["mean"])
    growth = _draw(rng, assumptions["revenue_growth"])
    margin = _draw(rng, assumptions["fcf_margin"])
    wacc = _draw(rng, assumptions["wacc"])
    terminal_growth = _draw(rng, assumptions["terminal_growth"])
    if wacc <= terminal_growth:
        raise ValueError("WACC must be greater than terminal growth in every simulation")

    years = int(assumptions["forecast_years"])
    free_cash_flow = base_fcf * (margin / base_margin)
    enterprise_value = 0.0
    for year in range(1, years + 1):
        free_cash_flow *= 1 + growth
        enterprise_value += free_cash_flow / ((1 + wacc) ** year)

    terminal_value = free_cash_flow * (1 + terminal_growth) / (wacc - terminal_growth)
    enterprise_value += terminal_value / ((1 + wacc) ** years)
    equity_value = enterprise_value - float(assumptions["net_debt"])
    return equity_value / float(assumptions["shares_outstanding"])


def run_dcf_simulation(
    assumptions: dict[str, Any], *, iterations: int = 10_000, seed: int = 0
) -> dict[str, Any]:
    """Run an auditable DCF simulation with deterministic seed and result hashes."""

    if iterations < 10_000:
        raise ValueError("Monte Carlo simulation requires at least 10000 iterations")
    if seed < 0:
        raise ValueError("seed must be non-negative")

    if float(assumptions["wacc"]["min"]) <= float(assumptions["terminal_growth"]["max"]):
        raise ValueError("WACC minimum must exceed terminal growth maximum")

    rng = random.Random(seed)
    values = sorted(_one_dcf_value(assumptions, rng) for _ in range(iterations))
    summary = {
        "model_version": "dcf-mc-v1",
        "seed": seed,
        "iterations": iterations,
        "mean": fmean(values),
        "median": median(values),
        "p05": _percentile(values, 0.05),
        "p95": _percentile(values, 0.95),
        "minimum": values[0],
        "maximum": values[-1],
    }
    canonical = json.dumps(summary, sort_keys=True, separators=(",", ":")).encode("utf-8")
    summary["result_sha256"] = hashlib.sha256(canonical).hexdigest()
    summary["code_sha256"] = hashlib.sha256(inspect.getsource(run_dcf_simulation).encode("utf-8")).hexdigest()
    return summary
