"""
debt.py — Debt Analysis and Repayment Strategy

Implements avalanche (highest-interest-first) and snowball strategies,
calculates payoff timelines, total interest cost, and debt-to-income
ratios.  Identifies high-interest debt requiring urgent attention.
T1-5: Student loan write-off intelligence with break-even salary.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


def analyse_debt(profile: dict, assumptions: dict) -> dict[str, Any]:
    """
    Produce a complete debt analysis:
    - Per-debt breakdown with payoff timeline and total interest
    - Avalanche-ordered priority list
    - Debt-to-income ratio
    - Recommended extra payment allocation
    - Debt-free date projection
    - T1-5: Student loan write-off intelligence
    """
    debts = profile.get("debts", [])
    inc = profile.get("income", {})
    personal = profile.get("personal", {})
    gross_monthly = inc.get("_total_gross_monthly", 0)
    primary_gross = inc.get("primary_gross_annual", 0)
    age = personal.get("age", 30)
    debt_cfg = assumptions.get("debt", {})
    sl_cfg = assumptions.get("student_loans", {})
    high_thresh = debt_cfg.get("high_interest_threshold", 0.10)
    mod_thresh = debt_cfg.get("moderate_interest_threshold", 0.05)

    if not debts:
        return _empty_result()

    # ------------------------------------------------------------------
    # 1. Per-debt analysis
    # ------------------------------------------------------------------
    analyses = []
    for d in debts:
        dtype = d.get("type", "unknown")
        if dtype in ("student_loan", "student_loan_postgrad"):
            a = _analyse_student_loan(d, dtype, primary_gross, age, sl_cfg, high_thresh, mod_thresh)
        else:
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
    [a for a in analyses if a["risk_tier"] == "moderate"]

    # ------------------------------------------------------------------
    # 5. Extra payment simulation (excludes student loans)
    # ------------------------------------------------------------------
    non_sl_debts = [d for d in debts if d.get("type", "") not in ("student_loan", "student_loan_postgrad")]
    debt_sim_cfg = assumptions.get("debt_simulation", {})
    extra_amounts = debt_sim_cfg.get("extra_payment_scenarios", [100, 200, 500])
    extra_scenarios = _simulate_extra_payments(non_sl_debts, extra_amounts)

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
# Student loan analysis (income-contingent) with T1-5 write-off intelligence
# ---------------------------------------------------------------------------

def _analyse_student_loan(
    debt: dict, dtype: str, gross_annual: float, age: int,
    sl_cfg: dict, high_thresh: float, mod_thresh: float,
) -> dict:
    """
    Analyse a student loan using income-contingent repayment rules.
    T1-5: Includes break-even salary calculation and overpayment recommendation.
    """
    plan_key = "plan_2" if dtype == "student_loan" else "plan_3"
    plan = sl_cfg.get(plan_key, {})

    name = debt.get("name", "Unnamed student loan")
    balance = debt.get("balance", 0)
    rate = debt.get("interest_rate", plan.get("interest_rate", 0.065))
    threshold = plan.get("repayment_threshold", 27295)
    repayment_rate = plan.get("repayment_rate", 0.09)
    write_off_years = plan.get("write_off_years", 30)

    # Income-contingent monthly repayment
    annual_above_threshold = max(0, gross_annual - threshold)
    annual_repayment = annual_above_threshold * repayment_rate
    monthly_repayment = round(annual_repayment / 12, 2)

    # Simulate year-by-year with write-off
    months, total_interest, total_repaid, written_off = _student_loan_projection(
        balance, rate, monthly_repayment, write_off_years,
    )

    will_be_written_off = written_off > 0
    write_off_age = age + (months // 12) if will_be_written_off else None
    years_to_write_off = (months // 12) if will_be_written_off else None

    # T1-5: Write-off intelligence
    write_off_intelligence = _student_loan_write_off_intelligence(
        balance, rate, threshold, repayment_rate, write_off_years,
        gross_annual, age, total_repaid, written_off,
    )

    # Student loans are always "low" risk tier — overpayment rarely advised
    risk_tier = "low"
    current_monthly_interest = balance * rate / 12

    result = {
        "name": name,
        "type": dtype,
        "balance": round(balance, 2),
        "interest_rate": rate,
        "interest_rate_pct": round(rate * 100, 2),
        "minimum_payment_monthly": round(monthly_repayment, 2),
        "income_contingent": True,
        "repayment_threshold": threshold,
        "repayment_rate_pct": round(repayment_rate * 100, 1),
        "current_monthly_interest": round(current_monthly_interest, 2),
        "months_to_payoff": months,
        "years_to_payoff": round(months / 12, 1),
        "total_interest_if_minimum": round(total_interest, 2),
        "total_repaid": round(total_repaid, 2),
        "total_cost": round(total_repaid + total_interest, 2),
        "write_off_years": write_off_years,
        "will_be_written_off": will_be_written_off,
        "amount_written_off": round(written_off, 2),
        "write_off_age": write_off_age,
        "years_to_write_off": years_to_write_off,
        "risk_tier": risk_tier,
        "avalanche_priority": 0,
        "snowball_priority": 0,
        "write_off_intelligence": write_off_intelligence,
    }

    return result


def _student_loan_write_off_intelligence(
    balance: float, rate: float, threshold: float,
    repayment_rate: float, write_off_years: int,
    current_gross: float, age: int,
    total_repaid: float, written_off: float,
) -> dict:
    """
    T1-5: Calculate whether overpaying makes sense and the break-even salary.
    """
    will_be_written_off = written_off > 0

    # Break-even salary: the salary at which total repayments over the loan
    # lifetime exactly equal the balance + interest (i.e. you'd clear it)
    # At salary S: annual repayment = (S - threshold) * repayment_rate
    # Need to find S where cumulative repayments = cumulative balance+interest
    # Approximate using binary search
    break_even_salary = _find_break_even_salary(
        balance, rate, threshold, repayment_rate, write_off_years,
    )

    overpay_recommendation = "do_not_overpay" if will_be_written_off else "consider_overpaying"

    result = {
        "total_lifetime_repayment": round(total_repaid, 2),
        "amount_written_off": round(written_off, 2),
        "will_be_written_off": will_be_written_off,
        "overpay_recommendation": overpay_recommendation,
        "break_even_salary": round(break_even_salary, 0) if break_even_salary else None,
    }

    if will_be_written_off:
        savings_vs_full_repayment = balance - total_repaid
        result["savings_from_write_off"] = round(max(0, savings_vs_full_repayment), 2)
        result["reasoning"] = (
            f"At your current salary trajectory, you will repay £{total_repaid:,.0f} "
            f"of the £{balance:,.0f} balance before it is written off. "
            f"Overpaying would waste money — every extra £1 paid is £1 less written off. "
            f"Direct surplus to higher-return uses instead."
        )
        if break_even_salary:
            result["reasoning"] += (
                f" You would need to earn over £{break_even_salary:,.0f}/year consistently "
                f"to clear this loan before write-off."
            )
    else:
        result["reasoning"] = (
            f"You are on track to repay this loan in full. "
            f"Overpaying could save interest, but compare the {rate*100:.1f}% rate "
            f"against other uses of your surplus."
        )

    return result


def _find_break_even_salary(
    balance: float, rate: float, threshold: float,
    repayment_rate: float, write_off_years: int,
) -> float | None:
    """Binary search for the salary that exactly clears the loan before write-off."""
    if balance <= 0:
        return None

    lo, hi = threshold, 500000
    for _ in range(50):
        mid = (lo + hi) / 2
        annual_repayment = max(0, mid - threshold) * repayment_rate
        monthly = annual_repayment / 12
        _months, _, _, written_off = _student_loan_projection(
            balance, rate, monthly, write_off_years,
        )
        if written_off > 0:
            lo = mid
        else:
            hi = mid
        if hi - lo < 100:
            break

    return round(hi, 0)


def _student_loan_projection(
    balance: float, annual_rate: float, monthly_payment: float, write_off_years: int,
) -> tuple[int, float, float, float]:
    """
    Project student loan balance month-by-month with write-off.
    Returns (months, total_interest, total_repaid, amount_written_off).
    """
    if balance <= 0:
        return 0, 0.0, 0.0, 0.0
    if monthly_payment <= 0:
        return write_off_years * 12, 0.0, 0.0, balance

    monthly_rate = annual_rate / 12
    remaining = balance
    total_interest = 0.0
    total_repaid = 0.0
    max_months = write_off_years * 12

    for month in range(1, max_months + 1):
        interest = remaining * monthly_rate
        total_interest += interest
        remaining += interest

        payment = min(monthly_payment, remaining)
        remaining -= payment
        total_repaid += payment

        if remaining <= 0:
            return month, total_interest, total_repaid, 0.0

    return max_months, total_interest, total_repaid, max(0, remaining)


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

    months, total_interest = _payoff_schedule(balance, rate, min_pay)

    if rate >= high_thresh:
        risk_tier = "high"
    elif rate >= mod_thresh:
        risk_tier = "moderate"
    else:
        risk_tier = "low"

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
        "avalanche_priority": 0,
        "snowball_priority": 0,
    }


def _payoff_schedule(balance: float, annual_rate: float, monthly_payment: float) -> tuple[int, float]:
    """
    Simulate month-by-month payoff and return (months, total_interest).
    Caps at max_months to avoid infinite loops on underpaying debts.
    """
    if balance <= 0:
        return 0, 0.0

    max_months = 600
    if monthly_payment <= 0:
        return max_months, balance * annual_rate / 12 * max_months

    monthly_rate = annual_rate / 12
    remaining = balance
    total_interest = 0.0
    months = 0

    while remaining > 0 and months < max_months:
        interest = remaining * monthly_rate
        total_interest += interest
        principal = monthly_payment - interest

        if principal <= 0:
            return max_months, total_interest + (remaining * monthly_rate * (max_months - months))

        remaining -= principal
        months += 1

    if remaining > 0:
        total_interest += remaining

    return months, round(total_interest, 2)


# ---------------------------------------------------------------------------
# Extra payment scenarios
# ---------------------------------------------------------------------------

def _simulate_extra_payments(debts: list[dict], extra_amounts: list[int]) -> list[dict]:
    """
    For each extra monthly amount, simulate avalanche payoff and compare
    to minimum-only baseline.
    """
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
    """
    if not debts:
        return 0, 0.0

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
        for d in active:
            if d["balance"] > 0:
                interest = d["balance"] * d["rate"] / 12
                total_interest += interest
                d["balance"] += interest

        freed = extra_monthly
        for d in active:
            if d["balance"] > 0:
                payment = min(d["min_pay"], d["balance"])
                d["balance"] -= payment
                if d["balance"] <= 0:
                    freed += d["min_pay"] - payment
                    d["balance"] = 0

        for d in active:
            if d["balance"] > 0 and freed > 0:
                payment = min(freed, d["balance"])
                d["balance"] -= payment
                freed -= payment
                if d["balance"] <= 0:
                    d["balance"] = 0
                break

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
