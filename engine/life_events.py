"""
life_events.py — Life Event Simulation Engine

Projects financial trajectory over time by applying income changes,
one-off expenses/incomes, recurring expense changes, investment growth,
salary growth, childcare tax relief, and equity growth projection.

Supports:
- FA-3: Childcare Tax-Free Childcare top-up
- FA-4: Windfall/inheritance one_off_income events
- MA-4: Property equity growth tracking
"""

from __future__ import annotations

from typing import Any

from engine.mortgage import _monthly_repayment


def simulate_life_events(
    profile: dict,
    assumptions: dict,
    cashflow: dict,
) -> dict[str, Any]:
    """
    Run a year-by-year simulation of the user's financial trajectory.
    """
    events = profile.get("life_events", [])
    personal = profile.get("personal", {})
    sav = profile.get("savings", {})
    inc = profile.get("income", {})
    debts = profile.get("debts", [])

    age = personal.get("age", 30)
    retirement_age = personal.get("retirement_age",
                                  assumptions.get("life_events", {}).get("retirement_age", 67))
    projection_years = assumptions.get("life_events", {}).get("default_projection_years", 10)

    if events:
        max_event_year = max(e.get("year_offset", 0) for e in events)
        projection_years = max(projection_years, max_event_year + 2)

    projection_years = min(projection_years, max(1, retirement_age - age))

    # Assumptions
    risk_profile = personal.get("risk_profile", "moderate")
    investment_return = assumptions.get("investment_returns", {}).get(risk_profile, 0.06)
    inflation = assumptions.get("inflation", {}).get("general", 0.03)
    housing_growth = assumptions.get("inflation", {}).get("housing", 0.04)
    salary_growth_key = personal.get("salary_growth_outlook", "average")
    salary_growth = assumptions.get("salary_growth", {}).get(salary_growth_key, 0.035)

    # Childcare config (FA-3)
    childcare_cfg = assumptions.get("childcare", {})
    tfc_pct = childcare_cfg.get("tax_free_childcare_pct", 0.20)
    max_topup = childcare_cfg.get("max_government_topup_per_child", 2000)
    dependents = personal.get("dependents", 0)

    # Mortgage config for equity tracking (MA-4)
    mort = profile.get("mortgage", {})
    mort_cfg = assumptions.get("mortgage", {})

    # ------------------------------------------------------------------
    # Initial state
    # ------------------------------------------------------------------
    state = _SimState(
        gross_annual=inc.get("primary_gross_annual", 0) + inc.get("partner_gross_annual", 0),
        other_income_annual=(
            inc.get("side_income_monthly", 0) * 12
            + inc.get("rental_income_monthly", 0) * 12
            + inc.get("investment_income_annual", 0)
        ),
        expenses_annual=cashflow.get("expenses", {}).get("total_annual", 0),
        debt_payments_annual=cashflow.get("debt_servicing", {}).get("total_annual", 0),
        liquid_savings=sav.get("_total_liquid", 0),
        investments=sav.get("pension_balance", 0) + sav.get("other_investments", 0),
        total_debt=profile.get("_debt_summary", {}).get("total_balance", 0),
        tax_rate=_effective_tax_rate(cashflow),
    )

    # Property tracking (MA-4)
    property_value = 0.0
    mortgage_balance = 0.0
    mortgage_rate = 0.0
    mortgage_term = 0
    owns_property = False
    num_children = dependents
    childcare_savings_total = 0.0

    # Build event lookup by year offset
    event_map: dict[int, list[dict]] = {}
    for e in events:
        yr = e.get("year_offset", 0)
        event_map.setdefault(yr, []).append(e)

    # ------------------------------------------------------------------
    # Year-by-year simulation
    # ------------------------------------------------------------------
    timeline: list[dict] = []
    cumulative_events: list[str] = []

    for year in range(0, projection_years + 1):
        year_events = event_map.get(year, [])
        event_descriptions = []
        year_childcare_saving = 0.0

        for ev in year_events:
            desc = ev.get("description", "Unknown event")
            event_descriptions.append(desc)
            cumulative_events.append(f"Year {year}: {desc}")

            # Income change (permanent, ongoing)
            income_change = ev.get("income_change_annual", 0)
            state.gross_annual += income_change

            # One-off expense (deducted from liquid savings)
            one_off = ev.get("one_off_expense", 0)
            state.liquid_savings -= one_off

            # FA-4: One-off income / windfall (added to liquid savings)
            one_off_income = ev.get("one_off_income", 0)
            state.liquid_savings += one_off_income

            # Recurring monthly expense change (permanent)
            monthly_change = ev.get("monthly_expense_change", 0)

            # FA-3: Apply childcare tax relief
            ev_type = ev.get("type", "")
            if ev_type == "childcare" and monthly_change > 0:
                annual_childcare = monthly_change * 12
                # Count children (track from "First child" events)
                children_for_relief = max(1, num_children)
                gov_topup = min(annual_childcare * tfc_pct, max_topup * children_for_relief)
                effective_annual = annual_childcare - gov_topup
                year_childcare_saving = gov_topup
                childcare_savings_total += gov_topup
                state.expenses_annual += effective_annual
            else:
                state.expenses_annual += monthly_change * 12

            # Track child events for dependents count
            if "child" in desc.lower() and "childcare" not in desc.lower():
                num_children += 1

            # MA-4: Track property purchase
            if "home" in desc.lower() or "property" in desc.lower() or "purchase" in desc.lower():
                if mort:
                    property_value = mort.get("target_property_value", 0)
                    deposit_pct = mort.get("preferred_deposit_pct", 0.15)
                    mortgage_balance = property_value * (1 - deposit_pct)
                    mortgage_rate = assumptions.get("mortgage", {}).get("stress_test_rate", 0.07) - 0.02
                    mortgage_term = mort.get("preferred_term_years", 25)
                    owns_property = True

        # Apply salary growth (compounding, skip year 0)
        if year > 0:
            state.gross_annual *= (1 + salary_growth)
            state.expenses_annual *= (1 + inflation)

        # Calculate net income for this year
        total_income = state.gross_annual + state.other_income_annual
        net_income = total_income * (1 - state.tax_rate)
        total_outgoings = state.expenses_annual + state.debt_payments_annual
        annual_surplus = net_income - total_outgoings

        # Allocate surplus
        if annual_surplus > 0:
            state.liquid_savings += annual_surplus * 0.6
            state.investments += annual_surplus * 0.4
        else:
            drawdown = abs(annual_surplus)
            if state.liquid_savings >= drawdown:
                state.liquid_savings -= drawdown
            else:
                drawdown -= state.liquid_savings
                state.liquid_savings = 0
                state.investments = max(0, state.investments - drawdown)

        # Grow investments
        state.investments *= (1 + investment_return)

        # Reduce debt
        if state.total_debt > 0:
            debt_reduction = min(state.debt_payments_annual, state.total_debt)
            state.total_debt = max(0, state.total_debt - debt_reduction * 0.7)

        # MA-4: Property equity tracking
        equity = 0.0
        if owns_property and property_value > 0:
            property_value *= (1 + housing_growth)
            if mortgage_balance > 0 and mortgage_rate > 0 and mortgage_term > 0:
                monthly_payment = _monthly_repayment(mortgage_balance, mortgage_rate, mortgage_term)
                annual_payment = monthly_payment * 12
                annual_interest = mortgage_balance * mortgage_rate
                principal_paid = max(0, annual_payment - annual_interest)
                mortgage_balance = max(0, mortgage_balance - principal_paid)
            equity = property_value - mortgage_balance

        # Net worth
        net_worth = state.liquid_savings + state.investments - state.total_debt + equity

        entry = {
            "year": year,
            "age": age + year,
            "events": event_descriptions if event_descriptions else None,
            "gross_income_annual": round(state.gross_annual + state.other_income_annual, 2),
            "net_income_annual": round(net_income, 2),
            "expenses_annual": round(state.expenses_annual, 2),
            "debt_payments_annual": round(state.debt_payments_annual, 2),
            "annual_surplus": round(annual_surplus, 2),
            "liquid_savings": round(state.liquid_savings, 2),
            "investments": round(state.investments, 2),
            "total_debt": round(state.total_debt, 2),
            "net_worth": round(net_worth, 2),
        }

        if owns_property:
            entry["property_value"] = round(property_value, 2)
            entry["mortgage_balance"] = round(mortgage_balance, 2)
            entry["equity"] = round(equity, 2)

        if year_childcare_saving > 0:
            entry["childcare_tax_relief"] = round(year_childcare_saving, 2)

        timeline.append(entry)

    # ------------------------------------------------------------------
    # Derive summary insights
    # ------------------------------------------------------------------
    first_nw = timeline[0]["net_worth"] if timeline else 0
    last_nw = timeline[-1]["net_worth"] if timeline else 0
    peak_nw = max(t["net_worth"] for t in timeline) if timeline else 0
    trough_nw = min(t["net_worth"] for t in timeline) if timeline else 0

    negative_year = None
    for t in timeline:
        if t["net_worth"] < 0:
            negative_year = t["year"]
            break

    # Goal feasibility check at end of projection
    goals = profile.get("goals", [])
    goal_feasibility = []
    for g in goals:
        deadline = g.get("deadline_years", 0)
        target = g.get("target_amount", 0)
        deadline_entry = next((t for t in timeline if t["year"] == deadline), None)
        if deadline_entry:
            available = deadline_entry["liquid_savings"]
            feasible = available >= target
        else:
            feasible = None
        goal_feasibility.append({
            "name": g.get("name", "Unknown"),
            "target": target,
            "deadline_year": deadline,
            "projected_liquid_at_deadline": round(deadline_entry["liquid_savings"], 2) if deadline_entry else None,
            "likely_feasible": feasible,
        })

    summary = {
        "starting_net_worth": round(first_nw, 2),
        "ending_net_worth": round(last_nw, 2),
        "peak_net_worth": round(peak_nw, 2),
        "trough_net_worth": round(trough_nw, 2),
        "net_worth_change": round(last_nw - first_nw, 2),
        "first_negative_year": negative_year,
        "cumulative_events": cumulative_events,
    }

    if childcare_savings_total > 0:
        summary["total_childcare_tax_relief"] = round(childcare_savings_total, 2)

    return {
        "projection_years": projection_years,
        "timeline": timeline,
        "summary": summary,
        "goal_feasibility_at_deadline": goal_feasibility,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class _SimState:
    """Mutable state container for the simulation loop."""
    def __init__(
        self,
        gross_annual: float,
        other_income_annual: float,
        expenses_annual: float,
        debt_payments_annual: float,
        liquid_savings: float,
        investments: float,
        total_debt: float,
        tax_rate: float,
    ):
        self.gross_annual = gross_annual
        self.other_income_annual = other_income_annual
        self.expenses_annual = expenses_annual
        self.debt_payments_annual = debt_payments_annual
        self.liquid_savings = liquid_savings
        self.investments = investments
        self.total_debt = total_debt
        self.tax_rate = tax_rate


def _effective_tax_rate(cashflow: dict) -> float:
    """Derive effective tax rate from cashflow analysis."""
    gross = cashflow.get("income", {}).get("total_gross_annual", 0)
    deductions = cashflow.get("deductions", {}).get("total_deductions_annual", 0)
    if gross <= 0:
        return 0.25
    return min(0.60, deductions / gross)
