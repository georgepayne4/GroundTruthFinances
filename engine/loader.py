"""
loader.py — YAML Loading and Schema Normalisation

Loads user financial profiles and system assumptions from YAML,
normalises nested structures into flat monthly/annual figures,
and provides accessor helpers used by every downstream module.
"""

from __future__ import annotations

import copy
import logging
from pathlib import Path
from typing import Any

import yaml

from engine.exceptions import AssumptionError, ProfileError
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
    with open(path, encoding="utf-8") as fh:
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


def merge_bank_data(
    profile: dict[str, Any],
    bank_result: dict[str, Any],
    override: bool = False,
) -> dict[str, Any]:
    """Merge bank-statement-derived data into a loaded profile (v5.2-02).

    bank_result is the dict returned by import_bank_csv(), containing
    ``expenses``, ``income_transactions``, ``recurring_transactions``,
    and ``summary``.

    Behaviour:
    - Expense sub-categories: by default the bank value supplements the
      profile value, taking the maximum (so manual entries are never
      under-stated). With override=True the bank value replaces the
      profile value entirely.
    - Income: if the bank summary detected a salary credit and the
      profile has no primary_gross_annual, infer it from the most recent
      payroll transaction (12x).
    - The merged profile is re-normalised so downstream totals are correct.
    - A ``_bank_import`` block is attached to the profile capturing what
      was merged, which fields were overridden, and the import summary.

    Returns a new profile dict (the input is not mutated).
    """
    merged = copy.deepcopy(profile)
    bank_expenses = bank_result.get("expenses", {}) or {}
    overridden: list[str] = []
    supplemented: list[str] = []

    profile_expenses = merged.setdefault("expenses", {})
    for category, sub_map in bank_expenses.items():
        existing_cat = profile_expenses.get(category)
        if not isinstance(existing_cat, dict):
            existing_cat = {}
            profile_expenses[category] = existing_cat
        for sub_key, bank_value in sub_map.items():
            existing_value = existing_cat.get(sub_key, 0) or 0
            if override or existing_value == 0:
                existing_cat[sub_key] = bank_value
                overridden.append(f"{category}.{sub_key}")
            else:
                # Take the higher of manual entry and bank-derived figure
                # so we never silently lower a user-stated commitment.
                merged_value = max(existing_value, bank_value)
                if merged_value != existing_value:
                    existing_cat[sub_key] = merged_value
                    supplemented.append(f"{category}.{sub_key}")

    # Strip computed fields so re-normalisation produces fresh totals
    for cat_data in profile_expenses.values():
        if isinstance(cat_data, dict):
            cat_data.pop("_category_monthly", None)
    profile_expenses.pop("_total_monthly", None)
    profile_expenses.pop("_total_annual", None)

    # Income inference: only fill if user didn't provide a salary
    income_inferred = None
    income_block = merged.setdefault("income", {})
    if not income_block.get("primary_gross_annual"):
        income_txns = bank_result.get("income_transactions") or []
        if income_txns:
            latest = max(income_txns, key=lambda t: t["date"])
            inferred_annual = round(latest["amount"] * 12, 2)
            income_block["primary_gross_annual"] = inferred_annual
            income_inferred = {
                "source_description": latest["description"],
                "monthly_credit": latest["amount"],
                "annual_estimate": inferred_annual,
            }

    # Re-normalise so downstream modules see fresh totals
    merged = _normalise_profile(merged)

    merged["_bank_import"] = {
        "summary": bank_result.get("summary", {}),
        "expense_fields_overridden": overridden,
        "expense_fields_supplemented": supplemented,
        "income_inferred": income_inferred,
        "recurring_transactions": bank_result.get("recurring_transactions", []),
        "subscriptions": bank_result.get("subscriptions", []),
        "committed_outflows": bank_result.get("committed_outflows", []),
    }
    logger.info(
        "Merged bank data: %d field overrides, %d supplements, income_inferred=%s",
        len(overridden), len(supplemented), bool(income_inferred),
    )
    return merged


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

_ACCOUNT_TYPE_MAPPING: dict[str, str] = {
    # account type → savings field it contributes to by default
    "current": "general_savings",
    "savings": "general_savings",
    "easy_access": "general_savings",
    "money_market": "general_savings",
    "premium_bonds": "general_savings",
    "isa": "isa_balance",
    "cash_isa": "isa_balance",
    "stocks_and_shares_isa": "isa_balance",
    "lisa": "lisa_balance",
    "cash_lisa": "lisa_balance",
    "stocks_and_shares_lisa": "lisa_balance",
    "pension": "pension_balance",
    "sipp": "pension_balance",
    "investment": "other_investments",
    "stocks_and_shares": "other_investments",
    "gia": "other_investments",
    "crypto": "other_investments",
}


def _aggregate_accounts(profile: dict) -> dict[str, float]:
    """v5.2-04: aggregate the accounts[] block into savings_field → total.

    Each account contributes to one savings field, determined by:
      1. explicit `maps_to` field on the account, OR
      2. _ACCOUNT_TYPE_MAPPING[account.type], OR
      3. "general_savings" as a safe fallback for unknown types.

    Returns a {savings_field: total} dict, plus an "_account_breakdown" key
    listing per-account routing for debugging / display.
    """
    accounts = profile.get("accounts", []) or []
    totals: dict[str, float] = {}
    for acc in accounts:
        if not isinstance(acc, dict):
            continue
        balance = acc.get("balance", 0) or 0
        if balance == 0:
            continue
        target = (
            acc.get("maps_to")
            or _ACCOUNT_TYPE_MAPPING.get(acc.get("type", "").lower())
            or "general_savings"
        )
        totals[target] = totals.get(target, 0) + balance
    return totals


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
    # v5.2-03: paid-in-full credit cards are cash-flow tools, not debt.
    # They contribute neither to total balance nor to minimum payments.
    debts = profile.get("debts", [])
    real_debts = [
        d for d in debts
        if not (
            d.get("type") == "credit_card"
            and d.get("payment_behaviour", "minimum") == "full"
        )
    ]
    total_debt_balance = sum(d.get("balance", 0) for d in real_debts)
    total_min_payments = sum(d.get("minimum_payment_monthly", 0) for d in real_debts)
    profile["_debt_summary"] = {
        "total_balance": total_debt_balance,
        "total_minimum_monthly": total_min_payments,
        "count": len(real_debts),
        "full_pay_card_count": len(debts) - len(real_debts),
    }

    # --- Savings / Net Worth ---
    sav = profile.get("savings", {})

    # v5.2-04: aggregate accounts[] block into savings fields. Mapped fields
    # are REPLACED by the account total — single source of truth per field.
    # Direct savings fields with no matching account are left untouched.
    account_totals = _aggregate_accounts(profile)
    overridden_fields: list[str] = []
    for field, total in account_totals.items():
        if field in sav and sav[field] != total:
            overridden_fields.append(field)
        sav[field] = total

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
    if account_totals:
        sav["_account_aggregated_fields"] = sorted(account_totals.keys())
    if overridden_fields:
        sav["_account_overridden_fields"] = overridden_fields
    profile["savings"] = sav

    # Net worth still subtracts paid-in-full card balances: the cash to clear
    # them sits in liquid savings but is already committed to next statement.
    full_pay_committed = sum(
        (d.get("current_balance") or d.get("balance", 0))
        for d in debts
        if d.get("type") == "credit_card" and d.get("payment_behaviour", "minimum") == "full"
    )
    profile["_net_worth"] = sav["_total_assets"] - total_debt_balance - full_pay_committed

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
