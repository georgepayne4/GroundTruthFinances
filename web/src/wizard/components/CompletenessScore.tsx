import { completenessColor, completenessLabel } from "../lib/wizard-completeness";

interface CompletenessScoreProps {
  score: number;
  showLabel?: boolean;
}

export default function CompletenessScore({ score, showLabel = true }: CompletenessScoreProps) {
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative w-20 h-20">
        <svg className="w-20 h-20 -rotate-90" viewBox="0 0 64 64">
          <circle cx="32" cy="32" r={radius} fill="none" stroke="currentColor" strokeWidth="4" className="text-gray-200 dark:text-gray-700" />
          <circle
            cx="32"
            cy="32"
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="4"
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            className={completenessColor(score)}
          />
        </svg>
        <div className="absolute inset-0 flex items-center justify-center">
          <span className={`text-lg font-bold ${completenessColor(score)}`}>{score}</span>
        </div>
      </div>
      {showLabel && (
        <p className="text-xs text-gray-500 dark:text-gray-500 text-center max-w-48">{completenessLabel(score)}</p>
      )}
    </div>
  );
}
