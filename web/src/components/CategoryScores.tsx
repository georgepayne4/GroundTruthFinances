import type { Scoring } from "../lib/api";

interface CategoryScoresProps {
  scoring: Scoring;
}

function barColor(score: number): string {
  if (score >= 80) return "bg-teal-500";
  if (score >= 60) return "bg-blue-500";
  if (score >= 40) return "bg-amber-500";
  if (score >= 20) return "bg-purple-500";
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
      <div className="space-y-3" role="list" aria-label="Category scores">
        {categories.map(([name, data]) => {
          const displayName = name.replace(/_/g, " ");
          const rounded = Math.round(data.score);
          return (
            <div key={name} role="listitem" aria-label={`${displayName}: ${rounded} out of 100`}>
              <div className="flex justify-between text-sm mb-1">
                <span className="text-gray-700 capitalize">{displayName}</span>
                <span className="font-semibold text-gray-900">{rounded}</span>
              </div>
              <div
                className="h-2 rounded-full bg-gray-100 overflow-hidden"
                role="progressbar"
                aria-valuenow={rounded}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label={`${displayName} score`}
              >
                <div
                  className={`h-full rounded-full transition-all duration-700 ${barColor(data.score)}`}
                  style={{ width: `${data.score}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
      {/* Screen-reader data table alternative */}
      <table className="sr-only">
        <caption>Score breakdown by category</caption>
        <thead>
          <tr><th scope="col">Category</th><th scope="col">Score</th></tr>
        </thead>
        <tbody>
          {categories.map(([name, data]) => (
            <tr key={name}>
              <td>{name.replace(/_/g, " ")}</td>
              <td>{Math.round(data.score)} / 100</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
