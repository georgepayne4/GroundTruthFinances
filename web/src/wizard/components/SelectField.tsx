interface SelectFieldProps {
  id: string;
  value: string;
  onChange: (val: string) => void;
  options: { value: string; label: string }[];
  "aria-describedby"?: string;
}

export default function SelectField({ id, value, onChange, options, "aria-describedby": ariaDescribedby }: SelectFieldProps) {
  return (
    <select
      id={id}
      value={value}
      onChange={(e) => onChange(e.target.value)}
      aria-describedby={ariaDescribedby}
      className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
    >
      {options.map((opt) => (
        <option key={opt.value} value={opt.value}>
          {opt.label}
        </option>
      ))}
    </select>
  );
}
