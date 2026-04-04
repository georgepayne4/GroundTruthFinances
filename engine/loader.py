"""
loader.py — YAML Loading and Schema Normalisation

Loads user financial profiles and system assumptions from YAML,
normalises nested structures into flat monthly/annual figures,
and provides accessor helpers used by every downstream module.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from engine.exceptions import ProfileError, AssumptionError
from engine.schemas import validate_assumptions

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_yaml(path: str | Path) -> dict[str, Any]:
    """Load a YAML file and return its contents as a dict."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"YAML file not found: {path}")
    logger.debug("Loading YAML: %s", path)
    with open(path, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ProfileError(f"Expected a YAML mapping at top level, got {type(data).__name__}")
    return data


def load_profile(path: str | Path) -> dict[str, Any]:
    """Load and normalise a user financial profile."""
    raw = load_yaml(path)
    profile = _normalise_profile(raw)
    logger.info("Profile loaded: %d sections", len([k for k in profile if not k.startswith("_")]))
    return profile


def load_assumptions(path: str | Path | None = None) -> dict[str, Any]:
    """Load and validate the assumptions file. Falls back to bundled default."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config" / "assumptions.yaml"
    data = load_yaml(path)
    try:
        validate_assumptions(data)
    except Exception as e:
        raise AssumptionError(f"Assumptions validation failed: {e}") from e
    logger.info("Assumptions loaded: tax year %s", data.get("tax_year", "unknown"))
    return data


# ---------------------------------------------------------------------------
# Normalisation helpers
# ---------------------------------------------------------------------------

def _normalise_profile(raw: dict) -> dict:
    """
    Walk the raw YAML and attach computed convenience fields so that
    downstream modules can work with consistent monthly/annual totals
    without re-deriving them.
    """
    profile = dict(raw)  # shallow copy top-level

    # --- Income ---
    inc = profile.get("income", {})
    primary_monthly = inc.get("primary_gross_annual", 0) / 12
    partner_monthly = inc.get("partner_gross_annual", 0) / 12
    side = inc.get("side_income_monthly", 0)
    rental = inc.get("rental_income_monthly", 0)
    invest_monthly = inc.get("investment_income_annual", 0) / 12
    inc["_total_gross_monthly"] = primary_monthly + partner_monthly + side + rental + invest_monthly
    inc["_total_gross_annual"] = inc["_total_gross_monthly"] * 12
    profile["income"] = inc

    # --- Expenses ---
    exp = profile.get("expenses", {})
    total_monthly = 0.0
    for category, items in exp.items():
        if category.startswith("_"):
            continue
        if not isinstance(items, dict):
            continue
        cat_monthly = 0.0
        for key, value in items.items():
            if key.startswith("_"):
                continue
            if "monthly" in key:
                cat_monthly += value
            elif "annual" in key:
                cat_monthly += value / 12
        items["_category_monthly"] = round(cat_monthly, 2)
        total_monthly += cat_monthly
    exp["_total_monthly"] = round(total_monthly, 2)
    exp["_total_annual"] = round(total_monthly * 12, 2)
    profile["expenses"] = exp

    # --- Debts ---
    debts = profile.get("debts", [])
    total_debt_balance = sum(d.get("balance", 0) for d in debts)
    total_min_payments = sum(d.get("minimum_payment_monthly", 0) for d in debts)
    profile["_debt_summary"] = {
        "total_balance": total_debt_balance,
        "total_minimum_monthly": total_min_payments,
        "count": len(debts),
    }

    # --- Savings / Net Worth ---
    sav = profile.get("savings", {})
    liquid = (
        sav.get("emergency_fund", 0)
        + sav.get("general_savings", 0)
        + sav.get("isa_balance", 0)
        + sav.get("lisa_balance", 0)
    )
    illiquid = sav.get("pension_balance", 0) + sav.get("other_investments", 0)
    sav["_total_liquid"] = liquid
    sav["_total_illiquid"] = illiquid
    sav["_total_assets"] = liquid + illiquid
    profile["savings"] = sav

    profile["_net_worth"] = sav["_total_assets"] - total_debt_balance

    # --- Goals ---
    goals = profile.get("goals", [])
    for g in goals:
        g.setdefault("priority", "medium")
        g.setdefault("category", "general")
    profile["goals"] = goals

    return profile


# ---------------------------------------------------------------------------
# Accessor utilities
# ---------------------------------------------------------------------------

def get_nested(data: dict, dotpath: str, default: Any = None) -> Any:
    """Retrieve a value from a nested dict using dot notation.

    >>> get_nested({"a": {"b": 1}}, "a.b")
    1
    """
    keys = dotpath.split(".")
    node = data
    for k in keys:
        if isinstance(node, dict):
            node = node.get(k, default)
        else:
            return default
    return node
