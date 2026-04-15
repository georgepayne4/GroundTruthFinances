import type { GoalItem, WizardState } from "../lib/wizard-types";
import StepShell from "../components/StepShell";
import FieldGroup from "../components/FieldGroup";
import CurrencyInput from "../components/CurrencyInput";
import SelectField from "../components/SelectField";
import DynamicList from "../components/DynamicList";
import TemplateGoalPicker from "../components/TemplateGoalPicker";
import { validateNumber } from "../lib/validation";

interface GoalsStepProps {
  data: GoalItem[];
  wizardState: WizardState;
  onChange: (data: GoalItem[]) => void;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
}

const PRIORITY_OPTIONS = [
  { value: "1", label: "High" },
  { value: "2", label: "Medium" },
  { value: "3", label: "Low" },
];

const CATEGORY_OPTIONS = [
  { value: "safety_net", label: "Safety net" },
  { value: "property", label: "Property" },
  { value: "education", label: "Education" },
  { value: "lifestyle", label: "Lifestyle" },
  { value: "general", label: "General" },
];

function createGoal(): GoalItem {
  return {
    id: crypto.randomUUID(),
    name: "",
    target_amount: 0,
    deadline_years: 5,
    priority: 2,
    category: "general",
  };
}

function goalErrors(item: GoalItem) {
  return {
    target: validateNumber(item.target_amount, { min: 0, max: 100_000_000, label: "Target amount" }),
    deadline: validateNumber(item.deadline_years, { min: 1, max: 60, label: "Deadline" }),
  };
}

export default function GoalsStep({ data, wizardState, onChange, onNext, onBack, onSkip }: GoalsStepProps) {
  const updateItem = (index: number, updates: Partial<GoalItem>) => {
    const next = [...data];
    next[index] = { ...next[index], ...updates };
    onChange(next);
  };

  const canProceed = data.every((item) => {
    const e = goalErrors(item);
    return !e.target && !e.deadline;
  });

  return (
    <StepShell
      title="Goals"
      description="What are you saving for? Pick from templates or add your own."
      onNext={onNext}
      onBack={onBack}
      onSkip={onSkip}
      canProceed={canProceed}
    >
      <div>
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Quick add</p>
        <TemplateGoalPicker
          state={wizardState}
          goals={data}
          onAdd={(goal) => onChange([...data, goal])}
        />
      </div>

      <div className="border-t border-gray-100 dark:border-gray-800 pt-4">
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Your goals</p>
        <DynamicList
          items={data}
          onAdd={() => onChange([...data, createGoal()])}
          onRemove={(i) => onChange(data.filter((_, idx) => idx !== i))}
          addLabel="Add custom goal"
          emptyMessage="No goals yet. Use the templates above or add a custom goal."
          itemLabel={(item) => item.name || "Unnamed goal"}
          renderItem={(item, i) => {
            const errors = goalErrors(item);
            const deadlineBorder = errors.deadline
              ? "border-red-500 dark:border-red-500 focus:ring-red-500"
              : "border-gray-300 dark:border-gray-700 focus:ring-gray-900 dark:focus:ring-gray-100";
            return (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pr-8">
              <FieldGroup label="Goal name" htmlFor={`goal-name-${i}`}>
                <input
                  id={`goal-name-${i}`}
                  type="text"
                  value={item.name}
                  onChange={(e) => updateItem(i, { name: e.target.value })}
                  placeholder="e.g. House deposit"
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
                />
              </FieldGroup>
              <FieldGroup label="Target amount" htmlFor={`goal-target-${i}`} error={errors.target}>
                <CurrencyInput
                  id={`goal-target-${i}`}
                  value={item.target_amount || null}
                  onChange={(v) => updateItem(i, { target_amount: v })}
                  min={0}
                  error={errors.target}
                />
              </FieldGroup>
              <FieldGroup label="Deadline (years)" htmlFor={`goal-deadline-${i}`} error={errors.deadline}>
                <input
                  id={`goal-deadline-${i}`}
                  type="number"
                  inputMode="numeric"
                  value={item.deadline_years || ""}
                  onChange={(e) => updateItem(i, { deadline_years: e.target.value === "" ? 0 : Number(e.target.value) })}
                  min={1}
                  max={60}
                  aria-invalid={!!errors.deadline}
                  aria-describedby={errors.deadline ? `goal-deadline-${i}-error` : undefined}
                  className={`w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:border-transparent ${deadlineBorder}`}
                />
              </FieldGroup>
              <FieldGroup label="Priority" htmlFor={`goal-priority-${i}`}>
                <SelectField
                  id={`goal-priority-${i}`}
                  value={String(item.priority)}
                  onChange={(v) => updateItem(i, { priority: Number(v) })}
                  options={PRIORITY_OPTIONS}
                />
              </FieldGroup>
              <FieldGroup label="Category" htmlFor={`goal-category-${i}`}>
                <SelectField
                  id={`goal-category-${i}`}
                  value={item.category}
                  onChange={(v) => updateItem(i, { category: v as GoalItem["category"] })}
                  options={CATEGORY_OPTIONS}
                />
              </FieldGroup>
            </div>
            );
          }}
        />
      </div>
    </StepShell>
  );
}
