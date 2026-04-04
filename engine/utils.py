"""
utils.py — Shared Utility Functions

Cross-module helpers that are needed by 2+ engine modules.
Keep this minimal — only extract here when genuinely shared.
"""

from __future__ import annotations


def monthly_repayment(principal: float, annual_rate: float, term_years: int) -> float:
    """Standard amortising repayment formula (e.g. mortgage, loan)."""
    if principal <= 0 or term_years <= 0:
        return 0.0
    if annual_rate <= 0:
        return principal / (term_years * 12)

    r = annual_rate / 12
    n = term_years * 12
    compound = (1 + r) ** n
    return principal * (r * compound) / (compound - 1)
