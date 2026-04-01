"""
validator.py — Advisor Validation Layer

Detects missing, inconsistent, or unrealistic inputs and emits structured
validation flags.  Never prompts the user — every issue is reported as a
flag with severity, message, and suggested action.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Flag schema
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    ERROR = "error"          # blocks meaningful analysis
    WARNING = "warning"      # analysis will run but results may be misleading
    INFO = "info"            # advisory note the user should be aware of


@dataclass
class ValidationFlag:
    field: str               # dotpath to the problematic field
    severity: Severity
    message: str
    suggested_action: str

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        return d


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_profile(profile: dict, assumptions: dict) -> list[ValidationFlag]:
    """Run all validation checks and return a list of flags."""
    flags: list[ValidationFlag] = []
    flags.extend(_check_required_sections(profile))
    flags.extend(_check_personal(profile))
    flags.extend(_check_income(profile, assumptions))
    flags.extend(_check_expenses(profile))
    flags.extend(_check_debts(profile, assumptions))
    flags.extend(_check_savings(profile, assumptions))
    flags.extend(_check_goals(profile))
    flags.extend(_check_mortgage(profile, assumptions))
    flags.extend(_check_cross_field_consistency(profile, assumptions))
    return flags


# ---------------------------------------------------------------------------
# Section-level checks
# ---------------------------------------------------------------------------

REQUIRED_SECTIONS = ["personal", "income", "expenses", "savings"]


def _check_required_sections(profile: dict) -> list[ValidationFlag]:
    flags = []
    for section in REQUIRED_SECTIONS:
        if section not in profile or not profile[section]:
            flags.append(ValidationFlag(
                field=section,
                severity=Severity.ERROR,
                message=f"Required section '{section}' is missing or empty.",
                suggested_action=f"Add the '{section}' section to your profile YAML.",
            ))
    return flags


def _check_personal(profile: dict) -> list[ValidationFlag]:
    flags = []
    personal = profile.get("personal", {})
    if not personal:
        return flags

    age = personal.get("age")
    if age is None:
        flags.append(ValidationFlag("personal.age", Severity.ERROR,
                                    "Age is missing.", "Provide your current age."))
    elif not (16 <= age <= 100):
        flags.append(ValidationFlag("personal.age", Severity.WARNING,
                                    f"Age {age} is outside the typical planning range (16-100).",
                                    "Verify your age is entered correctly."))

    ret_age = personal.get("retirement_age")
    if ret_age is not None and age is not None:
        if ret_age <= age:
            flags.append(ValidationFlag("personal.retirement_age", Severity.ERROR,
                                        "Retirement age must be greater than current age.",
                                        "Set retirement_age to a future age."))
        elif ret_age - age < 5:
            flags.append(ValidationFlag("personal.retirement_age", Severity.WARNING,
                                        f"Only {ret_age - age} years until retirement — short horizon affects strategy.",
                                        "Confirm retirement age or adjust planning assumptions."))

    risk = personal.get("risk_profile", "").lower()
    valid_risk = {"conservative", "moderate", "aggressive", "very_aggressive"}
    if risk and risk not in valid_risk:
        flags.append(ValidationFlag("personal.risk_profile", Severity.WARNING,
                                    f"Unrecognised risk profile '{risk}'.",
                                    f"Use one of: {', '.join(sorted(valid_risk))}."))

    return flags


def _check_income(profile: dict, assumptions: dict) -> list[ValidationFlag]:
    flags = []
    inc = profile.get("income", {})
    if not inc:
        return flags

    primary = inc.get("primary_gross_annual", 0)
    if primary <= 0:
        flags.append(ValidationFlag("income.primary_gross_annual", Severity.ERROR,
                                    "Primary income is zero or missing.",
                                    "Enter your gross annual income."))
    elif primary < 10000:
        flags.append(ValidationFlag("income.primary_gross_annual", Severity.WARNING,
                                    f"Primary income {primary:,.0f} seems very low for annual gross.",
                                    "Check whether this should be an annual (not monthly) figure."))
    elif primary > 500000:
        flags.append(ValidationFlag("income.primary_gross_annual", Severity.INFO,
                                    f"Primary income {primary:,.0f} is above the additional-rate threshold.",
                                    "Ensure tax planning and pension contributions are optimised."))

    side = inc.get("side_income_monthly", 0)
    if side > primary / 12 * 0.5 and side > 500:
        flags.append(ValidationFlag("income.side_income_monthly", Severity.INFO,
                                    "Side income exceeds 50% of primary monthly income.",
                                    "Verify stability; side income is often variable."))

    return flags


def _check_expenses(profile: dict) -> list[ValidationFlag]:
    flags = []
    exp = profile.get("expenses", {})
    total = exp.get("_total_monthly", 0)
    gross = profile.get("income", {}).get("_total_gross_monthly", 0)

    if total <= 0:
        flags.append(ValidationFlag("expenses", Severity.WARNING,
                                    "Total monthly expenses are zero — likely incomplete.",
                                    "Fill in expense categories for accurate analysis."))
    elif gross > 0 and total > gross:
        flags.append(ValidationFlag("expenses._total_monthly", Severity.WARNING,
                                    f"Expenses ({total:,.0f}/mo) exceed gross income ({gross:,.0f}/mo).",
                                    "Either expenses are overstated or income is understated."))

    # Check individual categories for plausibility
    housing = exp.get("housing", {})
    rent = housing.get("rent_monthly", 0)
    if rent > 0 and gross > 0 and rent > gross * 0.50:
        flags.append(ValidationFlag("expenses.housing.rent_monthly", Severity.WARNING,
                                    f"Rent ({rent:,.0f}/mo) is over 50% of gross income.",
                                    "High housing cost ratio will constrain all other goals."))

    return flags


def _check_debts(profile: dict, assumptions: dict) -> list[ValidationFlag]:
    flags = []
    debts = profile.get("debts", [])
    high_rate_thresh = assumptions.get("debt", {}).get("high_interest_threshold", 0.10)

    for i, d in enumerate(debts):
        prefix = f"debts[{i}]"
        bal = d.get("balance", 0)
        rate = d.get("interest_rate", 0)
        minpay = d.get("minimum_payment_monthly", 0)

        if bal < 0:
            flags.append(ValidationFlag(f"{prefix}.balance", Severity.ERROR,
                                        "Debt balance cannot be negative.",
                                        "Enter the outstanding balance as a positive number."))

        if rate > 0.50:
            flags.append(ValidationFlag(f"{prefix}.interest_rate", Severity.WARNING,
                                        f"Interest rate {rate*100:.1f}% is extremely high.",
                                        "Verify this is an annual rate expressed as a decimal (e.g. 0.20 for 20%)."))
        elif rate >= high_rate_thresh:
            flags.append(ValidationFlag(f"{prefix}.interest_rate", Severity.INFO,
                                        f"High-interest debt at {rate*100:.1f}%.",
                                        "Prioritise paying this off before investing."))

        if bal > 0 and minpay <= 0:
            flags.append(ValidationFlag(f"{prefix}.minimum_payment_monthly", Severity.WARNING,
                                        "Debt has a balance but no minimum payment specified.",
                                        "Add the required minimum monthly payment."))

        # Check if minimum payment even covers monthly interest
        if bal > 0 and rate > 0 and minpay > 0:
            monthly_interest = bal * rate / 12
            if minpay < monthly_interest:
                flags.append(ValidationFlag(f"{prefix}.minimum_payment_monthly", Severity.WARNING,
                                            f"Minimum payment ({minpay:.0f}) does not cover monthly interest ({monthly_interest:.0f}).",
                                            "This debt will grow. Increase payments or seek advice."))

    return flags


def _check_savings(profile: dict, assumptions: dict) -> list[ValidationFlag]:
    flags = []
    sav = profile.get("savings", {})
    exp = profile.get("expenses", {})
    monthly_exp = exp.get("_total_monthly", 0)

    ef = sav.get("emergency_fund", 0)
    min_months = assumptions.get("debt", {}).get("emergency_fund_months", 3)
    ideal_months = assumptions.get("debt", {}).get("ideal_emergency_fund_months", 6)
    needed = monthly_exp * min_months

    if ef <= 0:
        flags.append(ValidationFlag("savings.emergency_fund", Severity.WARNING,
                                    "No emergency fund reported.",
                                    f"Aim for at least {min_months} months of expenses ({needed:,.0f})."))
    elif ef < needed:
        flags.append(ValidationFlag("savings.emergency_fund", Severity.WARNING,
                                    f"Emergency fund ({ef:,.0f}) covers less than {min_months} months of expenses.",
                                    f"Target at least {needed:,.0f}."))
    elif ef < monthly_exp * ideal_months:
        flags.append(ValidationFlag("savings.emergency_fund", Severity.INFO,
                                    f"Emergency fund covers {ef / monthly_exp:.1f} months — good, but below the ideal {ideal_months} months.",
                                    f"Continue building toward {monthly_exp * ideal_months:,.0f}."))

    # Pension contribution sanity
    personal_pct = sav.get("pension_personal_contribution_pct", 0)
    employer_pct = sav.get("pension_employer_contribution_pct", 0)
    if personal_pct + employer_pct > 0.60:
        flags.append(ValidationFlag("savings.pension_contribution", Severity.WARNING,
                                    "Combined pension contribution exceeds 60% of salary.",
                                    "Verify contribution percentages are decimals (e.g. 0.05 for 5%)."))

    if personal_pct == 0 and employer_pct > 0:
        flags.append(ValidationFlag("savings.pension_personal_contribution_pct", Severity.INFO,
                                    "No personal pension contribution — only employer match.",
                                    "Consider contributing at least enough to maximise employer matching."))

    return flags


def _check_goals(profile: dict) -> list[ValidationFlag]:
    flags = []
    goals = profile.get("goals", [])

    for i, g in enumerate(goals):
        prefix = f"goals[{i}]"
        target = g.get("target_amount", 0)
        deadline = g.get("deadline_years", 0)
        name = g.get("name", f"Goal {i+1}")

        if target <= 0:
            flags.append(ValidationFlag(f"{prefix}.target_amount", Severity.WARNING,
                                        f"Goal '{name}' has no target amount.",
                                        "Set a realistic target to enable feasibility analysis."))
        if deadline <= 0:
            flags.append(ValidationFlag(f"{prefix}.deadline_years", Severity.WARNING,
                                        f"Goal '{name}' has no deadline.",
                                        "Set a time horizon in years."))

    return flags


def _check_mortgage(profile: dict, assumptions: dict) -> list[ValidationFlag]:
    flags = []
    mort = profile.get("mortgage")
    if mort is None:
        return flags

    target = mort.get("target_property_value", 0)
    if target <= 0:
        flags.append(ValidationFlag("mortgage.target_property_value", Severity.WARNING,
                                    "Target property value not set.",
                                    "Provide an estimate for mortgage analysis."))

    dep_pct = mort.get("preferred_deposit_pct", 0)
    min_dep = assumptions.get("mortgage", {}).get("min_deposit_pct", 0.05)
    if 0 < dep_pct < min_dep:
        flags.append(ValidationFlag("mortgage.preferred_deposit_pct", Severity.WARNING,
                                    f"Preferred deposit ({dep_pct*100:.0f}%) is below minimum ({min_dep*100:.0f}%).",
                                    f"Most lenders require at least {min_dep*100:.0f}% deposit."))

    term = mort.get("preferred_term_years", 25)
    if term > 35:
        flags.append(ValidationFlag("mortgage.preferred_term_years", Severity.INFO,
                                    f"Mortgage term of {term} years is unusually long.",
                                    "Longer terms reduce payments but increase total interest."))

    return flags


def _check_cross_field_consistency(profile: dict, assumptions: dict) -> list[ValidationFlag]:
    """Checks that span multiple sections."""
    flags = []
    inc = profile.get("income", {})
    exp = profile.get("expenses", {})
    debts = profile.get("debts", [])
    sav = profile.get("savings", {})

    gross_monthly = inc.get("_total_gross_monthly", 0)
    if gross_monthly <= 0:
        return flags  # can't do cross-checks without income

    # Debt-to-income ratio
    total_debt_payments = sum(d.get("minimum_payment_monthly", 0) for d in debts)
    dti = total_debt_payments / gross_monthly if gross_monthly else 0
    max_dti = assumptions.get("mortgage", {}).get("max_dti_ratio", 0.45)
    if dti > max_dti:
        flags.append(ValidationFlag("_cross.debt_to_income", Severity.WARNING,
                                    f"Debt-to-income ratio ({dti*100:.1f}%) exceeds safe threshold ({max_dti*100:.0f}%).",
                                    "Reducing debt payments will improve borrowing capacity."))
    elif dti > 0.30:
        flags.append(ValidationFlag("_cross.debt_to_income", Severity.INFO,
                                    f"Debt-to-income ratio ({dti*100:.1f}%) is moderate.",
                                    "Aim to reduce below 30% for optimal financial flexibility."))

    # Expense ratio check
    total_exp = exp.get("_total_monthly", 0) + total_debt_payments
    expense_ratio = total_exp / gross_monthly if gross_monthly else 0
    if expense_ratio > 0.90:
        flags.append(ValidationFlag("_cross.expense_ratio", Severity.WARNING,
                                    f"Expenses + debt consume {expense_ratio*100:.0f}% of gross income.",
                                    "Very limited capacity for savings or unexpected costs."))

    # Age + pension balance sanity
    personal = profile.get("personal", {})
    age = personal.get("age", 0)
    pension = sav.get("pension_balance", 0)
    if age > 40 and pension < gross_monthly * 12:
        flags.append(ValidationFlag("_cross.pension_adequacy", Severity.WARNING,
                                    f"Pension balance ({pension:,.0f}) is less than one year's gross income at age {age}.",
                                    "Consider increasing pension contributions — the earlier the better."))

    return flags
