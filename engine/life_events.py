"""
life_events.py — Life Event Simulation Engine

Projects financial trajectory over time by applying income changes,
one-off expenses, recurring expense changes, investment growth, and
salary growth.  Produces a year-by-year timeline showing net worth,
surplus, and goal feasibility at each point.
"""

from __future__ import annotations

from typing import Any


def simulate_life_events(
    profile: dict,
    assumptions: dict,
    cashflow: dict,
) -> dict[str, Any]:
    """
    Run a year-by-year simulation of the user's financial trajectory.

    Each year:
    1. Apply salary growth
    2. Apply any life events (income changes, one-off costs, recurring cost changes)
    3. Recalculate surplus
    4. Grow investments at expected return
    5. Pay down debt
    6. Track net worth and goal progress
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

    # Use the longer of default projection or latest life event
    if events:
        max_event_year = max(e.get("year_offset", 0) for e in events)
        projection_years = max(projection_years, max_event_year + 2)

    # Cap at years to retirement
    projection_years = min(projection_years, max(1, retirement_age - age))

    # Assumptions
    risk_profile = personal.get("risk_profile", "moderate")
    investment_return = assumptions.get("investment_returns", {}).get(risk_profile, 0.06)
    inflation = assumptions.get("inflation", {}).get("general", 0.03)
    salary_growth_key = personal.get("salary_growth_outlook", "average")
    salary_growth = assumptions.get("salary_growth", {}).get(salary_growth_key, 0.035)

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

        # Apply life events for this year
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

            # Recurring monthly expense change (permanent)
            monthly_change = ev.get("monthly_expense_change", 0)
            state.expenses_annual += monthly_change * 12

        # Apply salary growth (compounding, skip year 0)
        if year > 0:
            state.gross_annual *= (1 + salary_growth)
            # Inflate expenses
            state.expenses_annual *= (1 + inflation)

        # Calculate net income for this year
        total_income = state.gross_annual + state.other_income_annual
        net_income = total_income * (1 - state.tax_rate)
        total_outgoings = state.expenses_annual + state.debt_payments_annual
        annual_surplus = net_income - total_outgoings

        # Allocate surplus: positive → savings/investments, negative → drawdown
        if annual_surplus > 0:
            # Split: 60% to liquid savings, 40% to investments
            state.liquid_savings += annual_surplus * 0.6
            state.investments += annual_surplus * 0.4
        else:
            # Draw down liquid savings first
            drawdown = abs(annual_surplus)
            if state.liquid_savings >= drawdown:
                state.liquid_savings -= drawdown
            else:
                drawdown -= state.liquid_savings
                state.liquid_savings = 0
                state.investments = max(0, state.investments - drawdown)

        # Grow investments
        state.investments *= (1 + investment_return)

        # Reduce debt (simplified: assume minimum payments reduce balance)
        if state.total_debt > 0:
            debt_reduction = min(state.debt_payments_annual, state.total_debt)
            state.total_debt = max(0, state.total_debt - debt_reduction * 0.7)  # ~30% goes to interest

        # Net worth
        net_worth = state.liquid_savings + state.investments - state.total_debt

        timeline.append({
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
        })

    # ------------------------------------------------------------------
    # Derive summary insights
    # ------------------------------------------------------------------
    first_nw = timeline[0]["net_worth"] if timeline else 0
    last_nw = timeline[-1]["net_worth"] if timeline else 0
    peak_nw = max(t["net_worth"] for t in timeline) if timeline else 0
    trough_nw = min(t["net_worth"] for t in timeline) if timeline else 0

    # Find year when net worth first goes negative (if ever)
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
        # Find net worth at deadline year
        deadline_entry = next((t for t in timeline if t["year"] == deadline), None)
        if deadline_entry:
            # Rough check: is liquid savings at that point enough?
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

    return {
        "projection_years": projection_years,
        "timeline": timeline,
        "summary": {
            "starting_net_worth": round(first_nw, 2),
            "ending_net_worth": round(last_nw, 2),
            "peak_net_worth": round(peak_nw, 2),
            "trough_net_worth": round(trough_nw, 2),
            "net_worth_change": round(last_nw - first_nw, 2),
            "first_negative_year": negative_year,
            "cumulative_events": cumulative_events,
        },
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
        return 0.25  # fallback assumption
    return min(0.60, deductions / gross)  # cap at 60% for sanity
