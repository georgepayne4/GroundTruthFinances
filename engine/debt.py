"""
debt.py — Debt Analysis and Repayment Strategy

Implements avalanche (highest-interest-first) and snowball strategies,
calculates payoff timelines, total interest cost, and debt-to-income
ratios.  Identifies high-interest debt requiring urgent attention.
"""

from __future__ import annotations

import math
from typing import Any


def analyse_debt(profile: dict, assumptions: dict) -> dict[str, Any]:
    """
    Produce a complete debt analysis:
    - Per-debt breakdown with payoff timeline and total interest
    - Avalanche-ordered priority list
    - Debt-to-income ratio
    - Recommended extra payment allocation
    - Debt-free date projection
    """
    debts = profile.get("debts", [])
    inc = profile.get("income", {})
    gross_monthly = inc.get("_total_gross_monthly", 0)
    debt_cfg = assumptions.get("debt", {})
    high_thresh = debt_cfg.get("high_interest_threshold", 0.10)
    mod_thresh = debt_cfg.get("moderate_interest_threshold", 0.05)

    if not debts:
        return _empty_result()

    # ------------------------------------------------------------------
    # 1. Per-debt analysis
    # ------------------------------------------------------------------
    analyses = []
    for d in debts:
        a = _analyse_single_debt(d, high_thresh, mod_thresh)
        analyses.append(a)

    # ------------------------------------------------------------------
    # 2. Avalanche ordering (highest rate first)
    # ------------------------------------------------------------------
    avalanche_order = sorted(analyses, key=lambda x: x["interest_rate"], reverse=True)
    for rank, a in enumerate(avalanche_order, 1):
        a["avalanche_priority"] = rank

    # Also produce snowball order (lowest balance first) for reference
    snowball_order = sorted(analyses, key=lambda x: x["balance"])
    for rank, a in enumerate(snowball_order, 1):
        # Find matching entry and annotate
        for a2 in analyses:
            if a2["name"] == a["name"]:
                a2["snowball_priority"] = rank

    # ------------------------------------------------------------------
    # 3. Aggregate metrics
    # ------------------------------------------------------------------
    total_balance = sum(a["balance"] for a in analyses)
    total_min_monthly = sum(a["minimum_payment_monthly"] for a in analyses)
    total_interest_cost = sum(a["total_interest_if_minimum"] for a in analyses)
    weighted_rate = (
        sum(a["balance"] * a["interest_rate"] for a in analyses) / total_balance
        if total_balance > 0 else 0
    )

    # Debt-to-income ratios
    dti_gross = (total_min_monthly / gross_monthly * 100) if gross_monthly > 0 else 0

    # Longest payoff among all debts
    max_months = max((a["months_to_payoff"] for a in analyses), default=0)

    # ------------------------------------------------------------------
    # 4. Classify urgency
    # ------------------------------------------------------------------
    high_interest_debts = [a for a in analyses if a["risk_tier"] == "high"]
    moderate_debts = [a for a in analyses if a["risk_tier"] == "moderate"]

    # ------------------------------------------------------------------
    # 5. Extra payment simulation
    # ------------------------------------------------------------------
    # Show impact of directing an additional 100, 200, 500/mo toward debt
    extra_scenarios = _simulate_extra_payments(debts, [100, 200, 500])

    return {
        "debts": analyses,
        "summary": {
            "total_balance": round(total_balance, 2),
            "total_minimum_monthly": round(total_min_monthly, 2),
            "total_interest_if_minimum_only": round(total_interest_cost, 2),
            "weighted_average_rate_pct": round(weighted_rate * 100, 2),
            "debt_to_income_gross_pct": round(dti_gross, 1),
            "longest_payoff_months": max_months,
            "high_interest_debt_count": len(high_interest_debts),
            "high_interest_total_balance": round(
                sum(d["balance"] for d in high_interest_debts), 2
            ),
        },
        "recommended_strategy": "avalanche",
        "avalanche_order": [a["name"] for a in avalanche_order],
        "extra_payment_scenarios": extra_scenarios,
    }


# ---------------------------------------------------------------------------
# Per-debt analysis
# ---------------------------------------------------------------------------

def _analyse_single_debt(debt: dict, high_thresh: float, mod_thresh: float) -> dict:
    """Analyse a single debt instrument."""
    name = debt.get("name", "Unnamed debt")
    balance = debt.get("balance", 0)
    rate = debt.get("interest_rate", 0)
    min_pay = debt.get("minimum_payment_monthly", 0)
    dtype = debt.get("type", "unknown")

    # Payoff timeline at minimum payments
    months, total_interest = _payoff_schedule(balance, rate, min_pay)

    # Risk tier
    if rate >= high_thresh:
        risk_tier = "high"
    elif rate >= mod_thresh:
        risk_tier = "moderate"
    else:
        risk_tier = "low"

    # Monthly interest cost right now
    current_monthly_interest = balance * rate / 12

    return {
        "name": name,
        "type": dtype,
        "balance": round(balance, 2),
        "interest_rate": rate,
        "interest_rate_pct": round(rate * 100, 2),
        "minimum_payment_monthly": round(min_pay, 2),
        "current_monthly_interest": round(current_monthly_interest, 2),
        "months_to_payoff": months,
        "years_to_payoff": round(months / 12, 1),
        "total_interest_if_minimum": round(total_interest, 2),
        "total_cost": round(balance + total_interest, 2),
        "risk_tier": risk_tier,
        "avalanche_priority": 0,  # set later
        "snowball_priority": 0,   # set later
    }


def _payoff_schedule(balance: float, annual_rate: float, monthly_payment: float) -> tuple[int, float]:
    """
    Simulate month-by-month payoff and return (months, total_interest).
    Caps at 600 months (50 years) to avoid infinite loops on underpaying debts.
    """
    if balance <= 0:
        return 0, 0.0
    if monthly_payment <= 0:
        return 600, balance * annual_rate / 12 * 600  # effectively infinite

    monthly_rate = annual_rate / 12
    remaining = balance
    total_interest = 0.0
    months = 0
    max_months = 600

    while remaining > 0 and months < max_months:
        interest = remaining * monthly_rate
        total_interest += interest
        principal = monthly_payment - interest

        if principal <= 0:
            # Payment doesn't cover interest — debt is growing
            return max_months, total_interest + (remaining * monthly_rate * (max_months - months))

        remaining -= principal
        months += 1

    if remaining > 0:
        total_interest += remaining  # approximate remaining interest

    return months, round(total_interest, 2)


# ---------------------------------------------------------------------------
# Extra payment scenarios
# ---------------------------------------------------------------------------

def _simulate_extra_payments(debts: list[dict], extra_amounts: list[int]) -> list[dict]:
    """
    For each extra monthly amount, simulate avalanche payoff and compare
    to minimum-only baseline.
    """
    # Baseline: minimum payments only
    baseline_months, baseline_interest = _avalanche_payoff(debts, 0)

    scenarios = []
    for extra in extra_amounts:
        months, interest = _avalanche_payoff(debts, extra)
        scenarios.append({
            "extra_monthly": extra,
            "months_to_debt_free": months,
            "total_interest": round(interest, 2),
            "months_saved": baseline_months - months,
            "interest_saved": round(baseline_interest - interest, 2),
        })
    return scenarios


def _avalanche_payoff(debts: list[dict], extra_monthly: float) -> tuple[int, float]:
    """
    Simulate avalanche (highest-rate-first) payoff across all debts.
    Extra money goes to the highest-rate debt first; when one is paid off
    its payment cascades to the next.
    """
    if not debts:
        return 0, 0.0

    # Work with copies sorted by rate descending
    active = sorted(
        [
            {
                "balance": d.get("balance", 0),
                "rate": d.get("interest_rate", 0),
                "min_pay": d.get("minimum_payment_monthly", 0),
            }
            for d in debts if d.get("balance", 0) > 0
        ],
        key=lambda x: x["rate"],
        reverse=True,
    )

    total_interest = 0.0
    months = 0
    max_months = 600

    while any(d["balance"] > 0 for d in active) and months < max_months:
        months += 1
        # Apply interest to all active debts
        for d in active:
            if d["balance"] > 0:
                interest = d["balance"] * d["rate"] / 12
                total_interest += interest
                d["balance"] += interest

        # Pay minimums on all debts
        freed = extra_monthly
        for d in active:
            if d["balance"] > 0:
                payment = min(d["min_pay"], d["balance"])
                d["balance"] -= payment
                if d["balance"] <= 0:
                    freed += d["min_pay"] - payment  # freed-up minimum
                    d["balance"] = 0

        # Apply extra + freed money to highest-rate debt still active
        for d in active:
            if d["balance"] > 0 and freed > 0:
                payment = min(freed, d["balance"])
                d["balance"] -= payment
                freed -= payment
                if d["balance"] <= 0:
                    freed += 0  # already captured
                    d["balance"] = 0
                break  # only apply to top priority

    return months, round(total_interest, 2)


def _empty_result() -> dict:
    return {
        "debts": [],
        "summary": {
            "total_balance": 0,
            "total_minimum_monthly": 0,
            "total_interest_if_minimum_only": 0,
            "weighted_average_rate_pct": 0,
            "debt_to_income_gross_pct": 0,
            "longest_payoff_months": 0,
            "high_interest_debt_count": 0,
            "high_interest_total_balance": 0,
        },
        "recommended_strategy": "none",
        "avalanche_order": [],
        "extra_payment_scenarios": [],
    }
