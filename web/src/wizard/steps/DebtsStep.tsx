import type { DebtItem } from "../lib/wizard-types";
import StepShell from "../components/StepShell";
import FieldGroup from "../components/FieldGroup";
import CurrencyInput from "../components/CurrencyInput";
import SelectField from "../components/SelectField";
import DynamicList from "../components/DynamicList";

interface DebtsStepProps {
  data: DebtItem[];
  onChange: (data: DebtItem[]) => void;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
}

const DEBT_TYPES = [
  { value: "student_loan", label: "Student Loan (Plan 2)" },
  { value: "student_loan_postgrad", label: "Student Loan (Postgrad)" },
  { value: "credit_card", label: "Credit Card" },
  { value: "personal_loan", label: "Personal Loan" },
  { value: "car_loan", label: "Car Loan" },
];

function createDebt(): DebtItem {
  return {
    id: crypto.randomUUID(),
    name: "",
    type: "credit_card",
    balance: 0,
    interest_rate: 0,
    minimum_payment_monthly: 0,
  };
}

export default function DebtsStep({ data, onChange, onNext, onBack, onSkip }: DebtsStepProps) {
  const updateItem = (index: number, updates: Partial<DebtItem>) => {
    const next = [...data];
    next[index] = { ...next[index], ...updates };
    onChange(next);
  };

  return (
    <StepShell
      title="Debts"
      description="Add any outstanding debts. Skip this step if you're debt-free."
      onNext={onNext}
      onBack={onBack}
      onSkip={onSkip}
    >
      <DynamicList
        items={data}
        onAdd={() => onChange([...data, createDebt()])}
        onRemove={(i) => onChange(data.filter((_, idx) => idx !== i))}
        addLabel="Add a debt"
        emptyMessage="No debts added. Click below to add one, or skip this step."
        itemLabel={(item) => item.name || "Unnamed debt"}
        renderItem={(item, i) => (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 pr-8">
            <FieldGroup label="Name" htmlFor={`debt-name-${i}`}>
              <input
                id={`debt-name-${i}`}
                type="text"
                value={item.name}
                onChange={(e) => updateItem(i, { name: e.target.value })}
                placeholder="e.g. Barclays Credit Card"
                className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
              />
            </FieldGroup>
            <FieldGroup label="Type" htmlFor={`debt-type-${i}`}>
              <SelectField
                id={`debt-type-${i}`}
                value={item.type}
                onChange={(v) => updateItem(i, { type: v as DebtItem["type"] })}
                options={DEBT_TYPES}
              />
            </FieldGroup>
            <FieldGroup label="Balance" htmlFor={`debt-bal-${i}`}>
              <CurrencyInput
                id={`debt-bal-${i}`}
                value={item.balance || null}
                onChange={(v) => updateItem(i, { balance: v })}
                min={0}
              />
            </FieldGroup>
            <FieldGroup label="Interest rate (%)" htmlFor={`debt-rate-${i}`} helpText="Annual rate, e.g. 19.9">
              <input
                id={`debt-rate-${i}`}
                type="number"
                inputMode="decimal"
                value={item.interest_rate || ""}
                onChange={(e) => updateItem(i, { interest_rate: e.target.value === "" ? 0 : Number(e.target.value) })}
                min={0}
                max={100}
                step={0.1}
                placeholder="e.g. 19.9"
                className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
              />
            </FieldGroup>
            <FieldGroup label="Minimum payment" htmlFor={`debt-min-${i}`} helpText="Monthly minimum">
              <CurrencyInput
                id={`debt-min-${i}`}
                value={item.minimum_payment_monthly || null}
                onChange={(v) => updateItem(i, { minimum_payment_monthly: v })}
                min={0}
              />
            </FieldGroup>
          </div>
        )}
      />
    </StepShell>
  );
}
