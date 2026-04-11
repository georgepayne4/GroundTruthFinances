"""Tests for Monte Carlo investment simulation (v8.1)."""

from __future__ import annotations

import time

import numpy as np
import pytest

from engine.monte_carlo import (
    probability_of_meeting_target,
    run_pension_simulation,
    run_simulation,
)

# ---------------------------------------------------------------------------
# run_simulation
# ---------------------------------------------------------------------------

class TestRunSimulation:
    def test_zero_volatility_matches_deterministic(self):
        """With zero volatility, MC should degenerate to compound growth."""
        from engine.investments import _future_value

        pv, mc, ret, yrs = 10000, 200, 0.06, 20
        deterministic = _future_value(pv, mc, ret, yrs)

        result = run_simulation(
            present_value=pv, monthly_contribution=mc,
            annual_return=ret, annual_volatility=0.0,
            years=yrs, inflation=0.0, num_simulations=100,
            random_seed=42,
        )
        median = result["terminal_nominal"]["median"]
        assert abs(median - deterministic) / deterministic < 0.01

    def test_reproducibility_with_seed(self):
        kwargs = dict(
            present_value=10000, monthly_contribution=200,
            annual_return=0.06, annual_volatility=0.10,
            years=10, inflation=0.03, num_simulations=500,
            random_seed=123,
        )
        r1 = run_simulation(**kwargs)
        r2 = run_simulation(**kwargs)
        assert r1["terminal_nominal"]["median"] == r2["terminal_nominal"]["median"]

    def test_different_seeds_differ(self):
        kwargs = dict(
            present_value=10000, monthly_contribution=200,
            annual_return=0.06, annual_volatility=0.10,
            years=10, inflation=0.03, num_simulations=500,
        )
        r1 = run_simulation(**kwargs, random_seed=1)
        r2 = run_simulation(**kwargs, random_seed=2)
        assert r1["terminal_nominal"]["median"] != r2["terminal_nominal"]["median"]

    def test_median_approximates_expected_value(self):
        """Median of lognormal should be close to E[X] * exp(-0.5*var*T)."""
        result = run_simulation(
            present_value=50000, monthly_contribution=0,
            annual_return=0.07, annual_volatility=0.12,
            years=30, inflation=0.0, num_simulations=5000,
            random_seed=99,
        )
        # For lognormal, median = PV * exp(mu*T) where mu = r - 0.5*sigma^2
        expected_median = 50000 * np.exp((0.07 - 0.5 * 0.12**2) * 30)
        actual_median = result["terminal_nominal"]["median"]
        assert abs(actual_median - expected_median) / expected_median < 0.05

    def test_higher_volatility_wider_spread(self):
        base = dict(
            present_value=10000, monthly_contribution=100,
            annual_return=0.06, years=15, inflation=0.03,
            num_simulations=2000, random_seed=42,
        )
        low_vol = run_simulation(**base, annual_volatility=0.05)
        high_vol = run_simulation(**base, annual_volatility=0.20)
        low_spread = low_vol["terminal_real"]["p90"] - low_vol["terminal_real"]["p10"]
        high_spread = high_vol["terminal_real"]["p90"] - high_vol["terminal_real"]["p10"]
        assert high_spread > low_spread

    def test_percentile_ordering(self):
        result = run_simulation(
            present_value=10000, monthly_contribution=200,
            annual_return=0.06, annual_volatility=0.10,
            years=20, inflation=0.03, num_simulations=1000,
            random_seed=42,
        )
        tr = result["terminal_real"]
        assert tr["p10"] <= tr["p25"] <= tr["p50"] <= tr["p75"] <= tr["p90"]

    def test_all_terminal_values_non_negative(self):
        """Lognormal returns cannot produce negative wealth (with positive contributions)."""
        result = run_simulation(
            present_value=1000, monthly_contribution=50,
            annual_return=0.04, annual_volatility=0.15,
            years=30, inflation=0.02, num_simulations=1000,
            random_seed=42,
        )
        assert result["terminal_real"]["p10"] >= 0

    def test_output_structure(self):
        result = run_simulation(
            present_value=10000, monthly_contribution=100,
            annual_return=0.06, annual_volatility=0.10,
            years=10, inflation=0.03, num_simulations=100,
            random_seed=42,
        )
        assert "num_simulations" in result
        assert "years" in result
        assert "terminal_nominal" in result
        assert "terminal_real" in result
        assert "percentile_paths" in result
        assert "mean" in result["terminal_nominal"]
        assert "median" in result["terminal_nominal"]
        assert "p50" in result["terminal_nominal"]

    def test_zero_balance_contributions_only(self):
        result = run_simulation(
            present_value=0, monthly_contribution=500,
            annual_return=0.06, annual_volatility=0.10,
            years=20, inflation=0.03, num_simulations=500,
            random_seed=42,
        )
        assert result["terminal_nominal"]["median"] > 0

    def test_lump_sum_no_contributions(self):
        result = run_simulation(
            present_value=100000, monthly_contribution=0,
            annual_return=0.06, annual_volatility=0.10,
            years=10, inflation=0.03, num_simulations=500,
            random_seed=42,
        )
        assert result["terminal_nominal"]["median"] > 100000

    def test_annual_paths_length(self):
        years = 15
        result = run_simulation(
            present_value=10000, monthly_contribution=100,
            annual_return=0.06, annual_volatility=0.10,
            years=years, inflation=0.03, num_simulations=100,
            random_seed=42,
        )
        for _key, path in result["percentile_paths"].items():
            assert len(path) == years + 1

    def test_zero_years_returns_present_value(self):
        result = run_simulation(
            present_value=5000, monthly_contribution=100,
            annual_return=0.06, annual_volatility=0.10,
            years=0, inflation=0.03, num_simulations=100,
        )
        assert result["terminal_nominal"]["median"] == 5000
        assert result["num_simulations"] == 0


# ---------------------------------------------------------------------------
# probability_of_meeting_target
# ---------------------------------------------------------------------------

class TestProbabilityOfMeetingTarget:
    def test_low_target_high_probability(self):
        values = np.array([100, 200, 300, 400, 500])
        assert probability_of_meeting_target(values, 50) == 1.0

    def test_impossible_target_zero_probability(self):
        values = np.array([100, 200, 300])
        assert probability_of_meeting_target(values, 999999) == 0.0

    def test_returns_float_in_range(self):
        values = np.array([100, 200, 300, 400, 500])
        prob = probability_of_meeting_target(values, 250)
        assert 0.0 <= prob <= 1.0

    def test_exact_target(self):
        values = np.array([100, 200, 300])
        assert probability_of_meeting_target(values, 200) == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# run_pension_simulation
# ---------------------------------------------------------------------------

class TestRunPensionSimulation:
    def _mc_cfg(self, seed=42):
        return {
            "num_simulations": 500,
            "percentiles": [10, 25, 50, 75, 90],
            "random_seed": seed,
        }

    def test_returns_narrative(self):
        result = run_pension_simulation(
            pension_balance=50000, monthly_contribution=500,
            annual_return=0.06, annual_volatility=0.10,
            years_to_retirement=30, inflation=0.03,
            safe_withdrawal_rate=0.04, target_income=30000,
            state_pension_real=11500, mc_cfg=self._mc_cfg(),
        )
        assert "narrative" in result
        assert "%" in result["narrative"]
        assert len(result["narrative"]) > 20

    def test_pension_pot_percentiles_ordered(self):
        result = run_pension_simulation(
            pension_balance=50000, monthly_contribution=500,
            annual_return=0.06, annual_volatility=0.10,
            years_to_retirement=30, inflation=0.03,
            safe_withdrawal_rate=0.04, target_income=30000,
            state_pension_real=11500, mc_cfg=self._mc_cfg(),
        )
        pcts = result["pension_pot_percentiles"]
        assert pcts["p10"] <= pcts["p25"] <= pcts["p50"] <= pcts["p75"] <= pcts["p90"]

    def test_probability_of_target_reasonable(self):
        result = run_pension_simulation(
            pension_balance=50000, monthly_contribution=500,
            annual_return=0.06, annual_volatility=0.10,
            years_to_retirement=30, inflation=0.03,
            safe_withdrawal_rate=0.04, target_income=30000,
            state_pension_real=11500, mc_cfg=self._mc_cfg(),
        )
        prob = result["probability_of_target_pct"]
        assert 0 <= prob <= 100

    def test_with_real_assumptions(self):
        """Integration: loads assumptions.yaml and runs MC."""
        from pathlib import Path

        from engine.loader import load_assumptions

        assumptions = load_assumptions(
            Path(__file__).resolve().parent.parent / "config" / "assumptions.yaml"
        )
        mc_cfg = assumptions.get("monte_carlo", {})
        if not mc_cfg:
            pytest.skip("monte_carlo not in assumptions.yaml")

        mc_cfg["random_seed"] = 42
        mc_cfg["num_simulations"] = 200

        result = run_pension_simulation(
            pension_balance=30000, monthly_contribution=400,
            annual_return=0.06, annual_volatility=0.10,
            years_to_retirement=35, inflation=0.03,
            safe_withdrawal_rate=0.04, target_income=30000,
            state_pension_real=11500, mc_cfg=mc_cfg,
        )
        assert result["num_simulations"] == 200
        assert "pension_pot_percentiles" in result

    def test_zero_years_returns_degenerate(self):
        result = run_pension_simulation(
            pension_balance=100000, monthly_contribution=500,
            annual_return=0.06, annual_volatility=0.10,
            years_to_retirement=0, inflation=0.03,
            safe_withdrawal_rate=0.04, target_income=30000,
            state_pension_real=11500, mc_cfg=self._mc_cfg(),
        )
        assert result["num_simulations"] == 0


# ---------------------------------------------------------------------------
# Performance
# ---------------------------------------------------------------------------

class TestPerformance:
    def test_1000_sims_under_200ms(self):
        start = time.perf_counter()
        run_simulation(
            present_value=50000, monthly_contribution=500,
            annual_return=0.06, annual_volatility=0.12,
            years=37, inflation=0.03, num_simulations=1000,
            random_seed=42,
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 0.200

    def test_10000_sims_under_1s(self):
        start = time.perf_counter()
        run_simulation(
            present_value=50000, monthly_contribution=500,
            annual_return=0.06, annual_volatility=0.12,
            years=37, inflation=0.03, num_simulations=10000,
            random_seed=42,
        )
        elapsed = time.perf_counter() - start
        assert elapsed < 1.0
