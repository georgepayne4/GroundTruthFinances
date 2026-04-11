"""engine/monte_carlo.py — Monte Carlo investment simulation (v8.1).

Pure numpy-vectorized GBM (geometric Brownian motion) simulation for
investment and pension projections. Returns percentile-based outcomes
and probability metrics.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


def run_simulation(
    present_value: float,
    monthly_contribution: float,
    annual_return: float,
    annual_volatility: float,
    years: int,
    inflation: float,
    num_simulations: int = 1000,
    percentiles: list[int] | None = None,
    random_seed: int | None = None,
) -> dict[str, Any]:
    """Run Monte Carlo simulation of portfolio growth using GBM.

    Returns terminal value statistics, real (inflation-adjusted) values,
    and annual percentile paths for charting.
    """
    if years <= 0:
        return _empty_result(present_value, percentiles or [10, 25, 50, 75, 90])

    pctls = percentiles or [10, 25, 50, 75, 90]
    months = years * 12
    rng = np.random.default_rng(random_seed)

    # GBM monthly parameters
    mu_monthly = (annual_return - 0.5 * annual_volatility ** 2) / 12
    sigma_monthly = annual_volatility / np.sqrt(12)

    # Sample log-returns: shape (num_simulations, months)
    log_returns = rng.normal(mu_monthly, sigma_monthly, (num_simulations, months))
    monthly_returns = np.exp(log_returns)

    # Vectorized wealth accumulation
    wealth = np.full(num_simulations, present_value, dtype=np.float64)
    # Store annual snapshots for percentile paths (year 0 = now)
    annual_snapshots = np.empty((num_simulations, years + 1), dtype=np.float64)
    annual_snapshots[:, 0] = present_value

    for m in range(months):
        wealth = wealth * monthly_returns[:, m] + monthly_contribution
        year_idx = (m + 1) // 12
        if (m + 1) % 12 == 0:
            annual_snapshots[:, year_idx] = wealth

    terminal_values = wealth

    # Inflation adjustment
    inflation_factor = (1 + inflation) ** years
    terminal_real = terminal_values / inflation_factor

    # Annual paths in real terms
    annual_paths_real = np.empty_like(annual_snapshots)
    for y in range(years + 1):
        annual_paths_real[:, y] = annual_snapshots[:, y] / ((1 + inflation) ** y)

    # Percentile paths for charting
    percentile_paths = {}
    for p in pctls:
        path = np.percentile(annual_paths_real, p, axis=0)
        percentile_paths[f"p{p}"] = [round(float(v), 2) for v in path]

    # Terminal stats
    result = {
        "num_simulations": num_simulations,
        "years": years,
        "terminal_nominal": {
            "mean": round(float(np.mean(terminal_values)), 2),
            "median": round(float(np.median(terminal_values)), 2),
        },
        "terminal_real": {
            "mean": round(float(np.mean(terminal_real)), 2),
            "median": round(float(np.median(terminal_real)), 2),
        },
        "percentile_paths": percentile_paths,
    }

    for p in pctls:
        result["terminal_nominal"][f"p{p}"] = round(float(np.percentile(terminal_values, p)), 2)
        result["terminal_real"][f"p{p}"] = round(float(np.percentile(terminal_real, p)), 2)

    return result


def probability_of_meeting_target(
    terminal_values: np.ndarray, target: float,
) -> float:
    """Return the probability (0.0–1.0) that terminal values meet or exceed target."""
    return float(np.mean(terminal_values >= target))


def run_pension_simulation(
    pension_balance: float,
    monthly_contribution: float,
    annual_return: float,
    annual_volatility: float,
    years_to_retirement: int,
    inflation: float,
    safe_withdrawal_rate: float,
    target_income: float,
    state_pension_real: float,
    mc_cfg: dict[str, Any],
) -> dict[str, Any]:
    """Run MC simulation with pension-specific metrics and narrative."""
    num_sims = mc_cfg.get("num_simulations", 1000)
    pctls = mc_cfg.get("percentiles", [10, 25, 50, 75, 90])
    seed = mc_cfg.get("random_seed")

    if years_to_retirement <= 0:
        return _empty_pension_result(pension_balance, pctls)

    months = years_to_retirement * 12
    rng = np.random.default_rng(seed)

    mu_monthly = (annual_return - 0.5 * annual_volatility ** 2) / 12
    sigma_monthly = annual_volatility / np.sqrt(12)

    log_returns = rng.normal(mu_monthly, sigma_monthly, (num_sims, months))
    monthly_returns = np.exp(log_returns)

    wealth = np.full(num_sims, pension_balance, dtype=np.float64)
    for m in range(months):
        wealth = wealth * monthly_returns[:, m] + monthly_contribution

    terminal_values = wealth
    inflation_factor = (1 + inflation) ** years_to_retirement
    terminal_real = terminal_values / inflation_factor

    # Pension pot percentiles
    pot_percentiles = {}
    for p in pctls:
        pot_percentiles[f"p{p}"] = round(float(np.percentile(terminal_real, p)), 2)
    pot_percentiles["median"] = round(float(np.median(terminal_real)), 2)

    # Income from drawdown + state pension
    drawdown_income = terminal_real * safe_withdrawal_rate
    total_income = drawdown_income + state_pension_real

    income_percentiles = {}
    for p in pctls:
        income_percentiles[f"p{p}"] = round(float(np.percentile(total_income, p)), 2)
    income_percentiles["median"] = round(float(np.median(total_income)), 2)

    # Probability of meeting target
    needed_from_pension = max(0, target_income - state_pension_real)
    needed_pot = needed_from_pension / safe_withdrawal_rate if safe_withdrawal_rate > 0 else 0
    prob = probability_of_meeting_target(terminal_real, needed_pot)

    # Narrative
    median_pot = float(np.median(terminal_real))
    narrative = (
        f"There is a {prob * 100:.0f}% chance your pension will exceed "
        f"£{needed_pot:,.0f} in today's money by retirement, "
        f"providing the £{target_income:,.0f}/year income target. "
        f"Median projected pot: £{median_pot:,.0f}."
    )

    return {
        "pension_pot_percentiles": pot_percentiles,
        "income_percentiles": income_percentiles,
        "probability_of_target_pct": round(prob * 100, 1),
        "target_income": target_income,
        "needed_pot": round(needed_pot, 2),
        "narrative": narrative,
        "num_simulations": num_sims,
    }


def _empty_result(
    present_value: float, percentiles: list[int],
) -> dict[str, Any]:
    """Return a degenerate MC result when years <= 0."""
    pv = round(present_value, 2)
    paths = {f"p{p}": [pv] for p in percentiles}
    stats = {"mean": pv, "median": pv}
    for p in percentiles:
        stats[f"p{p}"] = pv
    return {
        "num_simulations": 0,
        "years": 0,
        "terminal_nominal": dict(stats),
        "terminal_real": dict(stats),
        "percentile_paths": paths,
    }


def _empty_pension_result(
    pension_balance: float, percentiles: list[int],
) -> dict[str, Any]:
    """Return a degenerate pension MC result when years <= 0."""
    pv = round(pension_balance, 2)
    pcts = {"median": pv}
    for p in percentiles:
        pcts[f"p{p}"] = pv
    return {
        "pension_pot_percentiles": pcts,
        "income_percentiles": {"median": 0},
        "probability_of_target_pct": 0.0,
        "target_income": 0,
        "needed_pot": 0,
        "narrative": "",
        "num_simulations": 0,
    }
