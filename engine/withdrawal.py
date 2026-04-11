"""engine/withdrawal.py — Tax-optimal withdrawal sequencing (v8.3).

Models the optimal order to draw from multiple retirement income sources
to minimise lifetime tax. Covers personal allowance filling, basic rate
band optimisation, PCLS timing, and state pension deferral analysis.
"""

from __future__ import annotations

import logging
from typing import Any

from engine.tax import calculate_tax_on_pension_withdrawal

logger = logging.getLogger(__name__)


def model_withdrawal_sequence(
    profile: dict[str, Any],
    assumptions: dict[str, Any],
    investment_result: dict[str, Any],
) -> dict[str, Any]:
    """Generate a year-by-year tax-optimal withdrawal schedule for retirement."""
    personal = profile.get("personal", {})
    sav = profile.get("savings", {})

    age = personal.get("age", 30)
    retirement_age = personal.get("retirement_age",
                                  assumptions.get("life_events", {}).get("retirement_age", 67))
    life_expectancy = assumptions.get("life_events", {}).get("life_expectancy", 85)

    tax_cfg = assumptions.get("tax", {})
    pa = tax_cfg.get("personal_allowance", 12570)
    basic_thresh = tax_cfg.get("basic_threshold", 50270)

    retire_cfg = assumptions.get("retirement", {})
    target_income = retire_cfg.get("default_income_target", 30000)
    pcls_fraction = retire_cfg.get("tax_free_lump_sum_fraction", 0.25)

    sp_cfg = assumptions.get("state_pension", {})
    state_pension_annual = sp_cfg.get("full_annual_amount", 11502)
    state_pension_age = sp_cfg.get("age", 67)
    deferral_rate = assumptions.get("lifetime_cashflow", {}).get(
        "state_pension_deferral_rate", 0.058)

    inflation = assumptions.get("inflation", {}).get("general", 0.03)
    risk_profile = personal.get("risk_profile", "moderate")
    investment_return = assumptions.get("investment_returns", {}).get(risk_profile, 0.06)

    # Projected balances at retirement from investment_result
    pension_analysis = investment_result.get("pension_analysis", {})
    pension_at_retire_real = pension_analysis.get("projected_at_retirement_real", 0)
    isa_bal = sav.get("isa_balance", 0) + sav.get("lisa_balance", 0)
    years_to_retire = max(0, retirement_age - age)
    isa_at_retire = isa_bal * ((1 + investment_return) ** years_to_retire)
    isa_at_retire_real = isa_at_retire / ((1 + inflation) ** years_to_retire) if years_to_retire > 0 else isa_bal

    # CGT config
    cgt_cfg = assumptions.get("capital_gains_tax", {})
    cgt_exemption = cgt_cfg.get("annual_exemption", 3000)

    # State pension at retirement (real terms)
    sp_real = pension_analysis.get("state_pension", {}).get("projected_annual_real", state_pension_annual)

    # Build optimised year-by-year schedule
    schedule = _build_schedule(
        pension_bal=pension_at_retire_real,
        isa_bal=isa_at_retire_real,
        state_pension=sp_real,
        target_income=target_income,
        pa=pa,
        basic_thresh=basic_thresh,
        pcls_fraction=pcls_fraction,
        tax_cfg=tax_cfg,
        investment_return=investment_return - inflation,  # real return
        retirement_age=retirement_age,
        life_expectancy=life_expectancy,
        cgt_exemption=cgt_exemption,
    )

    # Build naive schedule (pension-only)
    naive_schedule = _build_naive_schedule(
        pension_bal=pension_at_retire_real,
        isa_bal=isa_at_retire_real,
        state_pension=sp_real,
        target_income=target_income,
        tax_cfg=tax_cfg,
        investment_return=investment_return - inflation,
        retirement_age=retirement_age,
        life_expectancy=life_expectancy,
    )

    # Compare
    optimised_total_tax = sum(y["tax_paid"] for y in schedule)
    naive_total_tax = sum(y["tax_paid"] for y in naive_schedule)
    lifetime_saving = naive_total_tax - optimised_total_tax

    # PCLS timing analysis
    pcls_analysis = _analyse_pcls_timing(
        pension_at_retire_real, pcls_fraction, investment_return - inflation,
        retirement_age, life_expectancy,
    )

    # State pension deferral analysis
    deferral_analysis = _analyse_sp_deferral(
        sp_real, deferral_rate, retirement_age, state_pension_age, life_expectancy,
    )

    logger.info(
        "Withdrawal sequencing: lifetime tax saving £%.0f (optimised £%.0f vs naive £%.0f)",
        lifetime_saving, optimised_total_tax, naive_total_tax,
    )

    return {
        "optimised_schedule": schedule,
        "naive_total_tax": round(naive_total_tax, 2),
        "optimised_total_tax": round(optimised_total_tax, 2),
        "lifetime_tax_saving": round(lifetime_saving, 2),
        "draw_order": [
            "1. Use pension personal allowance band (tax-free up to PA)",
            "2. Draw pension to fill basic rate band",
            "3. Top up from ISA (tax-free withdrawals)",
            "4. Crystallise GIA gains within CGT annual exemption",
            "5. State pension received automatically",
        ],
        "pcls_timing": pcls_analysis,
        "state_pension_deferral": deferral_analysis,
        "years_modelled": life_expectancy - retirement_age,
    }


def _build_schedule(
    pension_bal: float,
    isa_bal: float,
    state_pension: float,
    target_income: float,
    pa: float,
    basic_thresh: float,
    pcls_fraction: float,
    tax_cfg: dict,
    investment_return: float,
    retirement_age: int,
    life_expectancy: int,
    cgt_exemption: float,
) -> list[dict[str, Any]]:
    """Build year-by-year optimised withdrawal schedule."""
    years = max(1, life_expectancy - retirement_age)
    schedule: list[dict[str, Any]] = []
    pcls_taken = False

    for yr in range(years):
        current_age = retirement_age + yr
        year_entry: dict[str, Any] = {"year": yr, "age": current_age}

        # PCLS in year 0
        pcls = 0.0
        if not pcls_taken:
            pcls = pension_bal * pcls_fraction
            pension_bal -= pcls
            pcls_taken = True
            year_entry["pcls_lump_sum"] = round(pcls, 2)

        # Income needed after state pension
        remaining_need = max(0, target_income - state_pension)

        # Step 1: Draw pension up to personal allowance (tax-free band)
        pension_to_pa = min(max(0, pa - state_pension), remaining_need, pension_bal)
        pension_bal -= pension_to_pa
        remaining_need -= pension_to_pa

        # Step 2: Draw pension to fill basic rate band
        basic_band_room = max(0, basic_thresh - pa)
        pension_to_basic = min(basic_band_room, remaining_need, pension_bal)
        pension_bal -= pension_to_basic
        remaining_need -= pension_to_basic

        total_pension_draw = pension_to_pa + pension_to_basic

        # Step 3: Top up from ISA (tax-free)
        isa_draw = min(remaining_need, isa_bal)
        isa_bal -= isa_draw
        remaining_need -= isa_draw

        # Calculate tax on pension + state pension
        tax_result = calculate_tax_on_pension_withdrawal(
            total_pension_draw, state_pension, tax_cfg,
        )
        tax_paid = tax_result["income_tax"]

        # Grow remaining balances
        pension_bal *= (1 + investment_return)
        isa_bal *= (1 + investment_return)

        total_gross = total_pension_draw + state_pension + isa_draw + pcls
        total_net = total_gross - tax_paid

        year_entry.update({
            "pension_drawdown": round(total_pension_draw, 2),
            "isa_drawdown": round(isa_draw, 2),
            "state_pension": round(state_pension, 2),
            "total_gross": round(total_gross, 2),
            "tax_paid": round(tax_paid, 2),
            "total_net": round(total_net, 2),
            "pension_remaining": round(pension_bal, 2),
            "isa_remaining": round(isa_bal, 2),
        })

        schedule.append(year_entry)

    return schedule


def _build_naive_schedule(
    pension_bal: float,
    isa_bal: float,
    state_pension: float,
    target_income: float,
    tax_cfg: dict,
    investment_return: float,
    retirement_age: int,
    life_expectancy: int,
) -> list[dict[str, Any]]:
    """Build naive withdrawal schedule: all from pension."""
    years = max(1, life_expectancy - retirement_age)
    schedule: list[dict[str, Any]] = []

    for yr in range(years):
        remaining_need = max(0, target_income - state_pension)
        pension_draw = min(remaining_need, pension_bal)
        pension_bal -= pension_draw

        tax_result = calculate_tax_on_pension_withdrawal(
            pension_draw, state_pension, tax_cfg,
        )

        pension_bal *= (1 + investment_return)
        isa_bal *= (1 + investment_return)

        schedule.append({
            "year": yr,
            "age": retirement_age + yr,
            "pension_drawdown": round(pension_draw, 2),
            "tax_paid": round(tax_result["income_tax"], 2),
        })

    return schedule


def _analyse_pcls_timing(
    pension_real: float,
    pcls_fraction: float,
    real_return: float,
    retirement_age: int,
    life_expectancy: int,
) -> dict[str, Any]:
    """Model early vs late PCLS and find break-even."""
    years_in_retirement = max(1, life_expectancy - retirement_age)
    early_pcls = pension_real * pcls_fraction

    # Early PCLS: take at retirement, invest the lump sum
    early_invested = early_pcls * ((1 + real_return) ** years_in_retirement)
    remaining_early = (pension_real - early_pcls) * ((1 + real_return) ** years_in_retirement)

    # Late PCLS: take at retirement + 5 years
    delay_years = min(5, years_in_retirement)
    pension_grown = pension_real * ((1 + real_return) ** delay_years)
    late_pcls = pension_grown * pcls_fraction
    remaining_late = (pension_grown - late_pcls) * ((1 + real_return) ** (years_in_retirement - delay_years))
    late_invested = late_pcls * ((1 + real_return) ** (years_in_retirement - delay_years))

    early_total = early_invested + remaining_early
    late_total = late_invested + remaining_late

    return {
        "early_pcls_amount": round(early_pcls, 2),
        "late_pcls_amount": round(late_pcls, 2),
        "delay_years": delay_years,
        "early_total_at_death": round(early_total, 2),
        "late_total_at_death": round(late_total, 2),
        "recommendation": "early" if early_total >= late_total else "late",
        "note": (
            "Taking PCLS early gives immediate access to tax-free cash but reduces "
            "the pension growing tax-sheltered. Delaying PCLS allows a larger lump sum "
            "but delays access."
        ),
    }


def _analyse_sp_deferral(
    state_pension_real: float,
    deferral_rate: float,
    retirement_age: int,
    state_pension_age: int,
    life_expectancy: int,
) -> dict[str, Any]:
    """Model state pension deferral scenarios and break-even ages."""
    scenarios = []
    years_from_spa = max(0, life_expectancy - state_pension_age)

    for defer_years in [1, 2, 3, 5]:
        if defer_years >= years_from_spa:
            continue

        enhanced_sp = state_pension_real * (1 + deferral_rate * defer_years)
        income_foregone = state_pension_real * defer_years
        annual_gain = enhanced_sp - state_pension_real
        break_even_years = income_foregone / annual_gain if annual_gain > 0 else float("inf")
        break_even_age = round(state_pension_age + defer_years + break_even_years, 1)
        receiving_years = years_from_spa - defer_years
        lifetime_total = enhanced_sp * receiving_years
        no_defer_total = state_pension_real * years_from_spa

        scenarios.append({
            "defer_years": defer_years,
            "enhanced_annual": round(enhanced_sp, 2),
            "uplift_pct": round(deferral_rate * defer_years * 100, 1),
            "income_foregone": round(income_foregone, 2),
            "break_even_age": break_even_age,
            "lifetime_total": round(lifetime_total, 2),
            "vs_no_deferral": round(lifetime_total - no_defer_total, 2),
            "beneficial": lifetime_total > no_defer_total,
        })

    best = max(scenarios, key=lambda s: s["vs_no_deferral"]) if scenarios else None

    return {
        "current_state_pension": round(state_pension_real, 2),
        "deferral_rate_pct": round(deferral_rate * 100, 1),
        "scenarios": scenarios,
        "recommendation": (
            f"Deferring {best['defer_years']} year(s) is optimal — "
            f"break-even at age {best['break_even_age']}, "
            f"lifetime gain £{best['vs_no_deferral']:,.0f}"
        ) if best and best["beneficial"] else "No deferral recommended at current life expectancy",
    }
