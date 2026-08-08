import hashlib

import pytest

from marketforge.monte_carlo import run_dcf_simulation


def assumptions():
    return {
        "base_fcf": 100.0,
        "shares_outstanding": 10.0,
        "net_debt": 0.0,
        "forecast_years": 5,
        "revenue_growth": {"distribution": "normal", "mean": 0.08, "std": 0.02, "min": -0.05, "max": 0.20},
        "fcf_margin": {"distribution": "normal", "mean": 0.20, "std": 0.02, "min": 0.10, "max": 0.30},
        "wacc": {"distribution": "normal", "mean": 0.10, "std": 0.01, "min": 0.07, "max": 0.14},
        "terminal_growth": {"distribution": "normal", "mean": 0.025, "std": 0.005, "min": 0.00, "max": 0.04},
    }


def test_simulation_is_reproducible_for_same_seed():
    first = run_dcf_simulation(assumptions(), iterations=10_000, seed=42)
    second = run_dcf_simulation(assumptions(), iterations=10_000, seed=42)
    assert first == second


def test_simulation_has_auditable_distribution_summary():
    result = run_dcf_simulation(assumptions(), iterations=10_000, seed=7)
    assert result["iterations"] == 10_000
    assert result["seed"] == 7
    assert result["p05"] <= result["median"] <= result["p95"]
    assert result["mean"] > 0
    assert len(result["result_sha256"]) == 64
    assert len(result["code_sha256"]) == 64


def test_simulation_rejects_wacc_not_above_terminal_growth():
    bad = assumptions()
    bad["wacc"] = {"distribution": "normal", "mean": 0.02, "std": 0.0, "min": 0.02, "max": 0.02}
    bad["terminal_growth"] = {
        "distribution": "normal",
        "mean": 0.03,
        "std": 0.0,
        "min": 0.03,
        "max": 0.03,
    }
    with pytest.raises(ValueError, match="WACC"):
        run_dcf_simulation(bad, iterations=10_000, seed=1)


def test_simulation_requires_at_least_10000_iterations():
    with pytest.raises(ValueError, match="10000"):
        run_dcf_simulation(assumptions(), iterations=9999, seed=1)
