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
    employer_national_insurance_rate: float = Field(default=0.15, ge=0.0, le=1.0)
    employer_ni_threshold: int = Field(default=5000, gt=0)
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
    additional_property_surcharge: float = Field(default=0.05, ge=0.0, le=0.20)
    non_resident_surcharge: float = Field(default=0.02, ge=0.0, le=0.10)


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
    credit_utilisation_warning_pct: float = Field(default=0.30, ge=0.0, le=1.0)
    credit_utilisation_high_pct: float = Field(default=0.50, ge=0.0, le=1.0)


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


class TaperReliefBand(BaseModel):
    min_years: int = Field(ge=0, le=10)
    relief_pct: float = Field(ge=0.0, le=1.0)


class InheritanceTaxConfig(BaseModel):
    nil_rate_band: int = Field(gt=0)
    residence_nil_rate: int = Field(ge=0)
    rate: float = Field(ge=0.0, le=1.0)
    charitable_rate: float = Field(default=0.36, ge=0.0, le=1.0)
    charitable_threshold_pct: float = Field(default=0.10, ge=0.0, le=1.0)
    spousal_exemption: bool
    annual_gift_exemption: int = Field(default=3000, ge=0)
    small_gift_limit: int = Field(default=250, ge=0)
    pet_full_exemption_years: int = Field(default=7, ge=1, le=14)
    taper_relief: list[TaperReliefBand] = Field(default_factory=list)
    rnrb_taper_threshold: int = Field(default=2000000, ge=0)
    rnrb_taper_rate: float = Field(default=0.50, ge=0.0, le=1.0)


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
    max_effective_tax_rate: float = Field(default=0.60, ge=0.0, le=1.0)
    net_worth_drop_warning_pct: float = Field(default=0.20, ge=0.0, le=1.0)


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


class PensionAnnualAllowanceConfig(BaseModel):
    standard: int = Field(gt=0)
    taper_threshold: int = Field(gt=0)
    taper_reduction_rate: float = Field(ge=0.0, le=1.0)
    minimum_allowance: int = Field(gt=0)
    tax_charge_rate_basic: float = Field(ge=0.0, le=1.0)
    tax_charge_rate_higher: float = Field(ge=0.0, le=1.0)
    tax_charge_rate_additional: float = Field(ge=0.0, le=1.0)


class RetirementConfig(BaseModel):
    safe_withdrawal_rate: float = Field(ge=0.01, le=0.10)
    tax_free_lump_sum_fraction: float = Field(ge=0.0, le=1.0)
    default_income_target: int = Field(gt=0)


class FeeComparisonConfig(BaseModel):
    low_cost_total_pct: float = Field(ge=0.0, le=0.10)
    high_cost_total_pct: float = Field(ge=0.0, le=0.10)


class RiskProfileAllocation(BaseModel):
    government_bonds: int = Field(default=0, ge=0, le=100)
    corporate_bonds: int = Field(default=0, ge=0, le=100)
    uk_equity: int = Field(default=0, ge=0, le=100)
    global_equity: int = Field(default=0, ge=0, le=100)
    emerging_markets: int = Field(default=0, ge=0, le=100)
    property_funds: int = Field(default=0, ge=0, le=100)
    cash: int = Field(default=0, ge=0, le=100)

    @model_validator(mode="after")
    def allocation_sums_to_100(self) -> RiskProfileAllocation:
        total = (
            self.government_bonds + self.corporate_bonds + self.uk_equity
            + self.global_equity + self.emerging_markets + self.property_funds + self.cash
        )
        if total != 100:
            raise ValueError(f"Risk profile allocation must sum to 100, got {total}")
        return self


class RiskProfileConfig(BaseModel):
    allocation: RiskProfileAllocation
    historical_volatility: float = Field(ge=0.0, le=0.50)
    max_drawdown: float = Field(le=0.0, ge=-1.0)
    worst_year: float = Field(le=0.0, ge=-1.0)
    negative_year_probability: float = Field(ge=0.0, le=1.0)


class RiskProfilesConfig(BaseModel):
    conservative: RiskProfileConfig
    moderate: RiskProfileConfig
    aggressive: RiskProfileConfig
    very_aggressive: RiskProfileConfig


class InvestmentAnalysisDefaultsConfig(BaseModel):
    dividend_yield: float = Field(default=0.02, ge=0.0, le=0.20)
    rebalancing_drift_threshold_pct: float = Field(default=5.0, ge=0.0, le=100.0)
    goal_monte_carlo_sim_cap: int = Field(default=500, ge=100, le=10000)


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


class LifetimeCashflowConfig(BaseModel):
    retirement_spending_pct_of_pre: float = Field(default=0.70, ge=0.0, le=1.0)
    late_life_spending_reduction: float = Field(default=0.15, ge=0.0, le=0.50)
    care_cost_annual_home: int = Field(default=15000, ge=0)
    care_cost_annual_residential: int = Field(default=40000, ge=0)
    care_provision_start_age: int = Field(default=85, ge=70, le=100)
    state_pension_deferral_rate: float = Field(default=0.058, ge=0.0, le=0.20)


class CapacityForLossConfig(BaseModel):
    emergency_months_for_full: int = Field(default=6, ge=1, le=24)
    emergency_months_for_moderate: int = Field(default=3, ge=1, le=12)
    full_drawdown_pct: float = Field(default=0.20, ge=0.0, le=1.0)
    moderate_drawdown_pct: float = Field(default=0.10, ge=0.0, le=1.0)
    low_drawdown_pct: float = Field(default=0.05, ge=0.0, le=1.0)


class RiskProfilingConfig(BaseModel):
    short_term_years: int = Field(default=5, ge=1, le=10)
    long_term_years: int = Field(default=15, ge=5, le=30)
    capacity_for_loss: CapacityForLossConfig = Field(default_factory=CapacityForLossConfig)


class MonteCarloConfig(BaseModel):
    num_simulations: int = Field(default=1000, ge=100, le=100000)
    percentiles: list[int] = Field(default=[10, 25, 50, 75, 90])
    random_seed: int | None = None
    inflation_volatility: float = Field(default=0.01, ge=0.0, le=0.10)


class CompoundScenarioDefinition(BaseModel):
    name: str
    description: str
    probability: float = Field(ge=0.0, le=1.0)
    income_multiplier: float = Field(default=1.0, ge=0.0)
    income_loss_months: int = Field(default=0, ge=0, le=12)
    expense_multiplier: float = Field(default=1.0, ge=0.0)
    investment_return_override: float | None = None
    interest_rate_bump_pct: float = Field(default=0.0)
    inflation_override_pct: float | None = None
    recommended_actions: list[str] = []
    nudge_category: str = "steady"


class CompoundScenariosConfig(BaseModel):
    discount_rate_override: float | None = None
    scenarios: list[CompoundScenarioDefinition] = []


class AssumptionsSchema(BaseModel):
    """Complete schema for assumptions.yaml."""
    schema_version: int = Field(default=1, ge=1)
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
    pension_annual_allowance: PensionAnnualAllowanceConfig
    fee_comparison: FeeComparisonConfig
    risk_profiles: RiskProfilesConfig
    investment_analysis_defaults: InvestmentAnalysisDefaultsConfig
    mortgage_costs: MortgageCostsConfig
    scenarios: ScenariosConfig
    self_employment: SelfEmploymentConfig
    capital_gains_tax: CapitalGainsTaxConfig
    dividend_tax: DividendTaxConfig
    insurance_cost_estimates: InsuranceCostEstimates
    advisory_cost_estimates: AdvisoryCostEstimates
    child_costs: ChildCostsConfig
    lifetime_cashflow: LifetimeCashflowConfig | None = None
    risk_profiling: RiskProfilingConfig | None = None
    monte_carlo: MonteCarloConfig | None = None
    compound_scenarios: CompoundScenariosConfig | None = None


# ---------------------------------------------------------------------------
# Validation functions
# ---------------------------------------------------------------------------

def validate_assumptions(data: dict) -> AssumptionsSchema:
    """Validate assumptions dict against schema. Raises ValidationError on failure."""
    return AssumptionsSchema.model_validate(data)
