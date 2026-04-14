import { useReport } from "../lib/report-context";
import CashflowBar from "../components/CashflowBar";
import CategoryScores from "../components/CategoryScores";
import MetricCard from "../components/MetricCard";
import PriorityActions from "../components/PriorityActions";
import ScoreGauge from "../components/ScoreGauge";
import EmptyState from "../components/EmptyState";
import ErrorBanner from "../components/ErrorBanner";
import { DashboardSkeleton } from "../components/Skeleton";

function fmt(n: number | undefined | null): string {
  if (n == null) return "-";
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

export default function HomePage() {
  const { report, loading, error } = useReport();

  if (error) return <ErrorBanner title="Analysis failed" message={error} />;
  if (loading && !report) return <DashboardSkeleton />;
  if (!report) return <EmptyState />;

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
        <div className="rounded-xl border border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950 p-5">
          <h3 className="text-sm font-semibold text-amber-700 dark:text-amber-300 uppercase tracking-wide mb-2">
            Validation Flags
          </h3>
          <div className="space-y-1">
            {report.validation.flags.map((f, i) => (
              <div key={i} className="text-sm text-amber-800 dark:text-amber-200">
                <span className="font-medium">[{f.severity}]</span> {f.field}: {f.message}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
