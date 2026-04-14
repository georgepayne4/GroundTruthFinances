import { useReport } from "../lib/report-context";
import PageHeader from "../components/PageHeader";
import MetricCard from "../components/MetricCard";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import { PageSkeleton } from "../components/Skeleton";

function fmt(n: number | undefined | null): string {
  if (n == null) return "-";
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

function riskColor(tier: string): string {
  if (tier === "high") return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
  if (tier === "medium") return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
  return "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200";
}

export default function DebtPage() {
  const { report, loading, error } = useReport();

  if (error) return <ErrorBanner title="Analysis failed" message={error} />;
  if (loading && !report) return <PageSkeleton />;
  if (!report) return <EmptyState />;

  const { debt } = report;
  const { debts, summary, recommended_strategy } = debt;

  if (debts.length === 0) {
    return (
      <div>
        <PageHeader title="Debt" description="You have no outstanding debts." />
        <div className="rounded-xl border border-teal-200 dark:border-teal-800 bg-teal-50 dark:bg-teal-950 p-6 text-sm text-teal-800 dark:text-teal-200">
          Debt-free — well done!
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Debt"
        description="Debt balances, repayment strategies, and payoff timeline."
      />

      {/* Summary metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Total Debt" value={fmt(summary.total_balance)} sublabel={`${summary.weighted_average_rate_pct.toFixed(1)}% avg rate`} />
        <MetricCard label="Monthly Payments" value={fmt(summary.total_minimum_monthly)} sublabel={`DTI: ${summary.debt_to_income_gross_pct.toFixed(1)}%`} />
        <MetricCard label="Total Interest" value={fmt(summary.total_interest_if_minimum_only)} sublabel="if minimums only" />
        <MetricCard label="Strategy" value={recommended_strategy.charAt(0).toUpperCase() + recommended_strategy.slice(1)} sublabel={`${summary.high_interest_debt_count} high-interest debt${summary.high_interest_debt_count !== 1 ? "s" : ""}`} />
      </div>

      {/* Debt cards */}
      <div className="space-y-4">
        {debts.map((d) => (
          <div key={d.name} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-gray-100">{d.name}</h3>
                <p className="text-xs text-gray-500 dark:text-gray-500 capitalize">{d.type.replace(/_/g, " ")}</p>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${riskColor(d.risk_tier)}`}>
                {d.risk_tier} risk
              </span>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              <div>
                <div className="text-gray-500 dark:text-gray-500">Balance</div>
                <div className="font-semibold text-gray-900 dark:text-gray-100">{fmt(d.balance)}</div>
              </div>
              <div>
                <div className="text-gray-500 dark:text-gray-500">Interest Rate</div>
                <div className="font-semibold text-gray-900 dark:text-gray-100">{d.interest_rate_pct}%</div>
              </div>
              <div>
                <div className="text-gray-500 dark:text-gray-500">Monthly Payment</div>
                <div className="font-semibold text-gray-900 dark:text-gray-100">{fmt(d.minimum_payment_monthly)}</div>
              </div>
              <div>
                <div className="text-gray-500 dark:text-gray-500">Payoff</div>
                <div className="font-semibold text-gray-900 dark:text-gray-100">
                  {d.years_to_payoff != null ? `${d.years_to_payoff.toFixed(1)} years` : "-"}
                </div>
              </div>
            </div>
            {d.total_interest_if_minimum != null && d.total_interest_if_minimum > 0 && (
              <div className="mt-3 text-xs text-gray-500 dark:text-gray-500">
                Total interest if minimum payments only: {fmt(d.total_interest_if_minimum)}
              </div>
            )}
            {d.write_off_intelligence && (
              <div className="mt-3 rounded-lg bg-gray-50 dark:bg-gray-800 p-3 text-xs text-gray-600 dark:text-gray-400">
                <span className="font-medium text-gray-700 dark:text-gray-300">Insight: </span>
                {d.write_off_intelligence.reasoning}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
