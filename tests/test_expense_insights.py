"""Tests for v5.2-09 expense micro-insights and monthly trend detection."""

from __future__ import annotations

from datetime import date

from engine.import_csv import Transaction, aggregate_monthly_totals
from engine.insights import _detect_trend, _expense_micro_insights


def _profile(
    *,
    rent: float = 0,
    mortgage: float = 0,
    groceries: float = 300,
    dining: float = 120,
    car: float = 0,
    fuel: float = 0,
    public_transport: float = 0,
    dependents: int = 0,
    subscriptions_monthly: float = 0,
    net_monthly: float = 3000,
    bank_subs: list | None = None,
    monthly_totals: dict | None = None,
) -> tuple[dict, dict]:
    """Return (profile, cashflow) pair for micro-insight testing."""
    profile = {
        "personal": {"dependents": dependents},
        "expenses": {
            "housing": {
                "rent_monthly": rent,
                "mortgage_monthly": mortgage,
                "council_tax_monthly": 150 if (rent or mortgage) else 0,
            },
            "transport": {
                "car_payment_monthly": car,
                "fuel_monthly": fuel,
                "public_transport_monthly": public_transport,
            },
            "living": {
                "groceries_monthly": groceries,
                "dining_out_monthly": dining,
                "subscriptions_monthly": subscriptions_monthly,
                "clothing_monthly": 50,
                "personal_care_monthly": 30,
            },
        },
    }
    if bank_subs is not None or monthly_totals is not None:
        profile["_bank_import"] = {
            "subscriptions": bank_subs or [],
            "monthly_totals": monthly_totals or {},
        }
    cashflow = {"net_income": {"monthly": net_monthly}}
    return profile, cashflow


# ---------------------------------------------------------------------------
# _detect_trend
# ---------------------------------------------------------------------------

class TestDetectTrend:
    def test_rising(self):
        assert _detect_trend([100, 110, 120, 130]) == "rising"

    def test_falling(self):
        assert _detect_trend([130, 120, 110, 100]) == "falling"

    def test_stable(self):
        assert _detect_trend([100, 102, 98, 101]) is None

    def test_too_few_values(self):
        assert _detect_trend([100, 110]) is None

    def test_zero_start_rising(self):
        assert _detect_trend([0, 0, 50]) == "rising"

    def test_zero_start_zero(self):
        assert _detect_trend([0, 0, 0]) is None


# ---------------------------------------------------------------------------
# aggregate_monthly_totals
# ---------------------------------------------------------------------------

class TestAggregateMonthlyTotals:
    def test_groups_by_month_and_category(self):
        txns = [
            Transaction(date(2026, 1, 5), "Tesco", -45, "monzo", category="living"),
            Transaction(date(2026, 1, 15), "Rent", -1100, "monzo", category="housing"),
            Transaction(date(2026, 2, 5), "Tesco", -50, "monzo", category="living"),
        ]
        result = aggregate_monthly_totals(txns)
        assert "2026-01" in result
        assert result["2026-01"]["living"] == 45.0
        assert result["2026-01"]["housing"] == 1100.0
        assert result["2026-02"]["living"] == 50.0

    def test_ignores_inflows(self):
        txns = [
            Transaction(date(2026, 1, 5), "Salary", 2500, "monzo", category="income"),
        ]
        assert aggregate_monthly_totals(txns) == {}

    def test_ignores_uncategorised(self):
        txns = [
            Transaction(date(2026, 1, 5), "Unknown Shop", -30, "monzo"),
        ]
        assert aggregate_monthly_totals(txns) == {}

    def test_months_sorted_ascending(self):
        txns = [
            Transaction(date(2026, 3, 1), "Rent", -1100, "monzo", category="housing"),
            Transaction(date(2026, 1, 1), "Rent", -1100, "monzo", category="housing"),
            Transaction(date(2026, 2, 1), "Rent", -1100, "monzo", category="housing"),
        ]
        result = aggregate_monthly_totals(txns)
        assert list(result.keys()) == ["2026-01", "2026-02", "2026-03"]


# ---------------------------------------------------------------------------
# _expense_micro_insights
# ---------------------------------------------------------------------------

class TestExpenseMicroInsights:
    def test_empty_expenses_not_applicable(self):
        result = _expense_micro_insights(
            {"expenses": {}, "personal": {}},
            {"net_income": {"monthly": 3000}},
        )
        assert not result.get("applicable")

    def test_housing_high_pct_flagged(self):
        p, c = _profile(rent=1500, net_monthly=3000)
        result = _expense_micro_insights(p, c)
        assert any("above" in m and "ceiling" in m for m in result["messages"])
        assert result["categories"]["housing"]["pct_of_net"] == 50.0

    def test_rent_to_own_prompt(self):
        p, c = _profile(rent=1100, net_monthly=3500)
        result = _expense_micro_insights(p, c)
        assert any("rent" in m.lower() and "equity" in m.lower() for m in result["messages"])
        assert result["categories"]["housing"]["renting"] is True

    def test_mortgage_no_rent_prompt(self):
        p, c = _profile(mortgage=1100, net_monthly=3500)
        result = _expense_micro_insights(p, c)
        renting_msgs = [m for m in result["messages"] if "equity" in m.lower()]
        assert len(renting_msgs) == 0

    def test_transport_car_and_public_insight(self):
        p, c = _profile(car=200, fuel=150, public_transport=100)
        result = _expense_micro_insights(p, c)
        assert any("car costs" in m.lower() or "public transport" in m.lower() for m in result["messages"])

    def test_transport_high_car_cost(self):
        p, c = _profile(car=300, fuel=100)
        result = _expense_micro_insights(p, c)
        assert any("car costs" in m.lower() for m in result["messages"])

    def test_groceries_per_person(self):
        p, c = _profile(groceries=600, dependents=1)
        result = _expense_micro_insights(p, c)
        assert result["categories"]["living"]["per_person_monthly"] == 300.0
        assert result["categories"]["living"]["household_size"] == 2

    def test_high_grocery_per_person_flagged(self):
        p, c = _profile(groceries=350, dependents=0)
        result = _expense_micro_insights(p, c)
        assert any("grocery" in m.lower() and "above" in m.lower() for m in result["messages"])

    def test_high_dining_pct_flagged(self):
        p, c = _profile(groceries=200, dining=250)
        result = _expense_micro_insights(p, c)
        dining_pct = result["categories"]["living"]["dining_pct_of_food"]
        assert dining_pct > 40
        assert any("dining" in m.lower() for m in result["messages"])

    def test_bank_subscriptions_surfaced(self):
        subs = [
            {"name": "Netflix", "monthly_cost": 12.99},
            {"name": "Spotify", "monthly_cost": 9.99},
        ]
        p, c = _profile(bank_subs=subs)
        result = _expense_micro_insights(p, c)
        assert result["categories"]["subscriptions"]["count"] == 2
        assert result["categories"]["subscriptions"]["monthly_total"] == 22.98

    def test_rising_trend_flagged(self):
        totals = {
            "2026-01": {"living": 400},
            "2026-02": {"living": 500},
            "2026-03": {"living": 600},
        }
        p, c = _profile(monthly_totals=totals)
        result = _expense_micro_insights(p, c)
        assert result["trends"].get("living") == "rising"
        assert any("rising" in m for m in result["messages"])

    def test_stable_trend_no_flag(self):
        totals = {
            "2026-01": {"living": 400},
            "2026-02": {"living": 410},
            "2026-03": {"living": 395},
        }
        p, c = _profile(monthly_totals=totals)
        result = _expense_micro_insights(p, c)
        assert result["trends"].get("living") is None

    def test_discretionary_total_calculated(self):
        p, c = _profile(dining=120, net_monthly=3000)
        result = _expense_micro_insights(p, c)
        assert "discretionary_monthly" in result
        assert "discretionary_pct_of_net" in result

    def test_no_net_income_skips_pct(self):
        p, c = _profile(rent=1000, net_monthly=0)
        result = _expense_micro_insights(p, c)
        assert "discretionary_pct_of_net" not in result
