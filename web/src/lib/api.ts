const API_KEY = import.meta.env.VITE_API_KEY || "dev-key-change-me";
const BASE = "/api/v1";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-API-Key": API_KEY,
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || `API error ${res.status}`);
  }
  return res.json();
}

export interface AnalyseResponse {
  profile_name: string | null;
  overall_score: number | null;
  grade: string | null;
  report: Report;
  run_id: number | null;
}

export interface Report {
  meta: { profile_name?: string; generated_at?: string; engine_version?: string };
  scoring: Scoring;
  cashflow: Cashflow;
  debt: DebtAnalysis;
  goals: GoalsAnalysis;
  investments: InvestmentsAnalysis;
  mortgage: MortgageAnalysis;
  life_events: LifeEventsAnalysis;
  insurance: Record<string, unknown>;
  stress_scenarios: StressScenarios;
  estate: Record<string, unknown>;
  sensitivity_analysis: Record<string, unknown>;
  advisor_insights: AdvisorInsights;
  validation: { flags: ValidationFlag[]; error_count: number; warning_count: number; info_count: number };
}

export interface Scoring {
  overall_score: number;
  grade: string;
  categories: Record<string, { score: number; weight: number; detail: string; benchmark?: string }>;
}

export interface Cashflow {
  income: { primary_gross_annual: number; partner_gross_annual: number; other_income_annual: number; total_gross_annual: number; total_gross_monthly: number };
  deductions: { income_tax_annual: number; national_insurance_annual: number; other_income_tax_annual: number; pension_personal_annual: number; pension_employer_annual: number; total_deductions_annual: number };
  net_income: { annual: number; monthly: number };
  expenses: { total_monthly: number; total_annual: number; category_breakdown_monthly: Record<string, number> };
  surplus: { monthly: number; annual: number };
  savings_rate: { basic_pct: number; effective_pct_incl_pension: number };
  debt_servicing: { total_monthly: number; total_annual: number };
  spending_benchmarks?: { comparisons: { category: string; actual_monthly: number; actual_pct_of_net: number; benchmark_pct_of_net: number; benchmark_monthly: number; delta_monthly: number; above_benchmark: boolean }[] };
}

export interface DebtItem {
  name: string;
  type: string;
  balance: number;
  interest_rate: number;
  interest_rate_pct: number;
  minimum_payment_monthly: number;
  months_to_payoff?: number;
  years_to_payoff?: number;
  total_interest_if_minimum?: number;
  risk_tier: string;
  avalanche_priority?: number;
  snowball_priority?: number;
  income_contingent?: boolean;
  write_off_intelligence?: { overpay_recommendation: string; reasoning: string };
}

export interface DebtAnalysis {
  debts: DebtItem[];
  summary: { total_balance: number; total_minimum_monthly: number; debt_to_income_gross_pct: number; high_interest_debt_count: number; weighted_average_rate_pct: number; total_interest_if_minimum_only: number; longest_payoff_months: number };
  recommended_strategy: string;
}

export interface GoalItem {
  name: string;
  category: string;
  priority: string;
  priority_rank: number;
  target_nominal: number;
  target_inflation_adjusted: number;
  current_progress: number;
  progress_pct: number;
  remaining_gap: number;
  deadline_years: number;
  deadline_months: number;
  required_monthly: number;
  allocated_monthly: number;
  feasibility_with_allocation: string;
  blocked_by?: string[];
  what_would_it_take?: { shortfall_monthly: number; option_increase_income_monthly: number; option_reduce_expenses_monthly: number; option_combined_income_and_expense: number };
}

export interface GoalsAnalysis {
  goals: GoalItem[];
  summary: { total_goals: number; on_track: number; at_risk: number; unreachable: number; blocked?: number; total_required_monthly: number; available_surplus_monthly: number; surplus_covers_goals: boolean; shortfall_monthly?: number };
}

export interface GrowthProjection {
  years: number;
  nominal_value: number;
  real_value_today_terms: number;
  total_contributions: number;
  investment_growth: number;
}

export interface InvestmentsAnalysis {
  current_portfolio: { isa_balance: number; lisa_balance: number; pension_balance: number; other_investments: number; total_invested: number };
  risk_profile: string;
  expected_annual_return_pct: number;
  net_return_after_fees_pct: number;
  suggested_allocation?: Record<string, number>;
  risk_metrics?: { expected_return_pct: number; historical_volatility_pct: number; max_drawdown_pct: number; worst_year_pct: number; negative_year_probability_pct: number; note: string };
  fee_analysis?: { current_fees: Record<string, number>; fee_drag_over_term: number; fee_comparison: Record<string, number>; projection_years: number };
  growth_projections?: GrowthProjection[];
  pension_analysis: { current_balance: number; monthly_contribution_total: number; annual_contribution_total: number; projected_at_retirement_nominal?: number; projected_at_retirement_real?: number; tax_free_lump_sum?: number; annual_income_net?: number; income_replacement_ratio_pct?: number; adequate?: boolean; fund_longevity_years?: number; years_in_retirement?: number };
}

// Mortgage types
export interface LtvBand {
  ltv_pct: number;
  deposit_required: number;
  extra_deposit_needed: number;
  mortgage_amount: number;
  rate_pct: number;
  monthly_payment: number;
  total_interest: number;
  achievable: boolean;
}

export interface OverpaymentScenario {
  extra_monthly: number;
  new_payoff_years: number;
  months_saved: number;
  years_saved: number;
  total_interest_saved: number;
  exceeds_10pct_limit: boolean;
}

export interface MortgageAnalysis {
  applicable: boolean;
  target_property_value?: number;
  first_time_buyer?: boolean;
  borrowing?: { income_used: number; income_multiple: number; max_borrowing_gross: number; max_borrowing_adjusted: number; required_mortgage: number; can_borrow_enough: boolean };
  deposit?: { required_at_preferred_pct: number; available_for_deposit: number; gap: number; adequate: boolean; months_to_save_gap: number };
  repayment?: { mortgage_amount: number; term_years: number; estimated_rate_pct: number; monthly_repayment: number; total_repayment: number; total_interest: number; replaces_rent: number; net_monthly_change: number; post_mortgage_surplus: number };
  affordability?: { repayment_to_income_pct: number; stress_test_to_income_pct: number; affordable: boolean; stress_test_passes: boolean };
  ltv_analysis?: { current_ltv_pct: number; bands: LtvBand[] };
  overpayment_analysis?: OverpaymentScenario[];
  readiness?: { ready: boolean; blockers: string[]; strengths: string[] };
}

// Life events types
export interface TimelineYear {
  year: number;
  age: number;
  events: string[] | null;
  gross_income_annual: number;
  net_income_annual: number;
  expenses_annual: number;
  debt_payments_annual: number;
  annual_surplus: number;
  savings_rate_pct: number;
  liquid_savings: number;
  investments: number;
  total_debt: number;
  net_worth: number;
  property_value?: number;
  mortgage_balance?: number;
  equity?: number;
}

export interface Milestone {
  year: number;
  age: number;
  type: string;
  message: string;
}

export interface LifeEventsAnalysis {
  projection_years: number;
  timeline: TimelineYear[];
  milestones?: Milestone[];
  summary?: Record<string, unknown>;
}

// Stress scenario types
export interface CompoundBranch {
  name: string;
  description: string;
  probability: number;
  nudge_category: string;
  results: { score: number; grade: string; surplus_monthly: number; npv_surplus: number; goal_feasibility: { name: string; status: string; on_track: boolean }[] };
  recommended_actions?: string[];
  score_delta?: number;
}

export interface StressScenarios {
  job_loss?: { monthly_burn_rate: number; liquid_savings: number; months_runway: number; assessment: string; recommendation: string; scenarios: Record<string, { total_cost: number; shortfall: number; survives: boolean }> };
  interest_rate_shock?: { applicable: boolean; base_rate_pct: number; base_payment: number; scenarios: Record<string, { rate_pct: number; monthly_payment: number; affordability_pct: number; affordable: boolean; post_mortgage_surplus: number; in_deficit: boolean }> };
  market_downturn?: { current_portfolio: number; recommendation: string; scenarios: Record<string, { portfolio_value: number; loss: number }> };
  compound_scenarios?: { branches: CompoundBranch[]; expected_values: Record<string, number>; decision_summary: Record<string, unknown>; baseline_npv: number };
}

export interface AdvisorInsights {
  executive_summary?: string;
  top_priorities?: { priority: number; category: string; title: string; detail: string }[];
  surplus_deployment_plan?: { applicable: boolean; deployment_order?: { action: string; allocated_monthly: number; effective_return_pct: number; guaranteed: boolean }[] };
}

export interface ValidationFlag {
  field: string;
  message: string;
  severity: string;
}

export function analyse(profile: Record<string, unknown>): Promise<AnalyseResponse> {
  return request<AnalyseResponse>("/analyse", {
    method: "POST",
    body: JSON.stringify({ profile }),
  });
}

export function getAssumptions(): Promise<Record<string, unknown>> {
  return request("/assumptions");
}

export interface HistoryRun {
  id: number;
  timestamp: string;
  profile_name: string;
  overall_score: number;
  grade: string;
  surplus_monthly: number;
  net_worth: number;
}

export function getHistory(limit = 10): Promise<{ runs: HistoryRun[]; count: number }> {
  return request(`/history?limit=${limit}`);
}
