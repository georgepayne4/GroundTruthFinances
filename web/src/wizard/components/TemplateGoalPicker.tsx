import type { WizardState, GoalItem } from "../lib/wizard-types";
import { TEMPLATE_GOALS } from "../lib/wizard-defaults";
import { Shield, Home, Sunset } from "lucide-react";
import type { LucideIcon } from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  emergency_fund: Shield,
  house_deposit: Home,
  retirement: Sunset,
};

function fmt(n: number): string {
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

interface TemplateGoalPickerProps {
  state: WizardState;
  goals: GoalItem[];
  onAdd: (goal: GoalItem) => void;
}

export default function TemplateGoalPicker({ state, goals, onAdd }: TemplateGoalPickerProps) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
      {TEMPLATE_GOALS.map((tpl) => {
        const Icon = ICONS[tpl.key] || Shield;
        const target = tpl.getTarget(state);
        const alreadyAdded = goals.some((g) => g.fromTemplate === tpl.key);

        return (
          <button
            key={tpl.key}
            type="button"
            onClick={() => {
              if (!alreadyAdded) {
                onAdd({
                  id: crypto.randomUUID(),
                  name: tpl.name,
                  target_amount: target,
                  deadline_years: tpl.key === "retirement" ? Math.max(1, (state.personal.retirement_age || 67) - (state.personal.age || 30)) : tpl.deadline_years,
                  priority: tpl.priority,
                  category: tpl.category,
                  fromTemplate: tpl.key,
                });
              }
            }}
            disabled={alreadyAdded}
            className={`text-left rounded-lg border p-4 transition-colors ${
              alreadyAdded
                ? "border-teal-200 dark:border-teal-800 bg-teal-50 dark:bg-teal-950"
                : "border-gray-200 dark:border-gray-700 hover:border-gray-400 dark:hover:border-gray-500 bg-white dark:bg-gray-900"
            }`}
          >
            <Icon size={20} className={alreadyAdded ? "text-teal-600 dark:text-teal-400" : "text-gray-400 dark:text-gray-500"} />
            <div className="mt-2 text-sm font-medium text-gray-900 dark:text-gray-100">{tpl.name}</div>
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-0.5">{tpl.description}</div>
            <div className="mt-2 text-sm font-semibold text-gray-900 dark:text-gray-100">{fmt(target)}</div>
            {alreadyAdded && <div className="text-xs text-teal-600 dark:text-teal-400 mt-1">Added</div>}
          </button>
        );
      })}
    </div>
  );
}
