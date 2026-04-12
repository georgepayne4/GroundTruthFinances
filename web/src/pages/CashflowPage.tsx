import { useReport } from "../lib/report-context";
import PageHeader from "../components/PageHeader";
import CashflowBar from "../components/CashflowBar";
import MetricCard from "../components/MetricCard";
import EmptyState from "../components/EmptyState";

function fmt(n: number | undefined | null): string {
  if (n == null) return "-";
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

function pct(n: number): string {
  return `${n.toFixed(1)}%`;
}

export default function CashflowPage() {
  const { report } = useReport();

  if (!report) return <EmptyState />;

  const { cashflow } = report;
  const { income, deductions, net_income, expenses, surplus, savings_rate, spending_benchmarks } = cashflow;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Cashflow"
        description="Detailed income, expenses, and surplus breakdown."
      />

      {/* Key metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard label="Gross Income" value={fmt(income.total_gross_monthly)} sublabel={`${fmt(income.total_gross_annual)}/yr`} />
        <MetricCard label="Net Income" value={fmt(net_income.monthly)} sublabel={`${fmt(net_income.annual)}/yr`} />
        <MetricCard label="Monthly Surplus" value={fmt(surplus.monthly)} sublabel={`${fmt(surplus.annual)}/yr`} />
        <MetricCard label="Savings Rate" value={pct(savings_rate.basic_pct)} sublabel={`${pct(savings_rate.effective_pct_incl_pension)} incl. pension`} />
      </div>

      {/* Chart */}
      <CashflowBar cashflow={cashflow} />

      {/* Income waterfall */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
          Income Waterfall
        </h3>
        <div className="space-y-2">
          {[
            { label: "Primary income", value: income.primary_gross_annual },
            ...(income.partner_gross_annual > 0 ? [{ label: "Partner income", value: income.partner_gross_annual }] : []),
            ...(income.other_income_annual > 0 ? [{ label: "Other income", value: income.other_income_annual }] : []),
          ].map((row) => (
            <div key={row.label} className="flex justify-between text-sm">
              <span className="text-gray-600 dark:text-gray-400">{row.label}</span>
              <span className="font-medium text-gray-900 dark:text-gray-100">{fmt(row.value)}</span>
            </div>
          ))}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-2 flex justify-between text-sm font-semibold">
            <span className="text-gray-700 dark:text-gray-300">Gross total</span>
            <span className="text-gray-900 dark:text-gray-100">{fmt(income.total_gross_annual)}</span>
          </div>
          {[
            { label: "Income tax", value: -deductions.income_tax_annual },
            { label: "National Insurance", value: -deductions.national_insurance_annual },
            ...(deductions.other_income_tax_annual > 0 ? [{ label: "Other income tax", value: -deductions.other_income_tax_annual }] : []),
            { label: "Pension (personal)", value: -deductions.pension_personal_annual },
          ].map((row) => (
            <div key={row.label} className="flex justify-between text-sm">
              <span className="text-gray-600 dark:text-gray-400">{row.label}</span>
              <span className="font-medium text-red-700 dark:text-red-400">{fmt(row.value)}</span>
            </div>
          ))}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-2 flex justify-between text-sm font-semibold">
            <span className="text-gray-700 dark:text-gray-300">Net income</span>
            <span className="text-gray-900 dark:text-gray-100">{fmt(net_income.annual)}</span>
          </div>
        </div>
      </div>

      {/* Expense breakdown with benchmarks */}
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
        <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
          Expense Breakdown
        </h3>
        <div className="space-y-3">
          {Object.entries(expenses.category_breakdown_monthly)
            .sort(([, a], [, b]) => b - a)
            .map(([category, amount]) => {
              const benchmark = spending_benchmarks?.comparisons.find((c) => c.category === category);
              const pctOfNet = net_income.monthly > 0 ? (amount / net_income.monthly) * 100 : 0;
              return (
                <div key={category}>
                  <div className="flex justify-between text-sm mb-1">
                    <span className="text-gray-700 dark:text-gray-300 capitalize">{category}</span>
                    <span className="font-medium text-gray-900 dark:text-gray-100">
                      {fmt(amount)}/mo
                      <span className="text-gray-500 dark:text-gray-500 ml-1">({pct(pctOfNet)} of net)</span>
                    </span>
                  </div>
                  <div className="h-2 rounded-full bg-gray-100 dark:bg-gray-800 overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all ${benchmark?.above_benchmark ? "bg-amber-500" : "bg-teal-500"}`}
                      style={{ width: `${Math.min(pctOfNet * 2, 100)}%` }}
                    />
                  </div>
                  {benchmark && (
                    <div className="text-xs mt-0.5 text-gray-500 dark:text-gray-500">
                      Benchmark: {pct(benchmark.benchmark_pct_of_net)} of net ({fmt(benchmark.benchmark_monthly)}/mo)
                      {benchmark.above_benchmark
                        ? ` — £${Math.abs(benchmark.delta_monthly).toFixed(0)} over`
                        : ` — £${Math.abs(benchmark.delta_monthly).toFixed(0)} under`}
                    </div>
                  )}
                </div>
              );
            })}
          <div className="border-t border-gray-200 dark:border-gray-700 pt-2 flex justify-between text-sm font-semibold">
            <span className="text-gray-700 dark:text-gray-300">Total expenses</span>
            <span className="text-gray-900 dark:text-gray-100">{fmt(expenses.total_monthly)}/mo</span>
          </div>
        </div>
      </div>
    </div>
  );
}
