import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import type { Cashflow } from "../lib/api";

interface CashflowBarProps {
  cashflow: Cashflow;
}

export default function CashflowBar({ cashflow }: CashflowBarProps) {
  const data = [
    { name: "Gross", value: cashflow.income.total_gross_monthly, color: "#6366f1" },
    { name: "Tax & NI", value: cashflow.income.total_gross_monthly - cashflow.net_income.monthly, color: "#ef4444" },
    { name: "Expenses", value: cashflow.expenses.total_monthly, color: "#f59e0b" },
    { name: "Debt", value: cashflow.debt_servicing.total_monthly, color: "#f97316" },
    { name: "Surplus", value: cashflow.surplus.monthly, color: "#10b981" },
  ];

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold text-gray-700 uppercase tracking-wide">
        Monthly Cashflow
      </h3>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} layout="vertical" margin={{ left: 60, right: 20 }}>
          <XAxis type="number" tickFormatter={(v: number) => `${(v / 1000).toFixed(1)}k`} />
          <YAxis type="category" dataKey="name" width={60} tick={{ fontSize: 12 }} />
          <Tooltip formatter={(v) => `£${Number(v).toLocaleString("en-GB", { minimumFractionDigits: 0 })}`} />
          <Bar dataKey="value" radius={[0, 4, 4, 0]}>
            {data.map((entry, i) => (
              <Cell key={i} fill={entry.color} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
