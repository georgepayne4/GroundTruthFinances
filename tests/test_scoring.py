"""Tests for engine/scoring.py."""

from __future__ import annotations

from engine.cashflow import analyse_cashflow
from engine.debt import analyse_debt
from engine.goals import analyse_goals
from engine.investments import analyse_investments
from engine.mortgage import analyse_mortgage
from engine.scoring import calculate_scores


class TestScoring:
    def test_score_range(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        goals = analyse_goals(sample_profile, assumptions, cashflow, debt)
        investments = analyse_investments(sample_profile, assumptions, cashflow)
        mortgage = analyse_mortgage(sample_profile, assumptions, cashflow, debt)

        result = calculate_scores(
            sample_profile, assumptions, cashflow, debt,
            goals, investments, mortgage,
        )
        assert 0 <= result["overall_score"] <= 100

    def test_has_grade(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        goals = analyse_goals(sample_profile, assumptions, cashflow, debt)
        investments = analyse_investments(sample_profile, assumptions, cashflow)
        mortgage = analyse_mortgage(sample_profile, assumptions, cashflow, debt)

        result = calculate_scores(
            sample_profile, assumptions, cashflow, debt,
            goals, investments, mortgage,
        )
        assert result["grade"] in ("A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "F")

    def test_categories_present(self, sample_profile, assumptions):
        cashflow = analyse_cashflow(sample_profile, assumptions)
        debt = analyse_debt(sample_profile, assumptions)
        goals = analyse_goals(sample_profile, assumptions, cashflow, debt)
        investments = analyse_investments(sample_profile, assumptions, cashflow)
        mortgage = analyse_mortgage(sample_profile, assumptions, cashflow, debt)

        result = calculate_scores(
            sample_profile, assumptions, cashflow, debt,
            goals, investments, mortgage,
        )
        assert "categories" in result
        assert len(result["categories"]) > 0
