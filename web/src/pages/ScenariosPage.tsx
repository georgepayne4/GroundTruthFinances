import { useReport } from "../lib/report-context";
import PageHeader from "../components/PageHeader";
import MetricCard from "../components/MetricCard";
import EmptyState from "../components/EmptyState";

function fmt(n: number | undefined | null): string {
  if (n == null) return "-";
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

function gradeColor(grade: string): string {
  if (grade.startsWith("A")) return "text-teal-700 dark:text-teal-400";
  if (grade.startsWith("B")) return "text-blue-700 dark:text-blue-400";
  if (grade.startsWith("C")) return "text-amber-700 dark:text-amber-400";
  if (grade.startsWith("D")) return "text-purple-700 dark:text-purple-400";
  return "text-red-700 dark:text-red-400";
}

export default function ScenariosPage() {
  const { report } = useReport();

  if (!report) return <EmptyState />;

  const { stress_scenarios } = report;
  const { job_loss, interest_rate_shock, market_downturn, compound_scenarios } = stress_scenarios;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Scenarios"
        description="Stress tests and what-if analysis for your financial plan."
      />

      {/* Compound scenario tree */}
      {compound_scenarios && (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {compound_scenarios.branches.map((b) => (
              <div key={b.name} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4 shadow-sm">
                <div className="flex items-center justify-between mb-2">
                  <h4 className="font-semibold text-gray-900 dark:text-gray-100 capitalize text-sm">{b.name}</h4>
                  <span className="text-xs text-gray-500 dark:text-gray-500">{(b.probability * 100).toFixed(0)}%</span>
                </div>
                <div className={`text-2xl font-bold ${gradeColor(b.results.grade)}`}>
                  {Math.round(b.results.score)}
                  <span className="text-sm ml-1">{b.results.grade}</span>
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                  Surplus: {fmt(b.results.surplus_monthly)}/mo
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-500">
                  NPV: {fmt(b.results.npv_surplus)}
                </div>
                {b.score_delta != null && (
                  <div className={`text-xs mt-1 font-medium ${b.score_delta >= 0 ? "text-teal-600 dark:text-teal-400" : "text-red-600 dark:text-red-400"}`}>
                    {b.score_delta >= 0 ? "+" : ""}{b.score_delta.toFixed(1)} pts vs baseline
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Expected values */}
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
              Probability-Weighted Outlook
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
              {Object.entries(compound_scenarios.expected_values).map(([key, val]) => (
                <div key={key}>
                  <div className="text-gray-500 dark:text-gray-500 capitalize">{key.replace(/_/g, " ")}</div>
                  <div className="font-semibold text-gray-900 dark:text-gray-100">
                    {key.includes("score") ? val.toFixed(1) : fmt(val)}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}

      {/* Stress tests */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Job loss */}
        {job_loss && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
              Job Loss Resilience
            </h3>
            <div className="grid grid-cols-2 gap-3 text-sm mb-3">
              <MetricCard label="Monthly Burn" value={fmt(job_loss.monthly_burn_rate)} />
              <MetricCard label="Runway" value={`${job_loss.months_runway.toFixed(1)} months`} sublabel={job_loss.assessment} />
            </div>
            <div className="space-y-2">
              {Object.entries(job_loss.scenarios).map(([key, s]) => (
                <div key={key} className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">{key.replace(/_/g, " ")}</span>
                  <span className={`font-medium ${s.survives ? "text-teal-700 dark:text-teal-400" : "text-red-700 dark:text-red-400"}`}>
                    {s.survives ? "Survives" : `${fmt(s.shortfall)} shortfall`}
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-gray-500 dark:text-gray-500">{job_loss.recommendation}</p>
          </div>
        )}

        {/* Interest rate shock */}
        {interest_rate_shock?.applicable && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
              Interest Rate Shock
            </h3>
            <div className="text-xs text-gray-500 dark:text-gray-500 mb-3">
              Base rate: {interest_rate_shock.base_rate_pct}% ({fmt(interest_rate_shock.base_payment)}/mo)
            </div>
            <div className="space-y-2">
              {Object.entries(interest_rate_shock.scenarios).map(([key, s]) => (
                <div key={key}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-600 dark:text-gray-400">{s.rate_pct}% rate</span>
                    <span className={`font-medium ${s.in_deficit ? "text-red-700 dark:text-red-400" : "text-gray-900 dark:text-gray-100"}`}>
                      {fmt(s.monthly_payment)}/mo
                    </span>
                  </div>
                  <div className="flex justify-between text-xs text-gray-500 dark:text-gray-500">
                    <span>{s.affordability_pct.toFixed(1)}% of income</span>
                    <span>{s.in_deficit ? "In deficit" : `${fmt(s.post_mortgage_surplus)} surplus`}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Market downturn */}
        {market_downturn && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h3 className="mb-3 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
              Market Downturn
            </h3>
            <div className="text-xs text-gray-500 dark:text-gray-500 mb-3">
              Current portfolio: {fmt(market_downturn.current_portfolio)}
            </div>
            <div className="space-y-2">
              {Object.entries(market_downturn.scenarios).map(([key, s]) => (
                <div key={key} className="flex justify-between text-sm">
                  <span className="text-gray-600 dark:text-gray-400">{key.replace(/_/g, " ").replace("minus ", "-")}</span>
                  <span className="text-red-700 dark:text-red-400 font-medium">
                    {fmt(s.portfolio_value)} ({fmt(-s.loss)})
                  </span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-gray-500 dark:text-gray-500">{market_downturn.recommendation}</p>
          </div>
        )}
      </div>

      {/* Compound scenario details */}
      {compound_scenarios?.branches.map((b) => (
        b.recommended_actions && b.recommended_actions.length > 0 && (
          <div key={b.name} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h3 className="mb-2 text-sm font-semibold text-gray-700 dark:text-gray-300 capitalize">
              {b.name} Scenario — Recommended Actions
            </h3>
            <p className="text-xs text-gray-500 dark:text-gray-500 mb-2">{b.description}</p>
            <ul className="space-y-1 text-sm text-gray-600 dark:text-gray-400">
              {b.recommended_actions.map((a, i) => <li key={i}>- {a}</li>)}
            </ul>
          </div>
        )
      ))}
    </div>
  );
}
