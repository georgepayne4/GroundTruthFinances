import type { Scoring } from "../lib/api";

interface CategoryScoresProps {
  scoring: Scoring;
}

function barColor(score: number): string {
  if (score >= 80) return "bg-emerald-500";
  if (score >= 60) return "bg-blue-500";
  if (score >= 40) return "bg-amber-500";
  if (score >= 20) return "bg-orange-500";
  return "bg-red-500";
}

export default function CategoryScores({ scoring }: CategoryScoresProps) {
  const categories = Object.entries(scoring.categories).sort(
    ([, a], [, b]) => b.score - a.score
  );

  return (
    <div className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
      <h3 className="mb-4 text-sm font-semibold text-gray-700 uppercase tracking-wide">
        Score Breakdown
      </h3>
      <div className="space-y-3">
        {categories.map(([name, data]) => (
          <div key={name}>
            <div className="flex justify-between text-sm mb-1">
              <span className="text-gray-600 capitalize">{name.replace(/_/g, " ")}</span>
              <span className="font-semibold text-gray-900">{Math.round(data.score)}</span>
            </div>
            <div className="h-2 rounded-full bg-gray-100 overflow-hidden">
              <div
                className={`h-full rounded-full transition-all duration-700 ${barColor(data.score)}`}
                style={{ width: `${data.score}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
