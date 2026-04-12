"""Tests for engine/risk_profiling.py — dynamic goal-specific risk profiling (v8.4)."""

from __future__ import annotations

from engine.cashflow import analyse_cashflow
from engine.debt import analyse_debt
from engine.goals import analyse_goals
from engine.investments import analyse_investments
from engine.risk_profiling import (
    _calculate_capacity_for_loss,
    _calculate_need_for_return,
    _determine_goal_risk,
    _resolve_effective_profile,
    assess_risk_profiles,
)

# ---------------------------------------------------------------------------
# Edge cases first
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_zero_deadline_conservative(self):
        goal = {"name": "Instant", "deadline_years": 0, "category": "general"}
        result = _determine_goal_risk(goal, "aggressive", {})
        assert result["recommended_profile"] == "conservative"

    def test_no_goals_empty_result(self, sample_profile, assumptions):
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {"name": "No Goals", "age": 30, "retirement_age": 67},
            "income": {"primary_gross_annual": 50000},
            "expenses": {"housing": {"rent_monthly": 1000}},
            "savings": {"emergency_fund": 5000},
            "debts": [],
            "goals": [],
        })
        cashflow = analyse_cashflow(profile, assumptions)
        debt = analyse_debt(profile, assumptions)
        goal_result = analyse_goals(profile, assumptions, cashflow, debt)
        result = assess_risk_profiles(profile, assumptions, cashflow, goal_result)
        assert result["goal_risk_profiles"] == []
        assert result["mismatches"] == []

    def test_zero_emergency_fund(self):
        profile = {"savings": {"emergency_fund": 0}}
        cashflow = {"expenses": {"monthly": 2000}}
        result = _calculate_capacity_for_loss(profile, cashflow, {})
        assert result["affordable_drawdown_pct"] == 0.05
        assert result["supports_profile"] == "conservative"

    def test_zero_target_need_for_return(self):
        goal = {"target_amount": 0, "deadline_years": 5}
        result = _calculate_need_for_return(goal, 1000, 0.03, {})
        assert result["required_real_return_pct"] == 0.0
        assert result["achievable"] is True

    def test_zero_savings_zero_allocated(self):
        goal = {"target_amount": 10000, "deadline_years": 5, "allocated_monthly": 0}
        result = _calculate_need_for_return(goal, 0, 0.03, {"conservative": 0.04})
        assert result["achievable"] is False


# ---------------------------------------------------------------------------
# Goal risk determination
# ---------------------------------------------------------------------------


class TestGoalRisk:
    def test_short_term_gets_conservative(self):
        goal = {"name": "Course", "deadline_years": 1, "category": "education"}
        result = _determine_goal_risk(goal, "very_aggressive", {})
        assert result["recommended_profile"] == "conservative"
        assert result["horizon_category"] == "short"

    def test_three_year_gets_conservative(self):
        goal = {"name": "Car", "deadline_years": 3, "category": "lifestyle"}
        result = _determine_goal_risk(goal, "aggressive", {})
        assert result["recommended_profile"] == "conservative"

    def test_medium_term_gets_moderate(self):
        goal = {"name": "Fund", "deadline_years": 10, "category": "general"}
        result = _determine_goal_risk(goal, "aggressive", {})
        assert result["recommended_profile"] == "moderate"
        assert result["horizon_category"] == "medium"

    def test_long_term_allows_aggressive(self):
        goal = {"name": "Retirement", "deadline_years": 20, "category": "general"}
        result = _determine_goal_risk(goal, "aggressive", {})
        assert result["recommended_profile"] == "aggressive"
        assert result["horizon_category"] == "long"

    def test_safety_net_always_conservative(self):
        goal = {"name": "Emergency", "deadline_years": 20, "category": "safety_net"}
        result = _determine_goal_risk(goal, "very_aggressive", {})
        assert result["recommended_profile"] == "conservative"

    def test_custom_thresholds(self):
        cfg = {"short_term_years": 3, "long_term_years": 10}
        goal = {"name": "Test", "deadline_years": 4, "category": "general"}
        result = _determine_goal_risk(goal, "aggressive", cfg)
        assert result["recommended_profile"] == "moderate"


# ---------------------------------------------------------------------------
# Capacity for loss
# ---------------------------------------------------------------------------


class TestCapacityForLoss:
    def test_full_emergency_fund(self):
        profile = {"savings": {"emergency_fund": 15000, "pension_balance": 100000}}
        cashflow = {"expenses": {"monthly": 2000}}
        result = _calculate_capacity_for_loss(profile, cashflow, {})
        assert result["affordable_drawdown_pct"] == 0.20
        assert result["supports_profile"] == "aggressive"
        assert result["emergency_months"] == 7.5

    def test_moderate_emergency_fund(self):
        profile = {"savings": {"emergency_fund": 6000}}
        cashflow = {"expenses": {"monthly": 2000}}
        result = _calculate_capacity_for_loss(profile, cashflow, {})
        assert result["affordable_drawdown_pct"] == 0.10
        assert result["supports_profile"] == "moderate"

    def test_low_emergency_fund(self):
        profile = {"savings": {"emergency_fund": 1000}}
        cashflow = {"expenses": {"monthly": 2000}}
        result = _calculate_capacity_for_loss(profile, cashflow, {})
        assert result["affordable_drawdown_pct"] == 0.05
        assert result["supports_profile"] == "conservative"

    def test_narrative_contains_values(self):
        profile = {"savings": {"emergency_fund": 12000}}
        cashflow = {"expenses": {"monthly": 2000}}
        result = _calculate_capacity_for_loss(profile, cashflow, {})
        assert "20%" in result["narrative"]
        assert "6.0" in result["narrative"]


# ---------------------------------------------------------------------------
# Need for return
# ---------------------------------------------------------------------------


class TestNeedForReturn:
    def test_achievable_at_conservative(self):
        goal = {"target_amount": 5000, "deadline_years": 10}
        returns = {"conservative": 0.04, "moderate": 0.06, "aggressive": 0.08}
        result = _calculate_need_for_return(goal, 4000, 0.03, returns)
        assert result["achievable"] is True

    def test_requires_aggressive(self):
        goal = {"target_amount": 15000, "deadline_years": 10}
        returns = {"conservative": 0.04, "moderate": 0.06, "aggressive": 0.08, "very_aggressive": 0.10}
        result = _calculate_need_for_return(goal, 8000, 0.03, returns)
        assert result["achievable"] is True
        assert result["minimum_profile"] in ("aggressive", "very_aggressive")

    def test_not_achievable(self):
        goal = {"target_amount": 1000000, "deadline_years": 2}
        returns = {"conservative": 0.04, "moderate": 0.06, "aggressive": 0.08, "very_aggressive": 0.10}
        result = _calculate_need_for_return(goal, 100, 0.03, returns)
        assert result["achievable"] is False

    def test_zero_current_savings_with_contributions(self):
        goal = {"target_amount": 5000, "deadline_years": 5, "allocated_monthly": 80}
        returns = {"conservative": 0.04, "moderate": 0.06}
        result = _calculate_need_for_return(goal, 0, 0.03, returns)
        assert result["required_real_return_pct"] >= 0


# ---------------------------------------------------------------------------
# Effective profile resolution
# ---------------------------------------------------------------------------


class TestEffectiveProfile:
    def test_horizon_is_ceiling(self):
        result = _resolve_effective_profile("conservative", "aggressive", "very_aggressive")
        assert result == "conservative"

    def test_capacity_can_lower(self):
        result = _resolve_effective_profile("aggressive", "conservative", "moderate")
        assert result == "conservative"

    def test_need_pushes_up_within_ceiling(self):
        # Horizon=aggressive, capacity=aggressive, need=moderate → moderate (need within ceiling)
        result = _resolve_effective_profile("aggressive", "aggressive", "moderate")
        assert result == "moderate"

    def test_all_agree(self):
        result = _resolve_effective_profile("moderate", "moderate", "moderate")
        assert result == "moderate"

    def test_need_cannot_exceed_horizon(self):
        result = _resolve_effective_profile("moderate", "aggressive", "very_aggressive")
        assert result == "moderate"


# ---------------------------------------------------------------------------
# Mismatch detection
# ---------------------------------------------------------------------------


class TestMismatchDetection:
    def test_short_term_aggressive_is_warning(self, sample_profile, assumptions):
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {"name": "Risky", "age": 30, "retirement_age": 67,
                         "risk_profile": "aggressive"},
            "income": {"primary_gross_annual": 50000},
            "expenses": {"housing": {"rent_monthly": 1000}},
            "savings": {"emergency_fund": 20000},
            "debts": [],
            "goals": [
                {"name": "Short goal", "target_amount": 5000, "deadline_years": 2,
                 "priority": "high", "category": "general"},
            ],
        })
        cashflow = analyse_cashflow(profile, assumptions)
        debt = analyse_debt(profile, assumptions)
        goal_result = analyse_goals(profile, assumptions, cashflow, debt)
        result = assess_risk_profiles(profile, assumptions, cashflow, goal_result)
        warnings = [m for m in result["mismatches"] if m["severity"] == "warning"]
        assert len(warnings) >= 1
        assert "Short goal" in warnings[0]["message"]

    def test_aligned_no_mismatch(self, assumptions):
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {"name": "Safe", "age": 30, "retirement_age": 67,
                         "risk_profile": "conservative"},
            "income": {"primary_gross_annual": 50000},
            "expenses": {"housing": {"rent_monthly": 1000}},
            "savings": {"emergency_fund": 5000},
            "debts": [],
            "goals": [
                {"name": "Slow goal", "target_amount": 5000, "deadline_years": 2,
                 "priority": "high", "category": "general"},
            ],
        })
        cashflow = analyse_cashflow(profile, assumptions)
        debt = analyse_debt(profile, assumptions)
        goal_result = analyse_goals(profile, assumptions, cashflow, debt)
        result = assess_risk_profiles(profile, assumptions, cashflow, goal_result)
        warnings = [m for m in result["mismatches"] if m["severity"] == "warning"]
        assert len(warnings) == 0


# ---------------------------------------------------------------------------
# Full integration
# ---------------------------------------------------------------------------


class TestPipelineIntegration:
    def test_risk_profiling_in_report(self, sample_profile, assumptions):
        from engine.pipeline import run_pipeline
        report, _, _ = run_pipeline(sample_profile, assumptions_override=assumptions)
        assert "risk_profiling" in report
        rp = report["risk_profiling"]
        assert "goal_risk_profiles" in rp
        assert "capacity_for_loss" in rp
        assert "mismatches" in rp

    def test_output_structure(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        goal_result = analyse_goals(sample_profile, assumptions, cashflow, debt)
        result = assess_risk_profiles(sample_profile, assumptions, cashflow, goal_result)
        assert "personal_risk_profile" in result
        assert "capacity_for_loss" in result
        assert "goal_risk_profiles" in result
        assert "mismatches" in result
        assert "summary" in result
        assert result["summary"]["goals_assessed"] == len(result["goal_risk_profiles"])

    def test_goal_profiles_have_required_fields(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        goal_result = analyse_goals(sample_profile, assumptions, cashflow, debt)
        result = assess_risk_profiles(sample_profile, assumptions, cashflow, goal_result)
        for gp in result["goal_risk_profiles"]:
            assert "goal_name" in gp
            assert "deadline_years" in gp
            assert "horizon_category" in gp
            assert "recommended_profile" in gp
            assert "effective_profile" in gp
            assert "need_for_return" in gp
            assert "mismatch" in gp

    def test_investments_accepts_risk_profiling(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        goal_result = analyse_goals(sample_profile, assumptions, cashflow, debt)
        rp = assess_risk_profiles(sample_profile, assumptions, cashflow, goal_result)
        inv = analyse_investments(sample_profile, assumptions, cashflow, goal_result, rp)
        assert "goal_risk_profiles" in inv
        assert inv["goal_risk_profiles"]["mismatches"] == rp["mismatches"]

    def test_backward_compat_without_risk_profiling(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        inv = analyse_investments(sample_profile, assumptions, cashflow)
        assert "goal_risk_profiles" not in inv
