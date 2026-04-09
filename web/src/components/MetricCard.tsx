interface MetricCardProps {
  label: string;
  value: string | number;
  sublabel?: string;
  trend?: "up" | "down" | "neutral";
}

export default function MetricCard({ label, value, sublabel, trend }: MetricCardProps) {
  const trendIcon = trend === "up" ? "^" : trend === "down" ? "v" : "";
  const trendColor = trend === "up" ? "text-emerald-500" : trend === "down" ? "text-red-500" : "text-gray-400";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <div className="text-sm font-medium text-gray-500">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-2xl font-bold text-gray-900">{value}</span>
        {trendIcon && <span className={`text-sm font-semibold ${trendColor}`}>{trendIcon}</span>}
      </div>
      {sublabel && <div className="mt-1 text-xs text-gray-400">{sublabel}</div>}
    </div>
  );
}
