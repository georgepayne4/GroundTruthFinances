import type { AdvisorInsights } from "../lib/api";

interface PriorityActionsProps {
  insights: AdvisorInsights;
}

function categoryBadge(category: string): string {
  const colors: Record<string, string> = {
    savings: "bg-teal-100 text-teal-800",
    debt: "bg-red-100 text-red-800",
    investment: "bg-blue-100 text-blue-800",
    pension: "bg-indigo-100 text-indigo-800",
    mortgage: "bg-amber-100 text-amber-800",
    insurance: "bg-purple-100 text-purple-800",
    tax: "bg-cyan-100 text-cyan-800",
  };
  return colors[category.toLowerCase()] || "bg-gray-100 text-gray-700";
}

export default function PriorityActions({ insights }: PriorityActionsProps) {
  const priorities = insights.top_priorities || [];

  if (priorities.length === 0) return null;

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold text-gray-700 uppercase tracking-wide">
        Priority Actions
      </h3>
      <ol className="space-y-3" aria-label="Priority actions list">
        {priorities.slice(0, 5).map((p) => (
          <li key={p.priority} className="flex gap-3 items-start">
            <span className="flex-shrink-0 w-6 h-6 rounded-full bg-gray-900 text-white text-xs font-bold flex items-center justify-center" aria-hidden="true">
              {p.priority}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-medium text-gray-900 text-sm">{p.title}</span>
                <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${categoryBadge(p.category)}`}>
                  {p.category}
                </span>
              </div>
              <p className="text-xs text-gray-600 mt-0.5">{p.detail}</p>
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
