interface MetricCardProps {
  label: string;
  value: string | number;
  sublabel?: string;
  trend?: "up" | "down" | "neutral";
}

export default function MetricCard({ label, value, sublabel, trend }: MetricCardProps) {
  const trendIcon = trend === "up" ? "\u2191" : trend === "down" ? "\u2193" : "";
  const trendColor = trend === "up" ? "text-teal-700 dark:text-teal-400" : trend === "down" ? "text-red-700 dark:text-red-400" : "text-gray-600 dark:text-gray-400";
  const trendLabel = trend === "up" ? "trending up" : trend === "down" ? "trending down" : "";

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm" role="group" aria-label={label}>
      <div className="text-sm font-medium text-gray-600 dark:text-gray-400">{label}</div>
      <div className="mt-1 flex items-baseline gap-2">
        <span className="text-2xl font-bold text-gray-900 dark:text-gray-100">{value}</span>
        {trendIcon && (
          <span className={`text-sm font-semibold ${trendColor}`} aria-label={trendLabel}>
            {trendIcon}
          </span>
        )}
      </div>
      {sublabel && <div className="mt-1 text-xs text-gray-600 dark:text-gray-400">{sublabel}</div>}
    </div>
  );
}
