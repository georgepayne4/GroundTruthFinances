import type { AdvisorInsights } from "../lib/api";

interface PriorityActionsProps {
  insights: AdvisorInsights;
}

function categoryBadge(category: string): string {
  const colors: Record<string, string> = {
    savings: "bg-teal-100 text-teal-800 dark:bg-teal-900 dark:text-teal-200",
    debt: "bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200",
    investment: "bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200",
    pension: "bg-indigo-100 text-indigo-800 dark:bg-indigo-900 dark:text-indigo-200",
    mortgage: "bg-amber-100 text-amber-800 dark:bg-amber-900 dark:text-amber-200",
    insurance: "bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-200",
    tax: "bg-cyan-100 text-cyan-800 dark:bg-cyan-900 dark:text-cyan-200",
  };
  return colors[category.toLowerCase()] || "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300";
}

export default function PriorityActions({ insights }: PriorityActionsProps) {
  const priorities = insights.top_priorities || [];

  if (priorities.length === 0) return null;

  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
        Priority Actions
      </h3>
      <ol className="space-y-3" aria-label="Priority actions list">
        {priorities.slice(0, 5).map((p) => (
          <li key={p.priority} className="flex gap-3 items-start">
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 text-xs font-bold flex items-center justify-center" aria-hidden="true">
              {p.priority}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-900 dark:text-gray-100 text-sm">{p.title}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${categoryBadge(p.category)}`}>
                  {p.category}
                </span>
              </div>
              <p className="text-xs text-gray-600 dark:text-gray-400 mt-0.5">{p.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
