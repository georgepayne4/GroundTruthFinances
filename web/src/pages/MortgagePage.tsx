import { useReport } from "../lib/report-context";
import PageHeader from "../components/PageHeader";
import MetricCard from "../components/MetricCard";
import EmptyState from "../components/EmptyState";

function fmt(n: number | undefined | null): string {
  if (n == null) return "-";
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

export default function MortgagePage() {
  const { report } = useReport();

  if (!report) return <EmptyState />;

  const { mortgage } = report;

  if (!mortgage.applicable) {
    return (
      <div>
        <PageHeader title="Mortgage" description="Mortgage analysis is not applicable to your profile." />
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm text-sm text-gray-600 dark:text-gray-400">
          Add a property goal or mortgage details to your profile to see mortgage analysis.
        </div>
      </div>
    );
  }

  const { borrowing, deposit, repayment, affordability, ltv_analysis, overpayment_analysis, readiness } = mortgage;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Mortgage"
        description={`${mortgage.first_time_buyer ? "First-time buyer" : "Homeowner"} analysis for ${fmt(mortgage.target_property_value)} property.`}
      />

      {/* Readiness */}
      {readiness && (
        <div className={`rounded-xl border p-5 ${readiness.ready ? "border-teal-200 dark:border-teal-800 bg-teal-50 dark:bg-teal-950" : "border-amber-200 dark:border-amber-800 bg-amber-50 dark:bg-amber-950"}`}>
          <h3 className={`text-sm font-semibold uppercase tracking-wide mb-2 ${readiness.ready ? "text-teal-700 dark:text-teal-300" : "text-amber-700 dark:text-amber-300"}`}>
            {readiness.ready ? "Ready to Buy" : "Not Yet Ready"}
          </h3>
          {readiness.blockers.length > 0 && (
            <ul className="text-sm text-amber-800 dark:text-amber-200 space-y-1 mb-2">
              {readiness.blockers.map((b, i) => <li key={i}>- {b}</li>)}
            </ul>
          )}
          {readiness.strengths.length > 0 && (
            <ul className="text-sm text-teal-800 dark:text-teal-200 space-y-1">
              {readiness.strengths.map((s, i) => <li key={i}>+ {s}</li>)}
            </ul>
          )}
        </div>
      )}

      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {borrowing && (
          <>
            <MetricCard label="Max Borrowing" value={fmt(borrowing.max_borrowing_adjusted)} sublabel={`${borrowing.income_multiple}x income`} />
            <MetricCard label="Required Mortgage" value={fmt(borrowing.required_mortgage)} sublabel={borrowing.can_borrow_enough ? "Achievable" : "Exceeds limit"} />
          </>
        )}
        {deposit && (
          <>
            <MetricCard label="Deposit Saved" value={fmt(deposit.available_for_deposit)} sublabel={deposit.adequate ? "Sufficient" : `${fmt(deposit.gap)} gap`} />
            <MetricCard label="Time to Save" value={deposit.months_to_save_gap > 0 ? `${Math.ceil(deposit.months_to_save_gap / 12)} years` : "Ready"} sublabel={deposit.months_to_save_gap > 0 ? `${deposit.months_to_save_gap} months` : undefined} />
          </>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Repayment details */}
        {repayment && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
              Repayment
            </h3>
            <div className="space-y-2 text-sm">
              {[
                { label: "Mortgage amount", value: fmt(repayment.mortgage_amount) },
                { label: "Term", value: `${repayment.term_years} years` },
                { label: "Estimated rate", value: `${repayment.estimated_rate_pct}%` },
                { label: "Monthly repayment", value: fmt(repayment.monthly_repayment) },
                { label: "Total interest", value: fmt(repayment.total_interest) },
                { label: "Replaces rent of", value: fmt(repayment.replaces_rent) },
                { label: "Net monthly change", value: fmt(repayment.net_monthly_change) },
                { label: "Post-mortgage surplus", value: fmt(repayment.post_mortgage_surplus) },
              ].map((row) => (
                <div key={row.label} className="flex justify-between">
                  <span className="text-gray-600 dark:text-gray-400">{row.label}</span>
                  <span className="font-medium text-gray-900 dark:text-gray-100">{row.value}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Affordability */}
        {affordability && (
          <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
            <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
              Affordability
            </h3>
            <div className="space-y-3 text-sm">
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-gray-600 dark:text-gray-400">Repayment-to-income</span>
                  <span className={`font-medium ${affordability.affordable ? "text-teal-700 dark:text-teal-400" : "text-red-700 dark:text-red-400"}`}>
                    {affordability.repayment_to_income_pct.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${affordability.affordable ? "bg-teal-500" : "bg-red-500"}`}
                    style={{ width: `${Math.min(affordability.repayment_to_income_pct * 2.5, 100)}%` }}
                  />
                </div>
              </div>
              <div>
                <div className="flex justify-between mb-1">
                  <span className="text-gray-600 dark:text-gray-400">Stress test (+3%)</span>
                  <span className={`font-medium ${affordability.stress_test_passes ? "text-teal-700 dark:text-teal-400" : "text-red-700 dark:text-red-400"}`}>
                    {affordability.stress_test_to_income_pct.toFixed(1)}%
                  </span>
                </div>
                <div className="h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
                  <div
                    className={`h-full rounded-full ${affordability.stress_test_passes ? "bg-teal-500" : "bg-amber-500"}`}
                    style={{ width: `${Math.min(affordability.stress_test_to_income_pct * 2.5, 100)}%` }}
                  />
                </div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* LTV bands */}
      {ltv_analysis && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
          <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
            LTV Comparison
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 text-gray-600 dark:text-gray-400 font-medium">LTV</th>
                  <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Deposit</th>
                  <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Rate</th>
                  <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Payment/mo</th>
                  <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Total Interest</th>
                  <th className="text-center py-2 text-gray-600 dark:text-gray-400 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {ltv_analysis.bands.map((band) => (
                  <tr key={band.ltv_pct} className={`border-b border-gray-100 dark:border-gray-800 ${band.ltv_pct === ltv_analysis.current_ltv_pct ? "bg-blue-50 dark:bg-blue-950" : ""}`}>
                    <td className="py-2 text-gray-900 dark:text-gray-100 font-medium">{band.ltv_pct}%</td>
                    <td className="py-2 text-right text-gray-600 dark:text-gray-400">{fmt(band.deposit_required)}</td>
                    <td className="py-2 text-right text-gray-600 dark:text-gray-400">{band.rate_pct}%</td>
                    <td className="py-2 text-right text-gray-900 dark:text-gray-100">{fmt(band.monthly_payment)}</td>
                    <td className="py-2 text-right text-gray-600 dark:text-gray-400">{fmt(band.total_interest)}</td>
                    <td className="py-2 text-center">
                      <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${band.achievable ? "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200" : "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400"}`}>
                        {band.achievable ? "Achievable" : "Not yet"}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Overpayment analysis */}
      {overpayment_analysis && overpayment_analysis.length > 0 && (
        <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
          <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
            Overpayment Scenarios
          </h3>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {overpayment_analysis.map((s) => (
              <div key={s.extra_monthly} className="rounded-lg bg-gray-50 dark:bg-gray-800 p-4">
                <div className="text-lg font-bold text-gray-900 dark:text-gray-100">+{fmt(s.extra_monthly)}/mo</div>
                <div className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                  Save {fmt(s.total_interest_saved)} interest
                </div>
                <div className="text-sm text-gray-600 dark:text-gray-400">
                  Pay off {s.years_saved.toFixed(1)} years sooner
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-500 mt-1">
                  New term: {s.new_payoff_years.toFixed(1)} years
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
