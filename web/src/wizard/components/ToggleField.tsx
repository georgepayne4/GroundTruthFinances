interface ToggleFieldProps {
  id: string;
  label: string;
  checked: boolean;
  onChange: (val: boolean) => void;
}

export default function ToggleField({ id, label, checked, onChange }: ToggleFieldProps) {
  return (
    <label htmlFor={id} className="flex items-center gap-3 cursor-pointer">
      <div className="relative">
        <input
          id={id}
          type="checkbox"
          checked={checked}
          onChange={(e) => onChange(e.target.checked)}
          className="sr-only peer"
        />
        <div className="w-9 h-5 bg-gray-300 dark:bg-gray-700 rounded-full peer-checked:bg-teal-500 dark:peer-checked:bg-teal-600 transition-colors" />
        <div className="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full shadow peer-checked:translate-x-4 transition-transform" />
      </div>
      <span className="text-sm text-gray-700 dark:text-gray-300">{label}</span>
    </label>
  );
}
