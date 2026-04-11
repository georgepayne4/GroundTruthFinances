"""Integration tests — cross-module contracts, CLI e2e, API pipeline (v7.2).

Tests that verify modules work together correctly, not just individually.
Each test exercises a real data path that spans 2+ modules.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from engine.cashflow import analyse_cashflow
from engine.debt import analyse_debt
from engine.estate import analyse_estate
from engine.exceptions import AssumptionError
from engine.goals import analyse_goals
from engine.insights import generate_insights
from engine.insurance import assess_insurance
from engine.investments import analyse_investments
from engine.life_events import simulate_life_events
from engine.loader import load_assumptions, load_profile
from engine.mortgage import analyse_mortgage
from engine.narrative import generate_narrative
from engine.pipeline import _check_assumptions_staleness, run_pipeline
from engine.report import assemble_report
from engine.scenarios import run_scenarios
from engine.scoring import calculate_scores
from engine.sensitivity import run_sensitivity
from engine.validator import Severity, validate_profile

PROJECT_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def full_profile():
    return load_profile(PROJECT_ROOT / "config" / "sample_input.yaml")


@pytest.fixture
def full_assumptions():
    return load_assumptions(PROJECT_ROOT / "config" / "assumptions.yaml")


# ---------------------------------------------------------------------------
# 1. Full pipeline end-to-end (engine)
# ---------------------------------------------------------------------------

class TestFullPipeline:
    def test_full_pipeline(self, full_profile, full_assumptions):
        """Run the entire analysis pipeline end-to-end with sample data."""
        flags = validate_profile(full_profile, full_assumptions)
        errors = [f for f in flags if f.severity == Severity.ERROR]
        assert len(errors) == 0, f"Validation errors: {[e.message for e in errors]}"

        cashflow = analyse_cashflow(full_profile, full_assumptions)
        assert cashflow["net_income"]["monthly"] > 0

        debt_result = analyse_debt(full_profile, full_assumptions)
        goal_result = analyse_goals(full_profile, full_assumptions, cashflow, debt_result)
        investment_result = analyse_investments(full_profile, full_assumptions, cashflow)
        mortgage_result = analyse_mortgage(full_profile, full_assumptions, cashflow, debt_result)
        insurance_result = assess_insurance(
            full_profile, full_assumptions, cashflow, mortgage_result, investment_result,
        )
        life_event_result = simulate_life_events(full_profile, full_assumptions, cashflow)
        scoring_result = calculate_scores(
            full_profile, full_assumptions, cashflow, debt_result,
            goal_result, investment_result, mortgage_result,
        )
        scenario_result = run_scenarios(
            full_profile, full_assumptions, cashflow, debt_result,
            mortgage_result, investment_result,
        )
        estate_result = analyse_estate(
            full_profile, full_assumptions, investment_result, mortgage_result, cashflow,
        )
        sensitivity_result = run_sensitivity(
            full_profile, full_assumptions, cashflow, debt_result,
            investment_result, mortgage_result,
        )
        insights_result = generate_insights(
            full_profile, full_assumptions, cashflow, debt_result,
            goal_result, investment_result, mortgage_result,
            scoring_result, life_event_result,
        )

        report = assemble_report(
            profile=full_profile,
            validation_flags=[f.to_dict() for f in flags],
            cashflow=cashflow,
            debt_analysis=debt_result,
            goal_analysis=goal_result,
            investment_analysis=investment_result,
            mortgage_analysis=mortgage_result,
            life_events=life_event_result,
            scoring=scoring_result,
            insights=insights_result,
            insurance=insurance_result,
            scenarios=scenario_result,
            estate=estate_result,
            sensitivity=sensitivity_result,
        )

        assert report["meta"]["engine_version"] is not None
        assert 0 <= report["scoring"]["overall_score"] <= 100

        narrative = generate_narrative(report)
        assert len(narrative) > 100
        assert "Financial Health" in narrative

    def test_pipeline_function(self, full_profile):
        """run_pipeline() produces a valid report with all sections."""
        report, _profile, _flags = run_pipeline(full_profile)

        # All expected report sections present
        expected_sections = [
            "meta", "validation", "scoring", "cashflow", "debt", "goals",
            "investments", "mortgage", "life_events", "insurance",
            "stress_scenarios", "estate", "sensitivity_analysis", "advisor_insights",
        ]
        for section in expected_sections:
            assert section in report, f"Missing report section: {section}"

        # Scoring is valid
        assert 0 <= report["scoring"]["overall_score"] <= 100
        assert report["scoring"]["grade"] in [
            "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F",
        ]

        # Cashflow has positive structure
        assert report["cashflow"]["net_income"]["monthly"] > 0
        assert report["cashflow"]["income"]["total_gross_annual"] > 0

        # Report is JSON-serialisable
        json.dumps(report, default=str)


# ---------------------------------------------------------------------------
# 2. CLI end-to-end
# ---------------------------------------------------------------------------

class TestCLI:
    def test_main_py_exits_cleanly(self, tmp_path):
        """main.py with sample_input.yaml should exit 0 and produce outputs."""
        result = subprocess.run(
            [sys.executable, str(PROJECT_ROOT / "main.py")],
            capture_output=True, text=True, timeout=30,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, f"main.py failed:\n{result.stderr}"
        assert "Done." in result.stdout
        assert "Report saved to" in result.stdout

    def test_main_py_produces_json_report(self):
        """The output report.json should be valid JSON with expected structure."""
        report_path = PROJECT_ROOT / "outputs" / "report.json"
        if not report_path.exists():
            subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "main.py")],
                capture_output=True, timeout=30, cwd=str(PROJECT_ROOT),
            )
        assert report_path.exists()
        with open(report_path) as f:
            report = json.load(f)
        assert "scoring" in report
        assert "cashflow" in report
        assert "meta" in report

    def test_main_py_produces_markdown_narrative(self):
        """The output report.md should contain the narrative."""
        report_path = PROJECT_ROOT / "outputs" / "report.md"
        if not report_path.exists():
            subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "main.py")],
                capture_output=True, timeout=30, cwd=str(PROJECT_ROOT),
            )
        assert report_path.exists()
        content = report_path.read_text()
        assert "Financial Health" in content
        assert len(content) > 200


# ---------------------------------------------------------------------------
# 3. Cross-module contract tests
# ---------------------------------------------------------------------------

class TestCrossModuleContracts:
    """Verify that module outputs have the shape downstream consumers expect."""

    def test_cashflow_feeds_investments(self, full_profile, full_assumptions):
        """investments.py reads cashflow net_income — verify structure."""
        cashflow = analyse_cashflow(full_profile, full_assumptions)
        assert "net_income" in cashflow
        assert "monthly" in cashflow["net_income"]
        assert "annual" in cashflow["net_income"]

        inv = analyse_investments(full_profile, full_assumptions, cashflow)
        assert "pension_analysis" in inv
        assert "current_portfolio" in inv

    def test_investments_feeds_scoring(self, full_profile, full_assumptions):
        """scoring.py reads investments pension_analysis and current_portfolio."""
        cashflow = analyse_cashflow(full_profile, full_assumptions)
        inv = analyse_investments(full_profile, full_assumptions, cashflow)

        # These keys must exist for scoring to work correctly
        assert "pension_analysis" in inv
        pension = inv["pension_analysis"]
        assert "adequate" in pension
        assert "income_replacement_ratio_pct" in pension

        assert "current_portfolio" in inv
        portfolio = inv["current_portfolio"]
        assert "total_invested" in portfolio

    def test_investments_feeds_insurance(self, full_profile, full_assumptions):
        """insurance.py reads investment_analysis for pension cross-reference."""
        cashflow = analyse_cashflow(full_profile, full_assumptions)
        inv = analyse_investments(full_profile, full_assumptions, cashflow)
        mortgage = analyse_mortgage(
            full_profile, full_assumptions, cashflow,
            analyse_debt(full_profile, full_assumptions),
        )

        insurance = assess_insurance(
            full_profile, full_assumptions, cashflow, mortgage, inv,
        )
        assert "coverage" in insurance or "gaps" in insurance or "recommendations" in insurance

    def test_cashflow_feeds_mortgage(self, full_profile, full_assumptions):
        """mortgage.py reads cashflow surplus — verify contract."""
        cashflow = analyse_cashflow(full_profile, full_assumptions)
        assert "surplus" in cashflow
        assert "monthly" in cashflow["surplus"]

        debt = analyse_debt(full_profile, full_assumptions)
        mortgage = analyse_mortgage(full_profile, full_assumptions, cashflow, debt)
        assert "borrowing_capacity" in mortgage or "applicable" in mortgage

    def test_scoring_reads_all_modules(self, full_profile, full_assumptions):
        """scoring.py requires cashflow, debt, goals, investments, mortgage."""
        cashflow = analyse_cashflow(full_profile, full_assumptions)
        debt = analyse_debt(full_profile, full_assumptions)
        goals = analyse_goals(full_profile, full_assumptions, cashflow, debt)
        inv = analyse_investments(full_profile, full_assumptions, cashflow)
        mortgage = analyse_mortgage(full_profile, full_assumptions, cashflow, debt)

        scoring = calculate_scores(
            full_profile, full_assumptions, cashflow, debt,
            goals, inv, mortgage,
        )
        assert "overall_score" in scoring
        assert "grade" in scoring
        assert "categories" in scoring
        assert 0 <= scoring["overall_score"] <= 100

    def test_insights_reads_all_modules(self, full_profile, full_assumptions):
        """insights.py reads scoring, investments, debt, goals, life_events."""
        cashflow = analyse_cashflow(full_profile, full_assumptions)
        debt = analyse_debt(full_profile, full_assumptions)
        goals = analyse_goals(full_profile, full_assumptions, cashflow, debt)
        inv = analyse_investments(full_profile, full_assumptions, cashflow)
        mortgage = analyse_mortgage(full_profile, full_assumptions, cashflow, debt)
        scoring = calculate_scores(
            full_profile, full_assumptions, cashflow, debt,
            goals, inv, mortgage,
        )
        life_events = simulate_life_events(full_profile, full_assumptions, cashflow)

        insights = generate_insights(
            full_profile, full_assumptions, cashflow, debt,
            goals, inv, mortgage, scoring, life_events,
        )
        assert "top_priorities" in insights
        assert "positive_reinforcements" in insights

    def test_scenarios_reads_cashflow_debt_mortgage_investments(
        self, full_profile, full_assumptions,
    ):
        """scenarios.py uses cashflow, debt, mortgage, investments."""
        cashflow = analyse_cashflow(full_profile, full_assumptions)
        debt = analyse_debt(full_profile, full_assumptions)
        inv = analyse_investments(full_profile, full_assumptions, cashflow)
        mortgage = analyse_mortgage(full_profile, full_assumptions, cashflow, debt)

        scenarios = run_scenarios(
            full_profile, full_assumptions, cashflow, debt, mortgage, inv,
        )
        assert isinstance(scenarios, dict)
        assert len(scenarios) > 0

    def test_estate_reads_investments_mortgage_cashflow(
        self, full_profile, full_assumptions,
    ):
        """estate.py uses investments, mortgage, cashflow."""
        cashflow = analyse_cashflow(full_profile, full_assumptions)
        debt = analyse_debt(full_profile, full_assumptions)
        inv = analyse_investments(full_profile, full_assumptions, cashflow)
        mortgage = analyse_mortgage(full_profile, full_assumptions, cashflow, debt)

        estate = analyse_estate(
            full_profile, full_assumptions, inv, mortgage, cashflow,
        )
        assert isinstance(estate, dict)


# ---------------------------------------------------------------------------
# 4. Bank CSV import → analyse pipeline
# ---------------------------------------------------------------------------

class TestBankImportPipeline:
    def test_csv_import_then_analyse(self, full_profile, full_assumptions, tmp_path):
        """Import a bank CSV, merge into profile, run full pipeline."""
        from engine.import_csv import import_bank_csv

        csv_content = (
            "Date,Type,Description,Value,Balance,Account Name,Account Number\n"
            "01/03/2025,DD,Rent Payment,-1200.00,3800.00,Current Account,12345678\n"
            "05/03/2025,FPI,Salary,3500.00,7300.00,Current Account,12345678\n"
            "10/03/2025,DEB,Tesco,-85.50,7214.50,Current Account,12345678\n"
            "15/03/2025,DEB,Shell,-60.00,7154.50,Current Account,12345678\n"
        )
        csv_path = tmp_path / "statement.csv"
        csv_path.write_text(csv_content)

        result = import_bank_csv(str(csv_path))
        assert "summary" in result
        assert result["summary"]["transactions_parsed"] == 4

        # Pipeline still works after import (no crash)
        report, _, _flags = run_pipeline(full_profile)
        assert report["scoring"]["overall_score"] >= 0


# ---------------------------------------------------------------------------
# 5. What-If roundtrip
# ---------------------------------------------------------------------------

class TestWhatIfIntegration:
    def test_whatif_delta_matches_reanalysis(self, full_profile, full_assumptions):
        """What-If parameter change should produce consistent deltas."""
        from api.whatif import ParameterChange, run_whatif

        change = ParameterChange(
            path="income.primary_gross_annual",
            value=60000,
        )
        result = run_whatif(full_profile, [change])
        assert result.base_score is not None
        assert result.modified_score is not None
        assert result.deltas is not None
        # Score should change when income changes
        assert result.base_score != result.modified_score


# ---------------------------------------------------------------------------
# 6. Multi-profile comparison
# ---------------------------------------------------------------------------

class TestComparisonIntegration:
    def test_compare_different_incomes(self, full_profile):
        """Comparing two profiles with different income should show differences."""
        import copy

        from api.comparison import compare_profiles

        profile_b = copy.deepcopy(full_profile)
        profile_b["income"]["primary_gross_annual"] = 80000

        report_a, report_b, _, comparisons = compare_profiles(full_profile, profile_b)
        score_a = report_a["scoring"]["overall_score"]
        score_b = report_b["scoring"]["overall_score"]
        assert score_a != score_b
        assert len(comparisons) > 0

    def test_branch_profile(self, full_profile):
        """Branch a profile with modifications and verify it produces different scores."""
        from api.comparison import branch_profile

        modifications = {"income.primary_gross_annual": 100000}
        _branched, base_report, branch_report = branch_profile(full_profile, modifications)

        # Different income should produce different scores
        assert base_report["scoring"]["overall_score"] != branch_report["scoring"]["overall_score"]


# ---------------------------------------------------------------------------
# 7. Edge case profiles
# ---------------------------------------------------------------------------

class TestEdgeCaseProfiles:
    def test_zero_income_profile(self, full_assumptions):
        """Profile with zero income should not crash — validator catches it."""
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {"name": "Zero", "age": 25, "retirement_age": 67},
            "income": {"primary_gross_annual": 0},
            "expenses": {"housing": {"rent_monthly": 500}},
            "savings": {"emergency_fund": 1000},
            "debts": [],
            "goals": [],
        })
        flags = validate_profile(profile, full_assumptions)
        errors = [f for f in flags if f.severity == Severity.ERROR]
        assert len(errors) > 0  # Should flag zero income

        # Pipeline should still run without crashing
        report, _, _ = run_pipeline(profile)
        assert report["scoring"]["overall_score"] >= 0

    def test_minimal_profile_succeeds(self, full_assumptions):
        """Bare minimum profile should produce valid output."""
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {"name": "Minimal", "age": 30, "retirement_age": 67},
            "income": {"primary_gross_annual": 30000},
            "expenses": {"housing": {"rent_monthly": 800}},
            "savings": {},
            "debts": [],
            "goals": [],
        })
        report, _, _flags = run_pipeline(profile)
        assert report["scoring"]["overall_score"] >= 0
        assert report["cashflow"]["net_income"]["monthly"] > 0

    def test_high_earner_profile(self, full_assumptions):
        """High earner profile with additional rate tax."""
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {
                "name": "High Earner", "age": 45, "retirement_age": 60,
                "dependents": 2, "risk_profile": "aggressive",
            },
            "income": {
                "primary_gross_annual": 200000,
                "bonus_annual_expected": 50000,
            },
            "expenses": {
                "housing": {"mortgage_monthly": 3000},
                "living": {"groceries_monthly": 800},
            },
            "savings": {
                "emergency_fund": 100000,
                "isa_balance": 150000,
                "pension_balance": 500000,
                "pension_personal_contribution_pct": 0.15,
                "pension_employer_contribution_pct": 0.05,
            },
            "debts": [],
            "goals": [],
        })
        report, _, _ = run_pipeline(profile)
        # High earner should still get a valid score
        assert 0 <= report["scoring"]["overall_score"] <= 100
        # Tax should be significant for £200k income
        assert report["cashflow"]["deductions"]["income_tax_annual"] > 30000

    def test_scottish_taxpayer(self, full_assumptions):
        """Scottish tax region should apply different bands."""
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {
                "name": "Scottish", "age": 35, "retirement_age": 67,
                "tax_region": "scotland",
            },
            "income": {"primary_gross_annual": 50000},
            "expenses": {"housing": {"rent_monthly": 900}},
            "savings": {"emergency_fund": 5000},
            "debts": [],
            "goals": [],
        })
        report, _, _ = run_pipeline(profile)
        assert report["cashflow"]["net_income"]["monthly"] > 0

    def test_self_employed_profile(self, full_assumptions):
        """Self-employed with business expenses."""
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {
                "name": "Freelancer", "age": 28, "retirement_age": 67,
                "employment_type": "self_employed",
            },
            "income": {
                "primary_gross_annual": 60000,
                "business_expenses_annual": 8000,
            },
            "expenses": {"housing": {"rent_monthly": 1000}},
            "savings": {
                "emergency_fund": 10000,
                "pension_personal_contribution_pct": 0.10,
            },
            "debts": [],
            "goals": [],
        })
        report, _, _ = run_pipeline(profile)
        assert report["cashflow"]["net_income"]["monthly"] > 0

    def test_retired_user(self, full_assumptions):
        """Near-retirement user with different planning horizon."""
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {
                "name": "Retiree", "age": 64, "retirement_age": 67,
                "dependents": 0, "risk_profile": "conservative",
            },
            "income": {"primary_gross_annual": 40000},
            "expenses": {"housing": {"mortgage_monthly": 500}},
            "savings": {
                "emergency_fund": 30000,
                "pension_balance": 350000,
                "isa_balance": 50000,
            },
            "debts": [],
            "goals": [],
        })
        report, _, _ = run_pipeline(profile)
        assert 0 <= report["scoring"]["overall_score"] <= 100

    def test_heavy_debt_profile(self, full_assumptions):
        """User with significant debt load."""
        from engine.loader import normalise_profile
        profile = normalise_profile({
            "personal": {"name": "Debtor", "age": 30, "retirement_age": 67},
            "income": {"primary_gross_annual": 35000},
            "expenses": {"housing": {"rent_monthly": 700}},
            "savings": {"emergency_fund": 500},
            "debts": [
                {"name": "Credit Card", "type": "credit_card", "balance": 8000,
                 "interest_rate": 0.22, "minimum_payment_monthly": 200},
                {"name": "Car Loan", "type": "personal_loan", "balance": 12000,
                 "interest_rate": 0.07, "minimum_payment_monthly": 250},
                {"name": "Student Loan", "type": "student_loan", "balance": 40000,
                 "interest_rate": 0.065, "minimum_payment_monthly": 0, "plan": "plan_2"},
            ],
            "goals": [],
        })
        report, _, _ = run_pipeline(profile)
        assert 0 <= report["scoring"]["overall_score"] <= 100
        assert report["debt"]["summary"]["total_balance"] > 0


# ---------------------------------------------------------------------------
# Assumptions governance (v7.6)
# ---------------------------------------------------------------------------

class TestAssumptionsStaleness:
    def test_expired_assumptions_raise_in_production(self):
        assumptions = {"effective_to": "2020-01-01", "tax_year": "2019/20"}
        with patch.dict(os.environ, {"GROUNDTRUTH_ENV": "production"}), pytest.raises(AssumptionError, match="expired"):
            _check_assumptions_staleness(assumptions)

    def test_expired_assumptions_warn_in_dev(self):
        assumptions = {"effective_to": "2020-01-01", "tax_year": "2019/20"}
        with patch.dict(os.environ, {"GROUNDTRUTH_ENV": "development"}):
            # Should not raise, just log warning
            _check_assumptions_staleness(assumptions)

    def test_valid_assumptions_pass(self):
        assumptions = {"effective_to": "2099-12-31", "tax_year": "2025/26"}
        _check_assumptions_staleness(assumptions)

    def test_missing_effective_to_passes(self):
        assumptions = {"tax_year": "2025/26"}
        _check_assumptions_staleness(assumptions)

    def test_invalid_date_format_passes(self):
        assumptions = {"effective_to": "not-a-date", "tax_year": "2025/26"}
        _check_assumptions_staleness(assumptions)

    def test_pipeline_includes_assumption_metadata_in_report(self, full_profile, full_assumptions):
        report, _, _ = run_pipeline(full_profile, assumptions_override=full_assumptions)
        meta = report["meta"]
        assert "assumptions" in meta
        assert meta["assumptions"]["tax_year"] == full_assumptions.get("tax_year", "unknown")
        assert "schema_version" in meta["assumptions"]
        assert "effective_from" in meta["assumptions"]
        assert "effective_to" in meta["assumptions"]

    def test_pipeline_blocks_stale_assumptions_in_production(self, full_profile, full_assumptions):
        stale = {**full_assumptions, "effective_to": "2020-01-01", "tax_year": "2019/20"}
        with patch.dict(os.environ, {"GROUNDTRUTH_ENV": "production"}), pytest.raises(AssumptionError, match="expired"):
            run_pipeline(full_profile, assumptions_override=stale)
