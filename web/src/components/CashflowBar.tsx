import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";
import type { Cashflow } from "../lib/api";

interface CashflowBarProps {
  cashflow: Cashflow;
}

function fmt(n: number): string {
  return `£${n.toLocaleString("en-GB", { minimumFractionDigits: 0 })}`;
}

export default function CashflowBar({ cashflow }: CashflowBarProps) {
  const data = [
    { name: "Gross", value: cashflow.income.total_gross_monthly, color: "#0077bb" },
    { name: "Tax & NI", value: cashflow.income.total_gross_monthly - cashflow.net_income.monthly, color: "#cc3311" },
    { name: "Expenses", value: cashflow.expenses.total_monthly, color: "#ee7733" },
    { name: "Debt", value: cashflow.debt_servicing.total_monthly, color: "#aa3377" },
    { name: "Surplus", value: cashflow.surplus.monthly, color: "#009988" },
  ];

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 id="cashflow-heading" className="mb-4 text-sm font-semibold text-gray-700 uppercase tracking-wide">
        Monthly Cashflow
      </h3>
      <div role="img" aria-labelledby="cashflow-heading" aria-describedby="cashflow-table">
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data} layout="vertical" margin={{ left: 60, right: 20 }}>
            <XAxis type="number" tickFormatter={(v: number) => `${(v / 1000).toFixed(1)}k`} />
            <YAxis type="category" dataKey="name" width={60} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(v) => fmt(Number(v))} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {data.map((entry, i) => (
                <Cell key={i} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      {/* Screen-reader data table alternative */}
      <table id="cashflow-table" className="sr-only">
        <caption>Monthly cashflow breakdown</caption>
        <thead>
          <tr><th scope="col">Category</th><th scope="col">Amount</th></tr>
        </thead>
        <tbody>
          {data.map((d) => (
            <tr key={d.name}>
              <td>{d.name}</td>
              <td>{fmt(d.value)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
