interface PercentInputProps {
  id: string;
  value: number;
  onChange: (decimal: number) => void;
  min?: number;
  max?: number;
  step?: number;
  error?: string;
  "aria-describedby"?: string;
}

/** Displays percentage to user (e.g. 5), stores as decimal (0.05). */
export default function PercentInput({
  id,
  value,
  onChange,
  min = 0,
  max = 100,
  step = 0.5,
  error,
  "aria-describedby": ariaDescribedby,
}: PercentInputProps) {
  const displayValue = value > 0 ? +(value * 100).toFixed(2) : "";
  const borderClass = error
    ? "border-red-500 dark:border-red-500 focus:ring-red-500"
    : "border-gray-300 dark:border-gray-700 focus:ring-gray-900 dark:focus:ring-gray-100";

  return (
    <div className="relative">
      <input
        id={id}
        type="number"
        inputMode="decimal"
        value={displayValue}
        onChange={(e) => {
          const pct = e.target.value === "" ? 0 : Number(e.target.value);
          onChange(pct / 100);
        }}
        min={min}
        max={max}
        step={step}
        aria-invalid={!!error}
        aria-describedby={ariaDescribedby ?? (error ? `${id}-error` : undefined)}
        className={`w-full pr-8 pl-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:border-transparent ${borderClass}`}
      />
      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-sm text-gray-500 dark:text-gray-400 pointer-events-none">
        %
      </span>
    </div>
  );
}
