interface MetricCardProps {
  label: string;
  value: string | number;
  sublabel?: string;
  trend?: "up" | "down" | "neutral";
}

export default function MetricCard({ label, value, sublabel, trend }: MetricCardProps) {
  const trendIcon = trend === "up" ? "\u2191" : trend === "down" ? "\u2193" : "";
  const trendColor = trend === "up" ? "text-teal-700" : trend === "down" ? "text-red-700" : "text-gray-600";
  const trendLabel = trend === "up" ? "trending up" : trend === "down" ? "trending down" : "";

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm" role="group" aria-label={label}>
      <div className="text-sm font-medium text-gray-600">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-2xl font-bold text-gray-900">{value}</span>
        {trendIcon && (
          <span className={`text-sm font-semibold ${trendColor}`} aria-label={trendLabel}>
            {trendIcon}
          </span>
        )}
      </div>
      {sublabel && <div className="mt-1 text-xs text-gray-600">{sublabel}</div>}
    </div>
  );
}
