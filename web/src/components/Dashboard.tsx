import { useState } from "react";
import type { Report } from "../lib/api";
import { analyse } from "../lib/api";
import CashflowBar from "./CashflowBar";
import CategoryScores from "./CategoryScores";
import MetricCard from "./MetricCard";
import PriorityActions from "./PriorityActions";
import ScoreGauge from "./ScoreGauge";

const SAMPLE_PROFILE = {
  personal: {
    name: "Dashboard Demo",
    age: 30,
    retirement_age: 67,
    dependents: 0,
    risk_profile: "moderate",
    employment_type: "employed",
  },
  income: { primary_gross_annual: 50000 },
  expenses: { housing: { rent_monthly: 1000 }, transport: { fuel_monthly: 150 }, living: { groceries_monthly: 400 } },
  savings: {
    emergency_fund: 5000,
    pension_balance: 15000,
    pension_personal_contribution_pct: 0.05,
    pension_employer_contribution_pct: 0.03,
    isa_balance: 3000,
  },
  debts: [
    { name: "Credit Card", type: "credit_card", balance: 2000, interest_rate: 19.9, minimum_payment_monthly: 50 },
  ],
  goals: [
    { name: "Emergency Fund", target_amount: 10000, deadline_years: 2, priority: 1, category: "savings" },
    { name: "House Deposit", target_amount: 30000, deadline_years: 5, priority: 2, category: "property" },
  ],
};

function fmt(n: number | undefined | null): string {
  if (n == null) return "-";
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

export default function Dashboard() {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profileJson, setProfileJson] = useState(JSON.stringify(SAMPLE_PROFILE, null, 2));

  async function handleAnalyse() {
    setLoading(true);
    setError(null);
    try {
      const parsed = JSON.parse(profileJson);
      const result = await analyse(parsed);
      setReport(result.report);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <a href="#main-content" className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-gray-900 focus:px-4 focus:py-2 focus:text-white">
        Skip to main content
      </a>
      <header className="border-b border-gray-200 bg-white" role="banner">
        <div className="mx-auto max-w-7xl px-6 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-gray-900">GroundTruth</h1>
            <p className="text-xs text-gray-600">Financial Planning Dashboard</p>
          </div>
          <button
            onClick={handleAnalyse}
            disabled={loading}
            aria-busy={loading}
            className="rounded-lg bg-gray-900 px-5 py-2 text-sm font-medium text-white hover:bg-gray-700 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:ring-offset-2 disabled:opacity-50 transition-colors"
          >
            {loading ? "Analysing..." : "Run Analysis"}
          </button>
        </div>
      </header>

      <main id="main-content" className="mx-auto max-w-7xl px-6 py-6" role="main">
        {error && (
          <div role="alert" className="mb-4 rounded-lg bg-red-50 border border-red-200 px-4 py-3 text-sm text-red-800">
            {error}
          </div>
        )}

        {!report ? (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="lg:col-span-2">
              <div className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
                <label htmlFor="profile-json" className="block text-sm font-semibold text-gray-700 uppercase tracking-wide mb-3">
                  Profile JSON
                </label>
                <textarea
                  id="profile-json"
                  value={profileJson}
                  onChange={(e) => setProfileJson(e.target.value)}
                  className="w-full h-80 font-mono text-xs border border-gray-300 rounded-lg p-3 focus:outline-none focus:ring-2 focus:ring-gray-900 focus:border-transparent"
                  spellCheck={false}
                  aria-describedby="profile-json-help"
                />
                <p id="profile-json-help" className="mt-2 text-xs text-gray-600">
                  Edit the profile above and click "Run Analysis" to see your financial health dashboard.
                </p>
              </div>
            </div>
          </div>
        ) : (
          <ReportDashboard report={report} />
        )}
      </main>
    </div>
  );
}

function ReportDashboard({ report }: { report: Report }) {
  const { scoring, cashflow, debt, goals, investments, advisor_insights } = report;

  return (
    <div className="space-y-6">
      {/* Score and key metrics */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
        <div className="relative flex items-center justify-center lg:col-span-1">
          <ScoreGauge score={scoring.overall_score} grade={scoring.grade} />
        </div>
        <div className="lg:col-span-4 grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard
            label="Monthly Surplus"
            value={fmt(cashflow.surplus.monthly)}
            sublabel={`${cashflow.savings_rate.basic_pct.toFixed(1)}% savings rate`}
          />
          <MetricCard
            label="Total Debt"
            value={fmt(debt.summary.total_balance)}
            sublabel={`${debt.summary.high_interest_debt_count} high-interest`}
          />
          <MetricCard
            label="Goals"
            value={`${goals.summary.on_track}/${goals.summary.total_goals} on track`}
            sublabel={goals.summary.at_risk > 0 ? `${goals.summary.at_risk} at risk` : "All good"}
          />
          <MetricCard
            label="Investments"
            value={fmt(investments.current_portfolio.total_invested)}
            sublabel={investments.pension_analysis?.income_replacement_ratio_pct
              ? `${investments.pension_analysis.income_replacement_ratio_pct.toFixed(0)}% replacement`
              : undefined}
          />
        </div>
      </div>

      {/* Charts and details */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CashflowBar cashflow={cashflow} />
        <CategoryScores scoring={scoring} />
      </div>

      {/* Priorities */}
      <PriorityActions insights={advisor_insights} />

      {/* Validation flags */}
      {report.validation.flags.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-5">
          <h3 className="text-sm font-semibold text-amber-700 uppercase tracking-wide mb-2">
            Validation Flags
          </h3>
          <div className="space-y-1">
            {report.validation.flags.map((f, i) => (
              <div key={i} className="text-sm text-amber-800">
                <span className="font-medium">[{f.severity}]</span> {f.field}: {f.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
