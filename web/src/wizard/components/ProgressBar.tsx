import { STEP_LABELS, REQUIRED_STEPS } from "../lib/wizard-types";
import { Check } from "lucide-react";

interface ProgressBarProps {
  currentStep: number;
  completeness: number;
  onStepClick: (step: number) => void;
  visitedSteps: Set<number>;
}

export default function ProgressBar({ currentStep, completeness, onStepClick, visitedSteps }: ProgressBarProps) {
  return (
    <div className="mb-6">
      <div className="flex items-center justify-between mb-3">
        <h1 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">
          Profile Setup
        </h1>
        <span className={`text-sm font-semibold ${completeness >= 70 ? "text-teal-600 dark:text-teal-400" : completeness >= 40 ? "text-amber-600 dark:text-amber-400" : "text-gray-500 dark:text-gray-400"}`}>
          {completeness}%
        </span>
      </div>

      {/* Step dots */}
      <nav aria-label="Wizard progress" className="flex items-center gap-1">
        {STEP_LABELS.map((label, i) => {
          const isCompleted = visitedSteps.has(i) && i < currentStep;
          const isCurrent = i === currentStep;
          const isOptional = i >= REQUIRED_STEPS && i < STEP_LABELS.length - 1;
          const isClickable = visitedSteps.has(i) || i <= currentStep;

          return (
            <div key={label} className="flex items-center flex-1">
              <button
                type="button"
                onClick={() => isClickable && onStepClick(i)}
                disabled={!isClickable}
                aria-current={isCurrent ? "step" : undefined}
                aria-label={`${label}${isCompleted ? " (completed)" : isCurrent ? " (current)" : ""}`}
                className={`relative flex items-center justify-center w-7 h-7 rounded-full text-xs font-medium transition-colors flex-shrink-0 ${
                  isCurrent
                    ? "bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900"
                    : isCompleted
                      ? "bg-teal-100 dark:bg-teal-900 text-teal-700 dark:text-teal-300"
                      : "bg-gray-100 dark:bg-gray-800 text-gray-400 dark:text-gray-600"
                } ${isClickable ? "cursor-pointer hover:ring-2 hover:ring-gray-300 dark:hover:ring-gray-600" : "cursor-default"} ${isOptional && !isCompleted && !isCurrent ? "border border-dashed border-gray-300 dark:border-gray-600 bg-transparent" : ""}`}
              >
                {isCompleted ? <Check size={14} /> : i + 1}
              </button>
              {i < STEP_LABELS.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-1 ${
                    isCompleted ? "bg-teal-300 dark:bg-teal-700" : "bg-gray-200 dark:bg-gray-700"
                  }`}
                />
              )}
            </div>
          );
        })}
      </nav>

      {/* Current step label */}
      <p className="mt-2 text-xs text-gray-500 dark:text-gray-500 text-center">
        Step {currentStep + 1}: {STEP_LABELS[currentStep]}
      </p>
    </div>
  );
}
