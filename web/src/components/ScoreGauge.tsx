interface ScoreGaugeProps {
  score: number;
  grade: string;
}

function gradeColor(grade: string): string {
  if (grade.startsWith("A")) return "text-teal-600";
  if (grade.startsWith("B")) return "text-blue-600";
  if (grade.startsWith("C")) return "text-amber-600";
  if (grade.startsWith("D")) return "text-purple-600";
  return "text-red-600";
}

function ringColor(score: number): string {
  if (score >= 80) return "stroke-teal-500";
  if (score >= 60) return "stroke-blue-500";
  if (score >= 40) return "stroke-amber-500";
  if (score >= 20) return "stroke-purple-500";
  return "stroke-red-500";
}

export default function ScoreGauge({ score, grade }: ScoreGaugeProps) {
  const radius = 70;
  const circumference = 2 * Math.PI * radius;
  const progress = (score / 100) * circumference;
  const roundedScore = Math.round(score);

  return (
    <div className="flex flex-col items-center" role="img" aria-label={`Financial health score: ${roundedScore} out of 100, grade ${grade}`}>
      <svg width="180" height="180" className="-rotate-90" aria-hidden="true" focusable="false">
        <circle
          cx="90" cy="90" r={radius}
          fill="none" strokeWidth="12"
          className="stroke-gray-200"
        />
        <circle
          cx="90" cy="90" r={radius}
          fill="none" strokeWidth="12"
          strokeDasharray={circumference}
          strokeDashoffset={circumference - progress}
          strokeLinecap="round"
          className={`${ringColor(score)} transition-all duration-1000`}
        />
      </svg>
      <div className="absolute mt-12 text-center" aria-hidden="true">
        <div className="text-4xl font-bold text-gray-900">{roundedScore}</div>
        <div className={`text-2xl font-semibold ${gradeColor(grade)}`}>{grade}</div>
      </div>
    </div>
  );
}
