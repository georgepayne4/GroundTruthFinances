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

function statusColor(status: string): string {
  if (status === "on_track") return "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200";
  if (status === "at_risk") return "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200";
  if (status === "blocked") return "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200";
  if (status === "unreachable") return "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
  return "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200";
}

function statusLabel(status: string): string {
  return status.replace(/_/g, " ");
}

function progressColor(pct: number): string {
  if (pct >= 75) return "bg-teal-500";
  if (pct >= 40) return "bg-blue-500";
  if (pct >= 10) return "bg-amber-500";
  return "bg-red-500";
}

export default function GoalsPage() {
  const { report, loading, error } = useReport();

  if (error) return <ErrorBanner title="Analysis failed" message={error} />;
  if (loading && !report) return <PageSkeleton />;
  if (!report) return <EmptyState />;

  const { goals } = report;
  const { summary } = goals;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Goals"
        description="Track progress towards your financial goals."
      />

      {/* Summary metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Total Goals" value={summary.total_goals} sublabel={`${summary.on_track} on track`} />
        <MetricCard
          label="Monthly Required"
          value={fmt(summary.total_required_monthly)}
          sublabel={summary.surplus_covers_goals ? "Covered by surplus" : `${fmt(summary.shortfall_monthly)} shortfall`}
        />
        <MetricCard label="Available Surplus" value={fmt(summary.available_surplus_monthly)} sublabel="per month" />
        <MetricCard
          label="Status"
          value={summary.blocked ? `${summary.blocked} blocked` : summary.at_risk > 0 ? `${summary.at_risk} at risk` : "All good"}
          sublabel={summary.unreachable > 0 ? `${summary.unreachable} unreachable` : undefined}
        />
      </div>

      {/* Goal cards */}
      <div className="space-y-4">
        {goals.goals.map((g) => (
          <div key={g.name} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <div className="flex items-start justify-between mb-3">
              <div>
                <h3 className="font-semibold text-gray-900 dark:text-gray-100">{g.name}</h3>
                <p className="text-xs text-gray-500 dark:text-gray-500 capitalize">
                  {g.category.replace(/_/g, " ")} · {g.priority} priority · {g.deadline_years} year{g.deadline_years !== 1 ? "s" : ""}
                </p>
              </div>
              <span className={`text-xs px-2 py-0.5 rounded-full font-medium capitalize ${statusColor(g.feasibility_with_allocation)}`}>
                {statusLabel(g.feasibility_with_allocation)}
              </span>
            </div>

            {/* Progress bar */}
            <div className="mb-3">
              <div className="flex justify-between text-xs text-gray-500 dark:text-gray-500 mb-1">
                <span>{fmt(g.current_progress)} saved</span>
                <span>{fmt(g.target_inflation_adjusted)} target</span>
              </div>
              <div className="h-2.5 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${progressColor(g.progress_pct)}`}
                  style={{ width: `${Math.min(g.progress_pct, 100)}%` }}
                />
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                {g.progress_pct.toFixed(0)}% complete · {fmt(g.remaining_gap)} remaining
              </div>
            </div>

            {/* Allocation info */}
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-sm">
              <div>
                <div className="text-gray-500 dark:text-gray-500">Required/mo</div>
                <div className="font-semibold text-gray-900 dark:text-gray-100">{fmt(g.required_monthly)}</div>
              </div>
              <div>
                <div className="text-gray-500 dark:text-gray-500">Allocated/mo</div>
                <div className="font-semibold text-gray-900 dark:text-gray-100">{fmt(g.allocated_monthly)}</div>
              </div>
              {g.what_would_it_take && (
                <div>
                  <div className="text-gray-500 dark:text-gray-500">Shortfall/mo</div>
                  <div className="font-semibold text-red-700 dark:text-red-400">{fmt(g.what_would_it_take.shortfall_monthly)}</div>
                </div>
              )}
            </div>

            {/* Blocked reasons */}
            {g.blocked_by && g.blocked_by.length > 0 && (
              <div className="mt-3 rounded-lg bg-red-50 dark:bg-red-950 p-3 text-xs text-red-700 dark:text-red-300">
                <span className="font-medium">Blocked: </span>
                {g.blocked_by.join(". ")}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
