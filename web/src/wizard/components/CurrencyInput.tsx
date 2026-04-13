interface CurrencyInputProps {
  id: string;
  value: number | null;
  onChange: (val: number) => void;
  min?: number;
  max?: number;
  placeholder?: string;
  required?: boolean;
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
  "aria-describedby": ariaDescribedby,
}: CurrencyInputProps) {
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
        aria-describedby={ariaDescribedby}
        className="w-full pl-7 pr-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
      />
    </div>
  );
}
