import { useReport } from "../lib/report-context";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";

function fmt(n: number | undefined | null): string {
  if (n == null) return "-";
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

export default function LifeEventsPage() {
  const { report } = useReport();

  if (!report) return <EmptyState />;

  const { life_events } = report;
  const { timeline, milestones } = life_events;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Life Events"
        description={`${life_events.projection_years}-year financial projection with major life events.`}
      />

      {/* Milestones */}
      {milestones && milestones.length > 0 && (
        <div className="rounded-xl border border-blue-200 dark:border-blue-800 bg-blue-50 dark:bg-blue-950 p-5">
          <h3 className="text-sm font-semibold text-blue-700 dark:text-blue-300 uppercase tracking-wide mb-3">
            Key Milestones
          </h3>
          <div className="space-y-2">
            {milestones.map((m, i) => (
              <div key={i} className="flex items-center gap-3 text-sm">
                <span className="flex-shrink-0 w-10 text-blue-600 dark:text-blue-400 font-semibold">Age {m.age}</span>
                <span className="text-blue-800 dark:text-blue-200">{m.message}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Timeline table */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
          Year-by-Year Projection
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="text-left py-2 text-gray-600 dark:text-gray-400 font-medium">Age</th>
                <th className="text-left py-2 text-gray-600 dark:text-gray-400 font-medium">Events</th>
                <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Income</th>
                <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Expenses</th>
                <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Surplus</th>
                <th className="text-right py-2 text-gray-600 dark:text-gray-400 font-medium">Net Worth</th>
              </tr>
            </thead>
            <tbody>
              {timeline.map((y) => (
                <tr key={y.year} className={`border-b border-gray-100 dark:border-gray-800 ${y.events ? "bg-blue-50/50 dark:bg-blue-950/30" : ""}`}>
                  <td className="py-2 text-gray-900 dark:text-gray-100 font-medium">{y.age}</td>
                  <td className="py-2 text-gray-600 dark:text-gray-400 max-w-xs">
                    {y.events ? (
                      <div className="space-y-0.5">
                        {y.events.map((e, i) => (
                          <div key={i} className="text-blue-700 dark:text-blue-400 text-xs font-medium">{e}</div>
                        ))}
                      </div>
                    ) : (
                      <span className="text-gray-400 dark:text-gray-600">-</span>
                    )}
                  </td>
                  <td className="py-2 text-right text-gray-900 dark:text-gray-100">{fmt(y.net_income_annual)}</td>
                  <td className="py-2 text-right text-gray-600 dark:text-gray-400">{fmt(y.expenses_annual)}</td>
                  <td className={`py-2 text-right font-medium ${y.annual_surplus >= 0 ? "text-teal-700 dark:text-teal-400" : "text-red-700 dark:text-red-400"}`}>
                    {fmt(y.annual_surplus)}
                  </td>
                  <td className={`py-2 text-right font-medium ${y.net_worth >= 0 ? "text-gray-900 dark:text-gray-100" : "text-red-700 dark:text-red-400"}`}>
                    {fmt(y.net_worth)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detailed breakdown for years with events */}
      {timeline.filter((y) => y.events).map((y) => (
        <div key={y.year} className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
          <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
            Age {y.age}: {y.events!.join(", ")}
          </h3>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
            <div>
              <div className="text-gray-500 dark:text-gray-500">Gross Income</div>
              <div className="font-semibold text-gray-900 dark:text-gray-100">{fmt(y.gross_income_annual)}</div>
            </div>
            <div>
              <div className="text-gray-500 dark:text-gray-500">Savings Rate</div>
              <div className="font-semibold text-gray-900 dark:text-gray-100">{y.savings_rate_pct.toFixed(1)}%</div>
            </div>
            <div>
              <div className="text-gray-500 dark:text-gray-500">Liquid Savings</div>
              <div className="font-semibold text-gray-900 dark:text-gray-100">{fmt(y.liquid_savings)}</div>
            </div>
            <div>
              <div className="text-gray-500 dark:text-gray-500">Total Debt</div>
              <div className="font-semibold text-gray-900 dark:text-gray-100">{fmt(y.total_debt)}</div>
            </div>
            {y.property_value != null && (
              <>
                <div>
                  <div className="text-gray-500 dark:text-gray-500">Property Value</div>
                  <div className="font-semibold text-gray-900 dark:text-gray-100">{fmt(y.property_value)}</div>
                </div>
                <div>
                  <div className="text-gray-500 dark:text-gray-500">Equity</div>
                  <div className="font-semibold text-teal-700 dark:text-teal-400">{fmt(y.equity)}</div>
                </div>
              </>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
