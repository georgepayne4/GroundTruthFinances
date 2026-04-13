import type { ReactNode } from "react";

interface FieldGroupProps {
  label: string;
  htmlFor: string;
  helpText?: string;
  error?: string;
  required?: boolean;
  children: ReactNode;
}

export default function FieldGroup({ label, htmlFor, helpText, error, required, children }: FieldGroupProps) {
  return (
    <div>
      <label htmlFor={htmlFor} className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {helpText && !error && (
        <p id={`${htmlFor}-help`} className="mt-1 text-xs text-gray-500 dark:text-gray-500">
          {helpText}
        </p>
      )}
      {error && (
        <p id={`${htmlFor}-error`} role="alert" className="mt-1 text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
    </div>
  );
}
