import type { LifeEventItem } from "../lib/wizard-types";
import StepShell from "../components/StepShell";
import FieldGroup from "../components/FieldGroup";
import CurrencyInput from "../components/CurrencyInput";
import DynamicList from "../components/DynamicList";

interface LifeEventsStepProps {
  data: LifeEventItem[];
  onChange: (data: LifeEventItem[]) => void;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
}

const TEMPLATES = [
  { label: "Promotion / pay rise", income_change_annual: 5000, one_off_expense: 0, monthly_expense_change: 0 },
  { label: "Have a child", income_change_annual: 0, one_off_expense: 5000, monthly_expense_change: 500 },
  { label: "Buy a home", income_change_annual: 0, one_off_expense: 10000, monthly_expense_change: 200 },
  { label: "Career change", income_change_annual: -5000, one_off_expense: 0, monthly_expense_change: 0 },
];

function createEvent(): LifeEventItem {
  return {
    id: crypto.randomUUID(),
    year_offset: 1,
    description: "",
    income_change_annual: 0,
    one_off_expense: 0,
    monthly_expense_change: 0,
  };
}

export default function LifeEventsStep({ data, onChange, onNext, onBack, onSkip }: LifeEventsStepProps) {
  const updateItem = (index: number, updates: Partial<LifeEventItem>) => {
    const next = [...data];
    next[index] = { ...next[index], ...updates };
    onChange(next);
  };

  const addFromTemplate = (tpl: (typeof TEMPLATES)[number]) => {
    onChange([
      ...data,
      {
        id: crypto.randomUUID(),
        year_offset: 3,
        description: tpl.label,
        income_change_annual: tpl.income_change_annual,
        one_off_expense: tpl.one_off_expense,
        monthly_expense_change: tpl.monthly_expense_change,
      },
    ]);
  };

  return (
    <StepShell
      title="Life Events"
      description="Any major changes you're expecting? These help project your finances over time."
      onNext={onNext}
      onBack={onBack}
      onSkip={onSkip}
    >
      <div>
        <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">Common events</p>
        <div className="flex flex-wrap gap-2">
          {TEMPLATES.map((tpl) => (
            <button
              key={tpl.label}
              type="button"
              onClick={() => addFromTemplate(tpl)}
              className="rounded-full border border-gray-200 dark:border-gray-700 px-3 py-1.5 text-xs font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            >
              + {tpl.label}
            </button>
          ))}
        </div>
      </div>

      <div className="border-t border-gray-100 dark:border-gray-800 pt-4">
        <DynamicList
          items={data}
          onAdd={() => onChange([...data, createEvent()])}
          onRemove={(i) => onChange(data.filter((_, idx) => idx !== i))}
          addLabel="Add life event"
          emptyMessage="No life events added. Use the templates above or add a custom event."
          itemLabel={(item) => item.description || "Unnamed event"}
          renderItem={(item, i) => (
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pr-8">
              <FieldGroup label="Description" htmlFor={`event-desc-${i}`}>
                <input
                  id={`event-desc-${i}`}
                  type="text"
                  value={item.description}
                  onChange={(e) => updateItem(i, { description: e.target.value })}
                  placeholder="e.g. Promotion"
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
                />
              </FieldGroup>
              <FieldGroup label="Years from now" htmlFor={`event-offset-${i}`}>
                <input
                  id={`event-offset-${i}`}
                  type="number"
                  inputMode="numeric"
                  value={item.year_offset || ""}
                  onChange={(e) => updateItem(i, { year_offset: e.target.value === "" ? 1 : Number(e.target.value) })}
                  min={1}
                  max={50}
                  className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
                />
              </FieldGroup>
              <FieldGroup label="Annual income change" htmlFor={`event-income-${i}`} helpText="Positive for increase, negative for decrease">
                <CurrencyInput
                  id={`event-income-${i}`}
                  value={item.income_change_annual || null}
                  onChange={(v) => updateItem(i, { income_change_annual: v })}
                />
              </FieldGroup>
              <FieldGroup label="One-off expense" htmlFor={`event-oneoff-${i}`}>
                <CurrencyInput
                  id={`event-oneoff-${i}`}
                  value={item.one_off_expense || null}
                  onChange={(v) => updateItem(i, { one_off_expense: v })}
                  min={0}
                />
              </FieldGroup>
              <FieldGroup label="Monthly expense change" htmlFor={`event-monthly-${i}`}>
                <CurrencyInput
                  id={`event-monthly-${i}`}
                  value={item.monthly_expense_change || null}
                  onChange={(v) => updateItem(i, { monthly_expense_change: v })}
                />
              </FieldGroup>
            </div>
          )}
        />
      </div>
    </StepShell>
  );
}
