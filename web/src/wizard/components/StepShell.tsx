import type { ReactNode } from "react";

interface StepShellProps {
  title: string;
  description: string;
  children: ReactNode;
  onNext: () => void;
  onBack?: () => void;
  onSkip?: () => void;
  canProceed?: boolean;
  nextLabel?: string;
}

export default function StepShell({
  title,
  description,
  children,
  onNext,
  onBack,
  onSkip,
  canProceed = true,
  nextLabel = "Next",
}: StepShellProps) {
  return (
    <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
      <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100 mb-1">{title}</h2>
      <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">{description}</p>

      <div className="space-y-5">{children}</div>

      <div className="flex items-center justify-between mt-8 pt-5 border-t border-gray-100 dark:border-gray-800">
        <div>
          {onBack && (
            <button
              type="button"
              onClick={onBack}
              className="rounded-lg px-5 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              Back
            </button>
          )}
        </div>
        <div className="flex gap-3">
          {onSkip && (
            <button
              type="button"
              onClick={onSkip}
              className="rounded-lg px-5 py-2 text-sm font-medium text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              Skip
            </button>
          )}
          <button
            type="button"
            onClick={onNext}
            disabled={!canProceed}
            className="rounded-lg bg-gray-900 dark:bg-gray-100 px-6 py-2 text-sm font-medium text-white dark:text-gray-900 hover:bg-gray-700 dark:hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:ring-offset-2 disabled:opacity-50 transition-colors"
          >
            {nextLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
