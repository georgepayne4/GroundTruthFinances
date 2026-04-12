import { useReport } from "../lib/report-context";
import PageHeader from "../components/PageHeader";
import MetricCard from "../components/MetricCard";
import EmptyState from "../components/EmptyState";

function fmt(n: number | undefined | null): string {
  if (n == null) return "-";
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

function allocationColor(key: string): string {
  const colors: Record<string, string> = {
    government_bonds: "bg-blue-400",
    corporate_bonds: "bg-indigo-400",
    uk_equity: "bg-teal-500",
    global_equity: "bg-emerald-500",
    property_funds: "bg-amber-500",
    cash: "bg-gray-400",
  };
  return colors[key] || "bg-purple-400";
}

export default function InvestmentsPage() {
  const { report } = useReport();

  if (!report) return <EmptyState />;

  const { investments } = report;
  const { current_portfolio, pension_analysis, suggested_allocation, risk_metrics, fee_analysis, growth_projections } = investments;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Investments"
        description="Portfolio analysis, pension projections, and investment strategy."
      />

      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Total Invested" value={fmt(current_portfolio.total_invested)} sublabel={`${investments.risk_profile} risk profile`} />
        <MetricCard label="Pension Balance" value={fmt(pension_analysis.current_balance)} sublabel={`${fmt(pension_analysis.monthly_contribution_total)}/mo contributions`} />
        <MetricCard
          label="Retirement Projection"
          value={pension_analysis.projected_at_retirement_real != null ? fmt(pension_analysis.projected_at_retirement_real) : "-"}
          sublabel="in today's money"
        />
        <MetricCard
          label="Income Replacement"
          value={pension_analysis.income_replacement_ratio_pct != null ? `${pension_analysis.income_replacement_ratio_pct.toFixed(0)}%` : "-"}
          sublabel={pension_analysis.adequate ? "Adequate" : "Below target"}
        />
      </div>

      {/* Portfolio breakdown */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
          Current Portfolio
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          {[
            { label: "ISA", value: current_portfolio.isa_balance },
            { label: "LISA", value: current_portfolio.lisa_balance },
            { label: "Pension", value: current_portfolio.pension_balance },
            { label: "Other", value: current_portfolio.other_investments },
          ].filter((item) => item.value > 0).map((item) => (
            <div key={item.label}>
              <div className="text-gray-500 dark:text-gray-500">{item.label}</div>
              <div className="text-xl font-bold text-gray-900 dark:text-gray-100">{fmt(item.value)}</div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Suggested allocation */}
        {suggested_allocation && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
              Suggested Allocation
            </h3>
            <div className="space-y-2">
              {Object.entries(suggested_allocation)
                .sort(([, a], [, b]) => b - a)
                .map(([key, pct]) => (
                  <div key={key}>
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-700 dark:text-gray-300 capitalize">{key.replace(/_/g, " ")}</span>
                      <span className="font-medium text-gray-900 dark:text-gray-100">{pct}%</span>
                    </div>
                    <div className="h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
                      <div className={`h-full rounded-full ${allocationColor(key)}`} style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                ))}
            </div>
          </div>
        )}

        {/* Risk metrics */}
        {risk_metrics && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
              Risk Profile
            </h3>
            <div className="space-y-3 text-sm">
              {[
                { label: "Expected return", value: `${risk_metrics.expected_return_pct}%` },
                { label: "Volatility", value: `${risk_metrics.historical_volatility_pct}%` },
                { label: "Max drawdown", value: `${risk_metrics.max_drawdown_pct}%` },
                { label: "Worst year", value: `${risk_metrics.worst_year_pct}%` },
                { label: "Negative year probability", value: `${risk_metrics.negative_year_probability_pct}%` },
              ].map((row) => (
                <div key={row.label} className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">{row.label}</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{row.value}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-xs text-gray-500 dark:text-gray-500">{risk_metrics.note}</p>
          </div>
        )}
      </div>

      {/* Growth projections */}
      {growth_projections && growth_projections.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
          <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
            Growth Projections
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 text-gray-600 dark:text-gray-400 font-medium">Years</th>
                  <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Contributions</th>
                  <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Growth</th>
                  <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Nominal</th>
                  <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Real Value</th>
                </tr>
              </thead>
              <tbody>
                {growth_projections.map((p) => (
                  <tr key={p.years} className="border-b border-gray-100 dark:border-gray-800">
                    <td className="py-2 text-gray-900 dark:text-gray-100">{p.years}</td>
                    <td className="py-2 text-right text-gray-600 dark:text-gray-400">{fmt(p.total_contributions)}</td>
                    <td className="py-2 text-right text-teal-700 dark:text-teal-400">{fmt(p.investment_growth)}</td>
                    <td className="py-2 text-right text-gray-900 dark:text-gray-100 font-medium">{fmt(p.nominal_value)}</td>
                    <td className="py-2 text-right text-gray-900 dark:text-gray-100 font-medium">{fmt(p.real_value_today_terms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Fee analysis */}
      {fee_analysis && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
          <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
            Fee Impact ({fee_analysis.projection_years} years)
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-sm">
            <div className="rounded-lg bg-gray-50 dark:bg-gray-800 p-3">
              <div className="text-gray-500 dark:text-gray-500">Current fees</div>
              <div className="text-xl font-bold text-gray-900 dark:text-gray-100">{fmt(fee_analysis.fee_comparison.current)}</div>
              <div className="text-xs text-gray-500 dark:text-gray-500">projected value</div>
            </div>
            <div className="rounded-lg bg-teal-50 dark:bg-teal-950 p-3">
              <div className="text-teal-700 dark:text-teal-300">Low-cost (0.15%)</div>
              <div className="text-xl font-bold text-teal-800 dark:text-teal-200">{fmt(fee_analysis.fee_comparison.low_cost_0_15pct)}</div>
              <div className="text-xs text-teal-600 dark:text-teal-400">+{fmt(fee_analysis.fee_comparison.cost_vs_low_cost)} vs current</div>
            </div>
            <div className="rounded-lg bg-red-50 dark:bg-red-950 p-3">
              <div className="text-red-700 dark:text-red-300">High-cost (1.5%)</div>
              <div className="text-xl font-bold text-red-800 dark:text-red-200">{fmt(fee_analysis.fee_comparison.high_cost_1_5pct)}</div>
              <div className="text-xs text-red-600 dark:text-red-400">-{fmt(fee_analysis.fee_comparison.saving_vs_high_cost)} vs current</div>
            </div>
          </div>
          <p className="mt-3 text-xs text-gray-500 dark:text-gray-500">
            Fee drag over {fee_analysis.projection_years} years: {fmt(fee_analysis.fee_drag_over_term)} lost to fees.
          </p>
        </div>
      )}
    </div>
  );
}
