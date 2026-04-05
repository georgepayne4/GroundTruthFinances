"""Shared test fixtures for the GroundTruth engine test suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from engine.loader import load_assumptions, load_profile

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def assumptions() -> dict:
    """Load the standard assumptions file."""
    return load_assumptions(PROJECT_ROOT / "config" / "assumptions.yaml")


@pytest.fixture
def sample_profile() -> dict:
    """Load and normalise the sample_input profile."""
    return load_profile(PROJECT_ROOT / "config" / "sample_input.yaml")


@pytest.fixture
def minimal_profile() -> dict:
    """Bare-minimum profile with only required fields."""
    from engine.loader import _normalise_profile
    return _normalise_profile({
        "personal": {
            "name": "Test User",
            "age": 30,
            "retirement_age": 67,
            "dependents": 0,
            "risk_profile": "moderate",
            "employment_type": "employed",
        },
        "income": {
            "primary_gross_annual": 50000,
        },
        "expenses": {
            "housing": {"rent_monthly": 1000},
            "living": {"groceries_monthly": 300},
        },
        "savings": {
            "emergency_fund": 5000,
            "pension_balance": 10000,
            "pension_personal_contribution_pct": 0.05,
            "pension_employer_contribution_pct": 0.03,
        },
        "debts": [],
        "goals": [],
    })


@pytest.fixture
def high_earner_profile() -> dict:
    """Profile with income above the additional rate threshold."""
    from engine.loader import _normalise_profile
    return _normalise_profile({
        "personal": {
            "name": "High Earner",
            "age": 45,
            "retirement_age": 60,
            "dependents": 2,
            "risk_profile": "aggressive",
            "employment_type": "employed",
            "has_will": True,
            "has_lpa": True,
        },
        "income": {
            "primary_gross_annual": 150000,
            "bonus_annual_expected": 30000,
        },
        "expenses": {
            "housing": {"mortgage_monthly": 2500},
            "living": {"groceries_monthly": 600},
        },
        "savings": {
            "emergency_fund": 50000,
            "general_savings": 20000,
            "isa_balance": 80000,
            "pension_balance": 250000,
            "pension_personal_contribution_pct": 0.10,
            "pension_employer_contribution_pct": 0.05,
        },
        "debts": [],
        "goals": [
            {"name": "University fund", "target_amount": 50000, "deadline_years": 10, "priority": "high"},
        ],
    })


@pytest.fixture
def self_employed_profile() -> dict:
    """Self-employed profile with business expenses."""
    from engine.loader import _normalise_profile
    return _normalise_profile({
        "personal": {
            "name": "Contractor",
            "age": 35,
            "retirement_age": 67,
            "dependents": 0,
            "risk_profile": "moderate",
            "employment_type": "self_employed",
        },
        "income": {
            "primary_gross_annual": 80000,
            "business_expenses_annual": 10000,
        },
        "expenses": {
            "housing": {"rent_monthly": 1200},
            "living": {"groceries_monthly": 350},
        },
        "savings": {
            "emergency_fund": 15000,
            "pension_balance": 30000,
            "pension_personal_contribution_pct": 0.08,
            "pension_employer_contribution_pct": 0.0,
        },
        "debts": [],
        "goals": [],
    })
