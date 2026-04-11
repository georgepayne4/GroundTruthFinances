"""
types.py — Shared TypedDict definitions for engine module results.

These define the top-level shape of dicts returned by each public engine
function. They use ``total=False`` because many fields are conditionally
populated (e.g. partner data only present when a partner exists).

Used as return type annotations on the public ``analyse_*`` / ``run_*`` /
``calculate_*`` functions to enable IDE autocomplete and catch dict-key
typos at type-check time. Internal helpers remain loosely typed.
"""

from __future__ import annotations

from typing import Any, TypedDict

# ---------------------------------------------------------------------------
# Profile / Assumptions inputs
# ---------------------------------------------------------------------------

# Profile and assumptions are user-supplied YAML — kept as plain dicts.
# Pydantic schemas in schemas.py provide structural validation at load time.
ProfileDict = dict[str, Any]
AssumptionsDict = dict[str, Any]


# ---------------------------------------------------------------------------
# Cashflow result
# ---------------------------------------------------------------------------

class CashflowResult(TypedDict, total=False):
    income: dict[str, float]
    deductions: dict[str, float]
    net_income: dict[str, float]
    expenses: dict[str, Any]
    debt_servicing: dict[str, float]
    surplus: dict[str, float]
    savings_rate: dict[str, float]
    total_outgoings_monthly: float
    bonus_scenarios: dict[str, Any]
    spending_benchmarks: dict[str, Any]
    self_employment: dict[str, Any]
    salary_sacrifice_comparison: dict[str, Any]
    partner: dict[str, Any]
    household: dict[str, float]
    marriage_allowance: dict[str, Any]


# ---------------------------------------------------------------------------
# Debt result
# ---------------------------------------------------------------------------

class DebtResult(TypedDict, total=False):
    debts: list[dict[str, Any]]
    summary: dict[str, Any]
    recommended_strategy: str
    avalanche_order: list[str]
    extra_payment_scenarios: list[dict[str, Any]]
    credit_card_tracking: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Goals result
# ---------------------------------------------------------------------------

class GoalsResult(TypedDict, total=False):
    goals: list[dict[str, Any]]
    prerequisites: dict[str, Any]
    summary: dict[str, Any]


# ---------------------------------------------------------------------------
# Investments result
# ---------------------------------------------------------------------------

class InvestmentsResult(TypedDict, total=False):
    portfolio_snapshot: dict[str, Any]
    risk_metrics: dict[str, Any]
    fee_analysis: dict[str, Any]
    growth_projections: dict[str, Any]
    pension_analysis: dict[str, Any]
    pension_match_optimisation: dict[str, Any]
    time_horizon_allocation: dict[str, Any]
    emergency_fund_warning: dict[str, Any]
    withdrawal_strategy: dict[str, Any]
    glide_path: dict[str, Any]
    annuity_comparison: dict[str, Any]
    isa_tracking: dict[str, Any]
    isa_note: str
    investable_surplus_monthly: float
    esg_note: str
    tax_efficiency: dict[str, Any]
    rebalancing: dict[str, Any]
    pension_annual_allowance: dict[str, Any]
    monte_carlo_summary: dict[str, Any]


# ---------------------------------------------------------------------------
# Mortgage result
# ---------------------------------------------------------------------------

class MortgageResult(TypedDict, total=False):
    applicable: bool
    target_property_value: float
    first_time_buyer: bool
    borrowing: dict[str, Any]
    deposit: dict[str, Any]
    repayment: dict[str, Any]
    affordability: dict[str, Any]
    ltv_analysis: dict[str, Any]
    acquisition_costs: dict[str, Any]
    product_comparison: list[dict[str, Any]]
    overpayment_analysis: dict[str, Any]
    remortgage_analysis: dict[str, Any]
    credit_warnings: list[dict[str, Any]]
    deposit_source: dict[str, Any]
    blockers: list[dict[str, Any]]
    readiness: str
    shared_ownership: dict[str, Any]
    employment_impact: dict[str, Any]


# ---------------------------------------------------------------------------
# Scoring result
# ---------------------------------------------------------------------------

class ScoringResult(TypedDict, total=False):
    overall_score: float
    grade: str
    categories: dict[str, dict[str, Any]]
    interpretation: str


# ---------------------------------------------------------------------------
# Insurance result
# ---------------------------------------------------------------------------

class InsuranceResult(TypedDict, total=False):
    life_insurance: dict[str, Any]
    income_protection: dict[str, Any]
    critical_illness: dict[str, Any]
    gaps: list[dict[str, Any]]
    gap_count: int
    overall_assessment: str
    pension_cross_reference: dict[str, Any]
    survivor_analysis: dict[str, Any]


# ---------------------------------------------------------------------------
# Life events result
# ---------------------------------------------------------------------------

class LifeEventsResult(TypedDict, total=False):
    projection_years: int
    timeline: list[dict[str, Any]]
    milestones: list[dict[str, Any]]
    summary: dict[str, Any]
    goal_feasibility_at_deadline: list[dict[str, Any]]


# ---------------------------------------------------------------------------
# Stress scenarios result
# ---------------------------------------------------------------------------

class ScenariosResult(TypedDict, total=False):
    job_loss: dict[str, Any]
    interest_rate_shock: dict[str, Any]
    market_downturn: dict[str, Any]
    inflation_shock: dict[str, Any]
    income_reduction: dict[str, Any]


# ---------------------------------------------------------------------------
# Sensitivity analysis result
# ---------------------------------------------------------------------------

class SensitivityResult(TypedDict, total=False):
    baseline: dict[str, Any]
    scenarios: dict[str, list[dict[str, Any]]]


# ---------------------------------------------------------------------------
# Estate result
# ---------------------------------------------------------------------------

class EstateResult(TypedDict, total=False):
    projected_estate_value: float
    projection_age: int
    estate_breakdown: dict[str, float]
    iht_threshold: dict[str, Any]
    iht_liability: float
    exceeds_threshold: bool
    iht_note: str | None
    estate_planning: dict[str, Any]


# ---------------------------------------------------------------------------
# Insights result
# ---------------------------------------------------------------------------

class InsightsResult(TypedDict, total=False):
    executive_summary: str
    top_priorities: list[dict[str, Any]]
    surplus_deployment_plan: dict[str, Any]
    cashflow_insights: list[str]
    debt_insights: list[str]
    goal_insights: list[str]
    investment_insights: list[str]
    mortgage_insights: list[str]
    life_event_insights: list[str]
    goal_event_conflicts: list[dict[str, Any]]
    tax_optimisation: list[dict[str, Any]]
    risk_warnings: list[dict[str, Any]]
    positive_reinforcements: list[str]
    recommended_next_steps: list[str]
    review_schedule: dict[str, Any]


# ---------------------------------------------------------------------------
# Final assembled report
# ---------------------------------------------------------------------------

class ReportDict(TypedDict, total=False):
    meta: dict[str, Any]
    validation: dict[str, Any]
    scoring: ScoringResult
    cashflow: CashflowResult
    debt: DebtResult
    goals: GoalsResult
    investments: InvestmentsResult
    mortgage: MortgageResult
    life_events: LifeEventsResult
    insurance: InsuranceResult | None
    stress_scenarios: ScenariosResult | None
    estate: EstateResult | None
    sensitivity_analysis: SensitivityResult | None
    advisor_insights: InsightsResult
    review_schedule: dict[str, Any] | None


# ---------------------------------------------------------------------------
# Tax calculation results
# ---------------------------------------------------------------------------

class MarriageAllowanceResult(TypedDict, total=False):
    eligible: bool
    reason: str
    transferor_income: float
    recipient_income: float
    transfer_amount: int
    annual_tax_saving: float


class PensionWithdrawalTaxResult(TypedDict):
    gross_income: float
    tax_free_drawdown: float
    taxable_income: float
    income_tax: float
    net_income: float
    effective_tax_rate_pct: float


class CapitalGainsTaxResult(TypedDict, total=False):
    gain: float
    annual_exemption: int
    taxable_gain: float
    basic_rate_portion: float
    higher_rate_portion: float
    tax: float
    effective_rate_pct: float


class DividendTaxResult(TypedDict, total=False):
    dividends: float
    allowance: int
    taxable_dividends: float
    tax: float
    effective_rate_pct: float
