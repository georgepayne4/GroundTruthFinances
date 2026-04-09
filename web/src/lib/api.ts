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
  mortgage: Record<string, unknown>;
  life_events: Record<string, unknown>;
  insurance: Record<string, unknown>;
  stress_scenarios: Record<string, unknown>;
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
  income: { total_gross_annual: number; total_gross_monthly: number };
  net_income: { annual: number; monthly: number };
  expenses: { total_monthly: number; total_annual: number; category_breakdown_monthly: Record<string, number> };
  surplus: { monthly: number; annual: number };
  savings_rate: { basic_pct: number; effective_pct_incl_pension: number };
  debt_servicing: { total_monthly: number };
}

export interface DebtAnalysis {
  debts: { name: string; balance: number; interest_rate: number; type: string; months_to_payoff?: number }[];
  summary: { total_balance: number; total_minimum_monthly: number; debt_to_income_gross_pct: number; high_interest_debt_count: number };
  recommended_strategy: string;
}

export interface GoalsAnalysis {
  goals: { name: string; target_amount: number; deadline_years: number; priority: number; status: string; feasibility: string }[];
  summary: { total_goals: number; on_track: number; at_risk: number; unreachable: number };
}

export interface InvestmentsAnalysis {
  current_portfolio: { isa_balance: number; lisa_balance: number; pension_balance: number; total_invested: number };
  pension_analysis: { projected_at_retirement_real?: number; income_replacement_ratio_pct?: number; monthly_contribution_total?: number };
  suggested_allocation?: Record<string, number>;
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
