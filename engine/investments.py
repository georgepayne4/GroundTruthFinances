"""
investments.py — Investment Allocation and Projection

Comprehensive investment analysis including:
- FA-1:  Tax on pension withdrawal
- FA-6:  Employer pension match optimisation
- IA-1:  Fee impact modelling
- IA-2:  Time-horizon-based allocation
- IA-3:  Emergency fund placement warning
- IA-4:  Tax-efficient withdrawal sequencing
- IA-5:  Glide path / age-based de-risking
- IA-7:  Dividend reinvestment & pound-cost averaging
- IA-8:  Portfolio risk metrics
- IA-9:  Drawdown vs annuity comparison
- IA-10: ESG awareness
- IA-11: ISA contribution tracking
"""

from __future__ import annotations

import math
from typing import Any

from engine.tax import calculate_tax_on_pension_withdrawal


# ---------------------------------------------------------------------------
# Model portfolios by risk profile (IA-8: with risk metrics)
# ---------------------------------------------------------------------------

MODEL_PORTFOLIOS = {
    "conservative": {
        "allocation": {
            "government_bonds": 40,
            "corporate_bonds": 20,
            "uk_equity": 15,
            "global_equity": 10,
            "property_funds": 5,
            "cash": 10,
        },
        "expected_return": 0.04,
        "historical_volatility": 0.06,
        "max_drawdown": -0.15,
        "worst_year": -0.10,
        "negative_year_probability": 0.12,
    },
    "moderate": {
        "allocation": {
            "government_bonds": 15,
            "corporate_bonds": 15,
            "uk_equity": 25,
            "global_equity": 25,
            "property_funds": 10,
            "cash": 10,
        },
        "expected_return": 0.06,
        "historical_volatility": 0.10,
        "max_drawdown": -0.25,
        "worst_year": -0.18,
        "negative_year_probability": 0.20,
    },
    "aggressive": {
        "allocation": {
            "government_bonds": 5,
            "corporate_bonds": 5,
            "uk_equity": 30,
            "global_equity": 40,
            "property_funds": 10,
            "cash": 10,
        },
        "expected_return": 0.08,
        "historical_volatility": 0.15,
        "max_drawdown": -0.35,
        "worst_year": -0.25,
        "negative_year_probability": 0.25,
    },
    "very_aggressive": {
        "allocation": {
            "government_bonds": 0,
            "corporate_bonds": 0,
            "uk_equity": 30,
            "global_equity": 45,
            "emerging_markets": 10,
            "property_funds": 10,
            "cash": 5,
        },
        "expected_return": 0.10,
        "historical_volatility": 0.20,
        "max_drawdown": -0.45,
        "worst_year": -0.35,
        "negative_year_probability": 0.30,
    },
}


def analyse_investments(profile: dict, assumptions: dict, cashflow: dict) -> dict[str, Any]:
    """
    Produce comprehensive investment analysis.
    """
    sav = profile.get("savings", {})
    personal = profile.get("personal", {})
    inc = profile.get("income", {})
    surplus = cashflow.get("surplus", {}).get("monthly", 0)

    risk_profile = personal.get("risk_profile", "moderate").lower()
    if risk_profile not in MODEL_PORTFOLIOS:
        risk_profile = "moderate"

    returns_cfg = assumptions.get("investment_returns", {})
    expected_return = returns_cfg.get(risk_profile, 0.06)
    inflation = assumptions.get("inflation", {}).get("general", 0.03)
    real_return = expected_return - inflation
    tax_cfg = assumptions.get("tax", {})

    age = personal.get("age", 30)
    retirement_age = personal.get("retirement_age",
                                  assumptions.get("life_events", {}).get("retirement_age", 67))
    years_to_retirement = max(1, retirement_age - age)

    # ------------------------------------------------------------------
    # 1. Current portfolio snapshot
    # ------------------------------------------------------------------
    isa = sav.get("isa_balance", 0)
    lisa = sav.get("lisa_balance", 0)
    pension = sav.get("pension_balance", 0)
    other_inv = sav.get("other_investments", 0)
    total_invested = isa + lisa + pension + other_inv

    primary_gross = inc.get("primary_gross_annual", 0)
    pension_personal_pct = sav.get("pension_personal_contribution_pct", 0)
    pension_employer_pct = sav.get("pension_employer_contribution_pct", 0)
    annual_pension_contribution = primary_gross * (pension_personal_pct + pension_employer_pct)
    monthly_pension_contribution = annual_pension_contribution / 12

    # ------------------------------------------------------------------
    # 2. Model portfolio & risk metrics (IA-8)
    # ------------------------------------------------------------------
    model = MODEL_PORTFOLIOS[risk_profile]
    risk_metrics = {
        "expected_return_pct": round(model["expected_return"] * 100, 1),
        "historical_volatility_pct": round(model["historical_volatility"] * 100, 1),
        "max_drawdown_pct": round(model["max_drawdown"] * 100, 1),
        "worst_year_pct": round(model["worst_year"] * 100, 1),
        "negative_year_probability_pct": round(model["negative_year_probability"] * 100, 0),
        "note": (
            f"With a '{risk_profile}' profile, expect your portfolio to lose value in roughly "
            f"1 out of every {int(1 / model['negative_year_probability'])} years. "
            f"The worst single-year loss could be around {abs(model['worst_year']) * 100:.0f}%. "
            f"This is normal and expected."
        ),
    }

    # ------------------------------------------------------------------
    # 3. Fee impact modelling (IA-1)
    # ------------------------------------------------------------------
    fees_cfg = sav.get("investment_fees", {})
    fee_analysis = _fee_impact_analysis(
        isa, pension, fees_cfg, expected_return, years_to_retirement,
        monthly_pension_contribution, surplus,
    )

    # Net return after fees
    total_isa_fee = fees_cfg.get("isa_platform_fee", 0) + fees_cfg.get("isa_fund_ocf", 0)
    total_pension_fee = fees_cfg.get("pension_platform_fee", 0) + fees_cfg.get("pension_fund_ocf", 0)
    blended_fee = 0.0
    if total_invested > 0:
        blended_fee = ((isa + lisa) * total_isa_fee + pension * total_pension_fee) / total_invested

    net_return = expected_return - blended_fee
    net_real_return = net_return - inflation

    # ------------------------------------------------------------------
    # 4. Portfolio growth projection
    # ------------------------------------------------------------------
    projections = _project_growth(
        current_invested=total_invested,
        monthly_contribution=monthly_pension_contribution,
        annual_return=net_return,
        inflation=inflation,
        years_list=[5, 10, years_to_retirement],
    )

    # ------------------------------------------------------------------
    # 5. Pension adequacy with tax on withdrawal (FA-1)
    # ------------------------------------------------------------------
    pension_at_retirement = _future_value(
        present_value=pension,
        monthly_contribution=monthly_pension_contribution,
        annual_return=net_return,
        years=years_to_retirement,
    )
    pension_at_retirement_real = pension_at_retirement / ((1 + inflation) ** years_to_retirement)

    safe_withdrawal_rate = 0.04
    gross_pension_income = pension_at_retirement_real * safe_withdrawal_rate
    tax_free_lump_sum = pension_at_retirement_real * 0.25

    # State pension
    sp_cfg = assumptions.get("state_pension", {})
    state_pension_annual = sp_cfg.get("full_annual_amount", 11502)
    state_pension_age = sp_cfg.get("age", 67)
    qualifying_years_needed = sp_cfg.get("qualifying_years_full", 35)
    qualifying_years_min = sp_cfg.get("qualifying_years_min", 10)
    triple_lock_growth = sp_cfg.get("triple_lock_growth", 0.035)

    estimated_qualifying_years = min(qualifying_years_needed, max(0, age - 21))
    years_to_state_pension = max(0, state_pension_age - age)
    projected_qualifying_years = min(qualifying_years_needed, estimated_qualifying_years + years_to_state_pension)

    if projected_qualifying_years >= qualifying_years_needed:
        state_pension_fraction = 1.0
    elif projected_qualifying_years >= qualifying_years_min:
        state_pension_fraction = projected_qualifying_years / qualifying_years_needed
    else:
        state_pension_fraction = 0.0

    state_pension_at_retirement = (
        state_pension_annual * state_pension_fraction * ((1 + triple_lock_growth) ** years_to_state_pension)
    )
    state_pension_at_retirement_real = state_pension_at_retirement / ((1 + inflation) ** years_to_state_pension)

    # FA-1: Tax on pension withdrawal
    retirement_tax = calculate_tax_on_pension_withdrawal(
        gross_pension_income, state_pension_at_retirement_real, tax_cfg,
    )

    total_retirement_income_gross = gross_pension_income + state_pension_at_retirement_real
    total_retirement_income_net = retirement_tax["net_income"]

    pension_replacement_ratio_gross = (
        total_retirement_income_gross / primary_gross * 100 if primary_gross > 0 else 0
    )
    pension_replacement_ratio_net = (
        total_retirement_income_net / primary_gross * 100 if primary_gross > 0 else 0
    )

    life_expectancy = assumptions.get("life_events", {}).get("life_expectancy", 85)
    years_in_retirement = max(1, life_expectancy - retirement_age)
    pension_lasts_years = (
        pension_at_retirement_real / (gross_pension_income or 1)
    )

    pension_adequate = pension_replacement_ratio_net >= 50

    # ------------------------------------------------------------------
    # 6. FA-6: Employer pension match optimisation
    # ------------------------------------------------------------------
    match_cap = sav.get("pension_employer_match_cap_pct", pension_employer_pct)
    pension_match_analysis = None
    if pension_personal_pct < match_cap:
        additional_pct = match_cap - pension_personal_pct
        additional_personal = primary_gross * additional_pct
        additional_employer = primary_gross * additional_pct
        # Net cost after tax relief (higher-rate payer pays 60p per £1)
        if primary_gross > tax_cfg.get("basic_threshold", 50270):
            net_cost = additional_personal * 0.60
        else:
            net_cost = additional_personal * 0.80

        pension_match_analysis = {
            "current_personal_pct": round(pension_personal_pct * 100, 1),
            "match_cap_pct": round(match_cap * 100, 1),
            "additional_personal_annual": round(additional_personal, 2),
            "additional_employer_annual": round(additional_employer, 2),
            "free_money_left_on_table": round(additional_employer, 2),
            "net_cost_after_tax_relief_annual": round(net_cost, 2),
            "net_cost_monthly": round(net_cost / 12, 2),
        }

    # ------------------------------------------------------------------
    # 7. IA-2: Time-horizon-based allocation suggestions
    # ------------------------------------------------------------------
    time_horizon_analysis = _time_horizon_allocation(sav, profile, years_to_retirement)

    # ------------------------------------------------------------------
    # 8. IA-3: Emergency fund placement warning
    # ------------------------------------------------------------------
    ef_type = sav.get("emergency_fund_type", "cash")
    ef_balance = sav.get("emergency_fund", 0)
    emergency_fund_warning = None
    if ef_type == "stocks_and_shares" and ef_balance > 0:
        loss_20pct = ef_balance * 0.80
        emergency_fund_warning = {
            "current_type": ef_type,
            "balance": round(ef_balance, 2),
            "risk": (
                f"Your emergency fund is invested in equities. A 20% market drop would "
                f"reduce your buffer from £{ef_balance:,.0f} to £{loss_20pct:,.0f} at exactly "
                f"the moment you might need it."
            ),
            "action": "Move emergency fund to a cash savings account or money market fund.",
        }

    # ------------------------------------------------------------------
    # 9. IA-4: Tax-efficient withdrawal sequencing
    # ------------------------------------------------------------------
    withdrawal_strategy = _retirement_withdrawal_strategy(
        pension_at_retirement_real, isa, state_pension_at_retirement_real, tax_cfg,
    )

    # ------------------------------------------------------------------
    # 10. IA-5: Glide path projection
    # ------------------------------------------------------------------
    glide_path_cfg = assumptions.get("glide_path", [])
    glide_path = _glide_path_projection(
        age, retirement_age, total_invested, monthly_pension_contribution,
        returns_cfg, inflation, glide_path_cfg,
    )

    # ------------------------------------------------------------------
    # 11. IA-9: Drawdown vs annuity comparison
    # ------------------------------------------------------------------
    annuity_cfg = assumptions.get("annuity", {})
    annuity_comparison = _annuity_comparison(
        pension_at_retirement_real, retirement_age, annuity_cfg,
        gross_pension_income, state_pension_at_retirement_real, tax_cfg,
    )

    # ------------------------------------------------------------------
    # 12. IA-11: ISA contribution tracking
    # ------------------------------------------------------------------
    isa_tracking = _isa_contribution_tracking(sav)

    # ------------------------------------------------------------------
    # 13. IA-10: ESG awareness
    # ------------------------------------------------------------------
    esg_pref = personal.get("esg_preference", "none")
    esg_note = None
    if esg_pref in ("preferred", "required"):
        esg_note = (
            "ESG/ethical fund options are available for all major asset classes with "
            "comparable long-term returns. Look for funds with MSCI ESG ratings of AA or above."
        )

    # ------------------------------------------------------------------
    # 14. Investable surplus
    # ------------------------------------------------------------------
    investable_monthly = max(0, surplus - monthly_pension_contribution)

    # ------------------------------------------------------------------
    # 15. Assemble
    # ------------------------------------------------------------------
    result = {
        "current_portfolio": {
            "isa_balance": round(isa, 2),
            "lisa_balance": round(lisa, 2),
            "pension_balance": round(pension, 2),
            "other_investments": round(other_inv, 2),
            "total_invested": round(total_invested, 2),
        },
        "risk_profile": risk_profile,
        "expected_annual_return_pct": round(expected_return * 100, 1),
        "expected_real_return_pct": round(real_return * 100, 1),
        "net_return_after_fees_pct": round(net_return * 100, 2),
        "suggested_allocation": model["allocation"],
        "risk_metrics": risk_metrics,
        "fee_analysis": fee_analysis,
        "growth_projections": projections,
        "pension_analysis": {
            "current_balance": round(pension, 2),
            "monthly_contribution_total": round(monthly_pension_contribution, 2),
            "annual_contribution_total": round(annual_pension_contribution, 2),
            "projected_at_retirement_nominal": round(pension_at_retirement, 2),
            "projected_at_retirement_real": round(pension_at_retirement_real, 2),
            "tax_free_lump_sum": round(tax_free_lump_sum, 2),
            "annual_income_gross": round(gross_pension_income, 2),
            "annual_income_net": round(retirement_tax["net_income"] - state_pension_at_retirement_real, 2),
            "retirement_tax": retirement_tax,
            "private_pension_replacement_pct": round(
                (gross_pension_income / primary_gross * 100) if primary_gross > 0 else 0, 1
            ),
            "state_pension": {
                "full_annual_amount": state_pension_annual,
                "state_pension_age": state_pension_age,
                "estimated_qualifying_years": projected_qualifying_years,
                "fraction_of_full": round(state_pension_fraction, 2),
                "projected_annual_real": round(state_pension_at_retirement_real, 2),
            },
            "total_retirement_income_gross": round(total_retirement_income_gross, 2),
            "total_retirement_income_net": round(total_retirement_income_net, 2),
            "income_replacement_ratio_pct": round(pension_replacement_ratio_net, 1),
            "income_replacement_ratio_gross_pct": round(pension_replacement_ratio_gross, 1),
            "years_in_retirement": years_in_retirement,
            "fund_longevity_years": round(pension_lasts_years, 1),
            "adequate": pension_adequate,
        },
        "time_horizon_allocation": time_horizon_analysis,
        "withdrawal_strategy": withdrawal_strategy,
        "glide_path": glide_path,
        "annuity_comparison": annuity_comparison,
        "isa_tracking": isa_tracking,
        "isa_note": (
            "ISA balance is zero — consider using your annual ISA allowance for tax-free growth."
            if isa == 0 else
            "Ensure you are maximising your annual ISA allowance before using taxable accounts."
        ),
        "investable_surplus_monthly": round(investable_monthly, 2),
    }

    if pension_match_analysis:
        result["pension_match_optimisation"] = pension_match_analysis
    if emergency_fund_warning:
        result["emergency_fund_warning"] = emergency_fund_warning
    if esg_note:
        result["esg_note"] = esg_note

    return result


# ---------------------------------------------------------------------------
# Fee impact analysis (IA-1)
# ---------------------------------------------------------------------------

def _fee_impact_analysis(
    isa: float, pension: float, fees_cfg: dict,
    expected_return: float, years: int,
    monthly_pension: float, surplus: float,
) -> dict:
    """Model the impact of investment fees over time."""
    isa_total_fee = fees_cfg.get("isa_platform_fee", 0) + fees_cfg.get("isa_fund_ocf", 0)
    pension_total_fee = fees_cfg.get("pension_platform_fee", 0) + fees_cfg.get("pension_fund_ocf", 0)

    # Project with and without fees
    gross_isa = _future_value(isa, 0, expected_return, years)
    net_isa = _future_value(isa, 0, expected_return - isa_total_fee, years)
    isa_fee_drag = gross_isa - net_isa

    gross_pension = _future_value(pension, monthly_pension, expected_return, years)
    net_pension = _future_value(pension, monthly_pension, expected_return - pension_total_fee, years)
    pension_fee_drag = gross_pension - net_pension

    total_fee_drag = isa_fee_drag + pension_fee_drag

    # Low-cost comparison (0.15% total)
    low_cost_fee = 0.0015
    low_cost_isa = _future_value(isa, 0, expected_return - low_cost_fee, years)
    low_cost_pension = _future_value(pension, monthly_pension, expected_return - low_cost_fee, years)
    low_cost_total = low_cost_isa + low_cost_pension

    # High-cost comparison (1.5% total)
    high_cost_fee = 0.015
    high_cost_isa = _future_value(isa, 0, expected_return - high_cost_fee, years)
    high_cost_pension = _future_value(pension, monthly_pension, expected_return - high_cost_fee, years)
    high_cost_total = high_cost_isa + high_cost_pension

    current_total = net_isa + net_pension

    return {
        "current_fees": {
            "isa_total_pct": round(isa_total_fee * 100, 3),
            "pension_total_pct": round(pension_total_fee * 100, 3),
        },
        "fee_drag_over_term": round(total_fee_drag, 2),
        "fee_comparison": {
            "current": round(current_total, 2),
            "low_cost_0_15pct": round(low_cost_total, 2),
            "high_cost_1_5pct": round(high_cost_total, 2),
            "saving_vs_high_cost": round(current_total - high_cost_total, 2),
            "cost_vs_low_cost": round(low_cost_total - current_total, 2),
        },
        "projection_years": years,
    }


# ---------------------------------------------------------------------------
# Time-horizon-based allocation (IA-2)
# ---------------------------------------------------------------------------

def _time_horizon_allocation(sav: dict, profile: dict, years_to_retirement: int) -> list[dict]:
    """Suggest allocation per account based on its time horizon."""
    goals = profile.get("goals", [])
    accounts = []

    # Emergency fund
    ef = sav.get("emergency_fund", 0)
    if ef > 0:
        accounts.append({
            "account": "Emergency Fund",
            "balance": round(ef, 2),
            "time_horizon": "Immediate",
            "years_to_use": 0,
            "suggested_allocation": "cash/money_market",
            "current_type": sav.get("emergency_fund_type", "unknown"),
            "mismatch": sav.get("emergency_fund_type", "cash") not in ("cash", "money_market"),
        })

    # LISA
    lisa = sav.get("lisa_balance", 0)
    if lisa > 0:
        property_goal = next((g for g in goals if g.get("category") == "property"), None)
        lisa_years = property_goal.get("deadline_years", 3) if property_goal else 3
        accounts.append({
            "account": "Lifetime ISA",
            "balance": round(lisa, 2),
            "time_horizon": f"{lisa_years} years (property deposit)",
            "years_to_use": lisa_years,
            "suggested_allocation": "conservative" if lisa_years <= 5 else "moderate",
            "mismatch": False,
        })

    # ISA
    isa = sav.get("isa_balance", 0)
    if isa > 0:
        accounts.append({
            "account": "Stocks & Shares ISA",
            "balance": round(isa, 2),
            "time_horizon": "Medium term",
            "years_to_use": 5,
            "suggested_allocation": "moderate",
            "mismatch": False,
        })

    # Pension
    pension = sav.get("pension_balance", 0)
    if pension > 0:
        accounts.append({
            "account": "Pension",
            "balance": round(pension, 2),
            "time_horizon": f"{years_to_retirement} years (retirement)",
            "years_to_use": years_to_retirement,
            "suggested_allocation": "aggressive" if years_to_retirement > 20 else "moderate",
            "mismatch": False,
        })

    return accounts


# ---------------------------------------------------------------------------
# Tax-efficient withdrawal sequencing (IA-4)
# ---------------------------------------------------------------------------

def _retirement_withdrawal_strategy(
    pension_real: float, isa_balance: float,
    state_pension: float, tax_cfg: dict,
) -> dict:
    """Model optimal vs naive withdrawal ordering in retirement."""
    pa = tax_cfg.get("personal_allowance", 12570)
    basic_thresh = tax_cfg.get("basic_threshold", 50270)
    target_income = 30000  # reasonable retirement income target

    # Naive: all from pension
    naive_tax = calculate_tax_on_pension_withdrawal(target_income, state_pension, tax_cfg)

    # Optimised: use ISA to fill gap, pension to fill tax bands
    pension_drawdown_to_fill_basic = max(0, basic_thresh - state_pension) * (4 / 3)  # gross up for 25% tax-free
    isa_topup = max(0, target_income - pension_drawdown_to_fill_basic - state_pension)
    optimised_pension_draw = min(pension_drawdown_to_fill_basic, target_income - state_pension)
    optimised_tax = calculate_tax_on_pension_withdrawal(optimised_pension_draw, state_pension, tax_cfg)

    annual_saving = naive_tax["income_tax"] - optimised_tax["income_tax"]

    return {
        "strategy": [
            "1. Use pension tax-free lump sum (25%) for initial expenses",
            "2. Draw from pension to fill basic rate band",
            "3. Top up from ISA (tax-free) to reach desired income",
            "4. Delay state pension if possible for higher payments",
        ],
        "naive_approach_tax": round(naive_tax["income_tax"], 2),
        "optimised_approach_tax": round(optimised_tax["income_tax"], 2),
        "annual_tax_saving": round(annual_saving, 2),
        "note": (
            "By drawing strategically from pension and ISA, you can minimise your "
            "effective tax rate in retirement."
        ),
    }


# ---------------------------------------------------------------------------
# Glide path projection (IA-5)
# ---------------------------------------------------------------------------

def _glide_path_projection(
    age: int, retirement_age: int, current_invested: float,
    monthly_contribution: float, returns_cfg: dict, inflation: float,
    glide_path_cfg: list,
) -> dict:
    """Project portfolio with age-based de-risking."""
    if not glide_path_cfg:
        return {"applicable": False}

    years_to_retirement = max(1, retirement_age - age)
    timeline = []

    balance = current_invested
    for year in range(years_to_retirement + 1):
        current_age = age + year
        equity_pct = _interpolate_equity(current_age, glide_path_cfg)
        # Blend return: equity portion gets aggressive return, bond portion gets conservative
        equity_return = returns_cfg.get("aggressive", 0.08)
        bond_return = returns_cfg.get("conservative", 0.04)
        blended_return = equity_pct * equity_return + (1 - equity_pct) * bond_return

        if year > 0:
            balance = balance * (1 + blended_return) + monthly_contribution * 12

        if year % 5 == 0 or year == years_to_retirement:
            real_balance = balance / ((1 + inflation) ** year) if year > 0 else balance
            timeline.append({
                "year": year,
                "age": current_age,
                "equity_pct": round(equity_pct * 100, 0),
                "bond_pct": round((1 - equity_pct) * 100, 0),
                "portfolio_nominal": round(balance, 2),
                "portfolio_real": round(real_balance, 2),
            })

    return {
        "applicable": True,
        "timeline": timeline,
        "note": "Consider a lifecycle/target-date fund that automatically de-risks as you approach retirement.",
    }


def _interpolate_equity(age: int, glide_path: list) -> float:
    """Interpolate equity percentage for a given age from glide path config."""
    if not glide_path:
        return 0.6

    sorted_gp = sorted(glide_path, key=lambda x: x["age"])

    if age <= sorted_gp[0]["age"]:
        return sorted_gp[0]["equity_pct"]
    if age >= sorted_gp[-1]["age"]:
        return sorted_gp[-1]["equity_pct"]

    for i in range(len(sorted_gp) - 1):
        a1, p1 = sorted_gp[i]["age"], sorted_gp[i]["equity_pct"]
        a2, p2 = sorted_gp[i + 1]["age"], sorted_gp[i + 1]["equity_pct"]
        if a1 <= age <= a2:
            progress = (age - a1) / (a2 - a1)
            return p1 + (p2 - p1) * progress

    return 0.6


# ---------------------------------------------------------------------------
# Annuity comparison (IA-9)
# ---------------------------------------------------------------------------

def _annuity_comparison(
    pension_real: float, retirement_age: int, annuity_cfg: dict,
    drawdown_income: float, state_pension: float, tax_cfg: dict,
) -> dict:
    """Compare drawdown vs annuity retirement options."""
    # Get annuity rate for retirement age
    rates = {
        60: annuity_cfg.get("rate_per_10k_age_60", 550),
        65: annuity_cfg.get("rate_per_10k_age_65", 620),
        67: annuity_cfg.get("rate_per_10k_age_67", 660),
        70: annuity_cfg.get("rate_per_10k_age_70", 720),
    }

    # Find closest rate
    closest_age = min(rates.keys(), key=lambda x: abs(x - retirement_age))
    rate_per_10k = rates[closest_age]

    annuity_income = (pension_real / 10000) * rate_per_10k
    annuity_tax = calculate_tax_on_pension_withdrawal(annuity_income, state_pension, tax_cfg)

    drawdown_tax = calculate_tax_on_pension_withdrawal(drawdown_income, state_pension, tax_cfg)

    return {
        "drawdown": {
            "annual_income_gross": round(drawdown_income, 2),
            "annual_income_net": round(drawdown_tax["net_income"] - state_pension, 2),
            "pros": ["Flexible withdrawals", "Pot inheritable", "Can adjust to needs"],
            "cons": ["Market risk", "Pot can run out", "Requires active management"],
        },
        "annuity": {
            "annual_income_gross": round(annuity_income, 2),
            "annual_income_net": round(annuity_tax["net_income"] - state_pension, 2),
            "rate_used_per_10k": rate_per_10k,
            "pros": ["Guaranteed income for life", "No investment risk", "Simple"],
            "cons": ["No inheritance", "No flexibility", "Inflation erosion without escalation"],
        },
    }


# ---------------------------------------------------------------------------
# ISA contribution tracking (IA-11)
# ---------------------------------------------------------------------------

def _isa_contribution_tracking(sav: dict) -> dict:
    """Track ISA and LISA contribution allowances."""
    isa_limit = 20000
    lisa_limit = 4000
    isa_used = sav.get("isa_contributions_this_year", 0)
    lisa_used = sav.get("lisa_contributions_this_year", 0)

    return {
        "isa_annual_limit": isa_limit,
        "isa_contributed_this_year": round(isa_used, 2),
        "isa_remaining_allowance": round(isa_limit - isa_used, 2),
        "lisa_annual_limit": lisa_limit,
        "lisa_contributed_this_year": round(lisa_used, 2),
        "lisa_remaining_allowance": round(lisa_limit - lisa_used, 2),
        "note": "Prioritise filling ISA before using taxable accounts. LISA contributions earn a 25% government bonus.",
    }


# ---------------------------------------------------------------------------
# Projection helpers
# ---------------------------------------------------------------------------

def _future_value(
    present_value: float,
    monthly_contribution: float,
    annual_return: float,
    years: int,
) -> float:
    """Calculate future value with monthly compounding and contributions."""
    if years <= 0:
        return present_value

    monthly_rate = annual_return / 12
    months = years * 12

    if monthly_rate == 0:
        return present_value + monthly_contribution * months

    compound = (1 + monthly_rate) ** months
    fv_lump = present_value * compound
    fv_annuity = monthly_contribution * ((compound - 1) / monthly_rate)
    return fv_lump + fv_annuity


def _project_growth(
    current_invested: float,
    monthly_contribution: float,
    annual_return: float,
    inflation: float,
    years_list: list[int],
) -> list[dict]:
    """Project portfolio value at multiple horizons, nominal and real."""
    results = []
    for y in years_list:
        nominal = _future_value(current_invested, monthly_contribution, annual_return, y)
        real = nominal / ((1 + inflation) ** y)
        total_contributions = current_invested + monthly_contribution * 12 * y
        growth = nominal - total_contributions
        results.append({
            "years": y,
            "nominal_value": round(nominal, 2),
            "real_value_today_terms": round(real, 2),
            "total_contributions": round(total_contributions, 2),
            "investment_growth": round(growth, 2),
        })
    return results
