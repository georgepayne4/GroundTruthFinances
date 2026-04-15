interface CurrencyInputProps {
  id: string;
  value: number | null;
  onChange: (val: number) => void;
  min?: number;
  max?: number;
  placeholder?: string;
  required?: boolean;
  error?: string;
  "aria-describedby"?: string;
}

export default function CurrencyInput({
  id,
  value,
  onChange,
  min,
  max,
  placeholder = "0",
  required,
  error,
  "aria-describedby": ariaDescribedby,
}: CurrencyInputProps) {
  const borderClass = error
    ? "border-red-500 dark:border-red-500 focus:ring-red-500"
    : "border-gray-300 dark:border-gray-700 focus:ring-gray-900 dark:focus:ring-gray-100";
  return (
    <div className="relative">
      <span className="absolute left-3 top-1/2 -translate-y-1/2 text-sm text-gray-500 dark:text-gray-400 pointer-events-none">
        £
      </span>
      <input
        id={id}
        type="number"
        inputMode="decimal"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? 0 : Number(e.target.value))}
        min={min}
        max={max}
        placeholder={placeholder}
        required={required}
        aria-required={required}
        aria-invalid={!!error}
        aria-describedby={ariaDescribedby ?? (error ? `${id}-error` : undefined)}
        className={`w-full pl-7 pr-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:border-transparent ${borderClass}`}
      />
    </div>
  );
}
