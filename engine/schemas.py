"""
schemas.py — Pydantic Schema Validation for Config Files

Validates assumptions.yaml and profile YAML against strict schemas.
Catches typos, missing keys, type errors, and out-of-range values at load time.
Reusable for API request validation in v5.3.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# Assumptions schema
# ---------------------------------------------------------------------------

class InflationConfig(BaseModel):
    general: float = Field(ge=0.0, le=0.20)
    education: float = Field(ge=0.0, le=0.20)
    healthcare: float = Field(ge=0.0, le=0.20)
    housing: float = Field(ge=0.0, le=0.20)


class InvestmentReturnsConfig(BaseModel):
    conservative: float = Field(ge=0.0, le=0.30)
    moderate: float = Field(ge=0.0, le=0.30)
    aggressive: float = Field(ge=0.0, le=0.30)
    very_aggressive: float = Field(ge=0.0, le=0.30)


class SalaryGrowthConfig(BaseModel):
    low: float = Field(ge=0.0, le=0.20)
    average: float = Field(ge=0.0, le=0.20)
    high: float = Field(ge=0.0, le=0.20)


class TaxConfig(BaseModel):
    personal_allowance: int = Field(gt=0)
    basic_rate: float = Field(ge=0.0, le=1.0)
    basic_threshold: int = Field(gt=0)
    higher_rate: float = Field(ge=0.0, le=1.0)
    higher_threshold: int = Field(gt=0)
    additional_rate: float = Field(ge=0.0, le=1.0)
    national_insurance_rate: float = Field(ge=0.0, le=1.0)
    marriage_allowance_transfer: int = Field(default=1260, ge=0)


class ScottishTaxConfig(BaseModel):
    starter_rate: float = Field(ge=0.0, le=1.0)
    starter_threshold: int = Field(gt=0)
    basic_rate: float = Field(ge=0.0, le=1.0)
    basic_threshold: int = Field(gt=0)
    intermediate_rate: float = Field(ge=0.0, le=1.0)
    intermediate_threshold: int = Field(gt=0)
    higher_rate: float = Field(ge=0.0, le=1.0)
    higher_threshold: int = Field(gt=0)
    advanced_rate: float = Field(ge=0.0, le=1.0)
    advanced_threshold: int = Field(gt=0)
    top_rate: float = Field(ge=0.0, le=1.0)


class StampDutyBand(BaseModel):
    threshold: int = Field(gt=0)
    rate: float = Field(ge=0.0, le=1.0)


class StampDutyConfig(BaseModel):
    first_time_buyer: list[StampDutyBand]
    standard: list[StampDutyBand]


class LtvTier(BaseModel):
    max_ltv: float = Field(ge=0.0, le=1.0)
    rate_adjustment: float = Field(ge=-0.05, le=0.05)


class MortgageConfig(BaseModel):
    income_multiple_single: float = Field(ge=1.0, le=10.0)
    income_multiple_joint: float = Field(ge=1.0, le=10.0)
    income_multiple_self_employed: float = Field(ge=1.0, le=10.0)
    min_deposit_pct: float = Field(ge=0.0, le=1.0)
    comfortable_deposit_pct: float = Field(ge=0.0, le=1.0)
    ideal_deposit_pct: float = Field(ge=0.0, le=1.0)
    stress_test_rate: float = Field(ge=0.0, le=0.20)
    max_dti_ratio: float = Field(ge=0.0, le=1.0)
    typical_term_years: int = Field(ge=5, le=40)


class MortgageProduct(BaseModel):
    rate: float = Field(ge=0.0, le=0.20)
    fee: int = Field(default=0, ge=0)
    term_years: int = Field(ge=0, le=10)
    margin_above_base: float | None = None


class MortgageProductsConfig(BaseModel):
    two_year_fix: MortgageProduct
    five_year_fix: MortgageProduct
    tracker: MortgageProduct
    svr: MortgageProduct


class SharedOwnershipConfig(BaseModel):
    rent_on_unowned_pct: float = Field(ge=0.0, le=0.10)
    service_charge_monthly: float = Field(ge=0)
    min_share_pct: float = Field(ge=0.0, le=1.0)


class DebtConfig(BaseModel):
    emergency_fund_months: int = Field(ge=1, le=24)
    ideal_emergency_fund_months: int = Field(ge=1, le=24)
    high_interest_threshold: float = Field(ge=0.0, le=1.0)
    moderate_interest_threshold: float = Field(ge=0.0, le=1.0)


class StudentLoanPlan(BaseModel):
    repayment_threshold: int = Field(gt=0)
    repayment_rate: float = Field(ge=0.0, le=1.0)
    interest_rate: float = Field(ge=0.0, le=0.20)
    write_off_years: int = Field(ge=1, le=50)


class StudentLoansConfig(BaseModel):
    plan_2: StudentLoanPlan
    plan_3: StudentLoanPlan


class ScoringWeights(BaseModel):
    savings_rate: float = Field(ge=0.0, le=1.0)
    debt_health: float = Field(ge=0.0, le=1.0)
    emergency_fund: float = Field(ge=0.0, le=1.0)
    net_worth_trend: float = Field(ge=0.0, le=1.0)
    goal_progress: float = Field(ge=0.0, le=1.0)
    investment_diversification: float = Field(ge=0.0, le=1.0)
    mortgage_readiness: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> ScoringWeights:
        total = (
            self.savings_rate + self.debt_health + self.emergency_fund +
            self.net_worth_trend + self.goal_progress +
            self.investment_diversification + self.mortgage_readiness
        )
        if abs(total - 1.0) > 0.01:
            raise ValueError(f"Scoring weights must sum to 1.0, got {total:.2f}")
        return self


class ScoringConfig(BaseModel):
    weights: ScoringWeights


class StatePensionConfig(BaseModel):
    full_annual_amount: int = Field(gt=0)
    age: int = Field(ge=60, le=75)
    qualifying_years_full: int = Field(ge=1, le=50)
    qualifying_years_min: int = Field(ge=1, le=50)
    triple_lock_growth: float = Field(ge=0.0, le=0.10)


class LifeEventsConfig(BaseModel):
    default_projection_years: int = Field(ge=1, le=50)
    retirement_age: int = Field(ge=50, le=80)
    life_expectancy: int = Field(ge=60, le=110)


class ChildcareConfig(BaseModel):
    tax_free_childcare_pct: float = Field(ge=0.0, le=1.0)
    max_government_topup_per_child: int = Field(ge=0)
    eligible_age_max: int = Field(ge=0, le=18)
    free_hours_3_4_year_olds: int = Field(ge=0, le=50)
    free_hours_hourly_rate: float = Field(ge=0.0)


class InheritanceTaxConfig(BaseModel):
    nil_rate_band: int = Field(gt=0)
    residence_nil_rate: int = Field(ge=0)
    rate: float = Field(ge=0.0, le=1.0)
    spousal_exemption: bool


class GlidePathPoint(BaseModel):
    age: int = Field(ge=18, le=100)
    equity_pct: float = Field(ge=0.0, le=1.0)


class AnnuityConfig(BaseModel):
    rate_per_10k_age_60: int = Field(gt=0)
    rate_per_10k_age_65: int = Field(gt=0)
    rate_per_10k_age_67: int = Field(gt=0)
    rate_per_10k_age_70: int = Field(gt=0)


class ExpenseBenchmarksConfig(BaseModel):
    housing_pct_of_net: float = Field(ge=0.0, le=1.0)
    transport_pct_of_net: float = Field(ge=0.0, le=1.0)
    food_pct_of_net: float = Field(ge=0.0, le=1.0)
    discretionary_pct_of_net: float = Field(ge=0.0, le=1.0)


class LifeEventSimulationConfig(BaseModel):
    surplus_allocation_liquid_pct: float = Field(ge=0.0, le=1.0)
    surplus_allocation_investment_pct: float = Field(ge=0.0, le=1.0)
    debt_principal_fraction: float = Field(ge=0.0, le=1.0)


class GoalPrerequisitesConfig(BaseModel):
    emergency_fund_months_required: int = Field(ge=0, le=24)
    clear_high_interest_debt_first: bool


class SurplusDeploymentConfig(BaseModel):
    emergency_fund_effective_return: float = Field(ge=0.0, le=1.0)
    mortgage_overpayment_return_proxy: float = Field(ge=0.0, le=1.0)


class SensitivityConfig(BaseModel):
    property_price_deltas_pct: list[int]
    retirement_age_deltas: list[int]
    savings_rate_increases_pct: list[int]
    pension_contribution_increases_pct: list[int]
    mortgage_terms: list[int]


class InsuranceConfig(BaseModel):
    life_multiplier_with_dependents: int = Field(ge=1, le=25)
    life_multiplier_mortgage_only: int = Field(ge=1, le=25)
    income_protection_pct: float = Field(ge=0.0, le=1.0)
    critical_illness_expense_months: int = Field(ge=1, le=60)
    pension_inadequacy_life_uplift: float = Field(ge=1.0, le=5.0)


class StudentLoanDtiConfig(BaseModel):
    years_to_writeoff_50pct_weight: int = Field(ge=1, le=30)
    years_to_writeoff_25pct_weight: int = Field(ge=1, le=30)


class DebtSimulationConfig(BaseModel):
    extra_payment_scenarios: list[int]
    max_simulation_months: int = Field(ge=12, le=1200)


class LisaConfig(BaseModel):
    annual_limit: int = Field(gt=0)
    bonus_rate: float = Field(ge=0.0, le=1.0)
    property_price_limit: int = Field(gt=0)
    age_limit: int = Field(ge=18, le=60)


class IsaConfig(BaseModel):
    annual_limit: int = Field(gt=0)


class RetirementConfig(BaseModel):
    safe_withdrawal_rate: float = Field(ge=0.01, le=0.10)
    tax_free_lump_sum_fraction: float = Field(ge=0.0, le=1.0)
    default_income_target: int = Field(gt=0)


class FeeComparisonConfig(BaseModel):
    low_cost_total_pct: float = Field(ge=0.0, le=0.10)
    high_cost_total_pct: float = Field(ge=0.0, le=0.10)


class MortgageCostsConfig(BaseModel):
    solicitor: int = Field(ge=0)
    survey: int = Field(ge=0)
    valuation: int = Field(ge=0)
    arrangement_fee: int = Field(ge=0)
    moving_costs: int = Field(ge=0)
    remortgage_fee: int = Field(ge=0)
    overpayment_annual_limit_pct: float = Field(ge=0.0, le=1.0)
    overpayment_scenarios: list[int]
    rate_offset_from_stress: float = Field(ge=0.0, le=0.10)
    dti_adjustment_cap_pct: float = Field(ge=0.0, le=1.0)
    first_time_buyer_threshold: int = Field(gt=0)
    shared_ownership_deposit_pct: float = Field(ge=0.0, le=1.0)


class ScenariosConfig(BaseModel):
    job_loss_months: list[int]
    rate_shock_bumps_pct: list[int]
    market_drop_pcts: list[int]
    inflation_shock_pcts: list[int]
    income_cut_pcts: list[int]


class SelfEmploymentConfig(BaseModel):
    class4_main_rate: float = Field(ge=0.0, le=1.0)
    class4_additional_rate: float = Field(ge=0.0, le=1.0)
    class2_weekly_rate: float = Field(ge=0.0)


class CapitalGainsTaxConfig(BaseModel):
    annual_exemption: int = Field(ge=0)
    basic_rate: float = Field(ge=0.0, le=1.0)
    higher_rate: float = Field(ge=0.0, le=1.0)
    basic_rate_property: float = Field(ge=0.0, le=1.0)
    higher_rate_property: float = Field(ge=0.0, le=1.0)


class DividendTaxConfig(BaseModel):
    allowance: int = Field(ge=0)
    basic_rate: float = Field(ge=0.0, le=1.0)
    higher_rate: float = Field(ge=0.0, le=1.0)
    additional_rate: float = Field(ge=0.0, le=1.0)


class InsuranceCostRange(BaseModel):
    monthly_low: int = Field(ge=0)
    monthly_high: int = Field(ge=0)


class InsuranceCostEstimates(BaseModel):
    term_life_per_100k: dict[str, InsuranceCostRange]
    income_protection_pct_of_benefit: float = Field(ge=0.0, le=1.0)
    critical_illness_per_100k: dict[str, InsuranceCostRange]


class CostRange(BaseModel):
    low: int = Field(ge=0)
    high: int = Field(ge=0)


class AdvisoryCostEstimates(BaseModel):
    will_simple: CostRange
    will_mirror_couple: CostRange
    lpa_per_type: int = Field(ge=0)
    ifa_initial_consultation: CostRange
    pension_transfer_analysis: CostRange


class ChildCostsConfig(BaseModel):
    nursery_0_2_monthly: int = Field(ge=0)
    nursery_3_4_monthly: int = Field(ge=0)
    after_school_5_11_monthly: int = Field(ge=0)
    secondary_12_17_monthly: int = Field(ge=0)
    university_annual: int = Field(ge=0)


class AssumptionsSchema(BaseModel):
    """Complete schema for assumptions.yaml."""
    tax_year: str
    effective_from: str
    effective_to: str
    inflation: InflationConfig
    investment_returns: InvestmentReturnsConfig
    salary_growth: SalaryGrowthConfig
    tax: TaxConfig
    scottish_tax: ScottishTaxConfig
    stamp_duty: StampDutyConfig
    ltv_rate_tiers: list[LtvTier]
    mortgage: MortgageConfig
    mortgage_products: MortgageProductsConfig
    shared_ownership: SharedOwnershipConfig
    debt: DebtConfig
    student_loans: StudentLoansConfig
    scoring: ScoringConfig
    state_pension: StatePensionConfig
    life_events: LifeEventsConfig
    childcare: ChildcareConfig
    inheritance_tax: InheritanceTaxConfig
    glide_path: list[GlidePathPoint]
    annuity: AnnuityConfig
    expense_benchmarks: ExpenseBenchmarksConfig
    life_event_simulation: LifeEventSimulationConfig
    goal_prerequisites: GoalPrerequisitesConfig
    surplus_deployment: SurplusDeploymentConfig
    sensitivity: SensitivityConfig
    insurance: InsuranceConfig
    student_loan_dti: StudentLoanDtiConfig
    debt_simulation: DebtSimulationConfig
    lisa: LisaConfig
    isa: IsaConfig
    retirement: RetirementConfig
    fee_comparison: FeeComparisonConfig
    mortgage_costs: MortgageCostsConfig
    scenarios: ScenariosConfig
    self_employment: SelfEmploymentConfig
    capital_gains_tax: CapitalGainsTaxConfig
    dividend_tax: DividendTaxConfig
    insurance_cost_estimates: InsuranceCostEstimates
    advisory_cost_estimates: AdvisoryCostEstimates
    child_costs: ChildCostsConfig


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def validate_assumptions(data: dict) -> AssumptionsSchema:
    """Validate assumptions dict against schema. Raises ValidationError on failure."""
    return AssumptionsSchema.model_validate(data)
