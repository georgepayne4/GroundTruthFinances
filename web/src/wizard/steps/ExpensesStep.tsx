import { useState } from "react";
import type { ExpensesData } from "../lib/wizard-types";
import StepShell from "../components/StepShell";
import FieldGroup from "../components/FieldGroup";
import CurrencyInput from "../components/CurrencyInput";
import { ChevronDown } from "lucide-react";

interface ExpensesStepProps {
  data: ExpensesData;
  onChange: (data: ExpensesData) => void;
  onNext: () => void;
  onBack: () => void;
  hasDefaults: boolean;
}

function categoryTotal(cat: Record<string, number>, annualFields: string[] = []): number {
  return Object.entries(cat).reduce((sum, [key, val]) => {
    if (annualFields.includes(key)) return sum + val / 12;
    return sum + val;
  }, 0);
}

function fmt(n: number): string {
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

interface CategorySectionProps {
  title: string;
  total: number;
  expanded: boolean;
  onToggle: () => void;
  children: React.ReactNode;
}

function CategorySection({ title, total, expanded, onToggle, children }: CategorySectionProps) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700">
      <button
        type="button"
        onClick={onToggle}
        className="w-full flex items-center justify-between p-4 text-left hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
      >
        <span className="text-sm font-medium text-gray-900 dark:text-gray-100">{title}</span>
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500 dark:text-gray-400">{fmt(total)}/mo</span>
          <ChevronDown size={16} className={`text-gray-400 transition-transform ${expanded ? "rotate-180" : ""}`} />
        </div>
      </button>
      {expanded && <div className="p-4 pt-0 space-y-4">{children}</div>}
    </div>
  );
}

export default function ExpensesStep({ data, onChange, onNext, onBack, hasDefaults }: ExpensesStepProps) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({});

  const toggle = (key: string) => setExpanded((prev) => ({ ...prev, [key]: !prev[key] }));

  const updateCategory = <K extends keyof ExpensesData>(
    category: K,
    field: string,
    value: number,
  ) => {
    onChange({
      ...data,
      [category]: { ...data[category], [field]: value },
    });
  };

  const housingTotal = categoryTotal(data.housing);
  const transportTotal = categoryTotal(data.transport);
  const livingTotal = categoryTotal(data.living);
  const otherTotal = categoryTotal(data.other, ["holidays_annual", "gifts_annual"]);
  const grandTotal = housingTotal + transportTotal + livingTotal + otherTotal;

  return (
    <StepShell
      title="Expenses"
      description="Your monthly spending by category. Expand each section to adjust individual items."
      onNext={onNext}
      onBack={onBack}
    >
      {hasDefaults && (
        <div className="rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 px-4 py-3 text-xs text-blue-700 dark:text-blue-300">
          Estimated from UK averages for your income bracket. Adjust as needed.
        </div>
      )}

      <div className="space-y-3">
        <CategorySection title="Housing" total={housingTotal} expanded={!!expanded.housing} onToggle={() => toggle("housing")}>
          <div className="grid grid-cols-2 gap-4">
            <FieldGroup label="Rent / mortgage" htmlFor="exp-rent">
              <CurrencyInput id="exp-rent" value={data.housing.rent_monthly || null} onChange={(v) => updateCategory("housing", "rent_monthly", v)} />
            </FieldGroup>
            <FieldGroup label="Council tax" htmlFor="exp-council">
              <CurrencyInput id="exp-council" value={data.housing.council_tax_monthly || null} onChange={(v) => updateCategory("housing", "council_tax_monthly", v)} />
            </FieldGroup>
            <FieldGroup label="Utilities" htmlFor="exp-utilities">
              <CurrencyInput id="exp-utilities" value={data.housing.utilities_monthly || null} onChange={(v) => updateCategory("housing", "utilities_monthly", v)} />
            </FieldGroup>
            <FieldGroup label="Home insurance" htmlFor="exp-insurance">
              <CurrencyInput id="exp-insurance" value={data.housing.insurance_monthly || null} onChange={(v) => updateCategory("housing", "insurance_monthly", v)} />
            </FieldGroup>
          </div>
        </CategorySection>

        <CategorySection title="Transport" total={transportTotal} expanded={!!expanded.transport} onToggle={() => toggle("transport")}>
          <div className="grid grid-cols-2 gap-4">
            <FieldGroup label="Car payment" htmlFor="exp-car">
              <CurrencyInput id="exp-car" value={data.transport.car_payment_monthly || null} onChange={(v) => updateCategory("transport", "car_payment_monthly", v)} />
            </FieldGroup>
            <FieldGroup label="Fuel" htmlFor="exp-fuel">
              <CurrencyInput id="exp-fuel" value={data.transport.fuel_monthly || null} onChange={(v) => updateCategory("transport", "fuel_monthly", v)} />
            </FieldGroup>
            <FieldGroup label="Public transport" htmlFor="exp-public">
              <CurrencyInput id="exp-public" value={data.transport.public_transport_monthly || null} onChange={(v) => updateCategory("transport", "public_transport_monthly", v)} />
            </FieldGroup>
          </div>
        </CategorySection>

        <CategorySection title="Living" total={livingTotal} expanded={!!expanded.living} onToggle={() => toggle("living")}>
          <div className="grid grid-cols-2 gap-4">
            <FieldGroup label="Groceries" htmlFor="exp-groceries">
              <CurrencyInput id="exp-groceries" value={data.living.groceries_monthly || null} onChange={(v) => updateCategory("living", "groceries_monthly", v)} />
            </FieldGroup>
            <FieldGroup label="Dining out" htmlFor="exp-dining">
              <CurrencyInput id="exp-dining" value={data.living.dining_out_monthly || null} onChange={(v) => updateCategory("living", "dining_out_monthly", v)} />
            </FieldGroup>
            <FieldGroup label="Subscriptions" htmlFor="exp-subs">
              <CurrencyInput id="exp-subs" value={data.living.subscriptions_monthly || null} onChange={(v) => updateCategory("living", "subscriptions_monthly", v)} />
            </FieldGroup>
            <FieldGroup label="Clothing" htmlFor="exp-clothing">
              <CurrencyInput id="exp-clothing" value={data.living.clothing_monthly || null} onChange={(v) => updateCategory("living", "clothing_monthly", v)} />
            </FieldGroup>
            <FieldGroup label="Personal care" htmlFor="exp-personal">
              <CurrencyInput id="exp-personal" value={data.living.personal_care_monthly || null} onChange={(v) => updateCategory("living", "personal_care_monthly", v)} />
            </FieldGroup>
          </div>
        </CategorySection>

        <CategorySection title="Other" total={otherTotal} expanded={!!expanded.other} onToggle={() => toggle("other")}>
          <div className="grid grid-cols-2 gap-4">
            <FieldGroup label="Phone" htmlFor="exp-phone">
              <CurrencyInput id="exp-phone" value={data.other.phone_monthly || null} onChange={(v) => updateCategory("other", "phone_monthly", v)} />
            </FieldGroup>
            <FieldGroup label="Gym" htmlFor="exp-gym">
              <CurrencyInput id="exp-gym" value={data.other.gym_monthly || null} onChange={(v) => updateCategory("other", "gym_monthly", v)} />
            </FieldGroup>
            <FieldGroup label="Holidays (annual)" htmlFor="exp-holidays">
              <CurrencyInput id="exp-holidays" value={data.other.holidays_annual || null} onChange={(v) => updateCategory("other", "holidays_annual", v)} />
            </FieldGroup>
            <FieldGroup label="Gifts (annual)" htmlFor="exp-gifts">
              <CurrencyInput id="exp-gifts" value={data.other.gifts_annual || null} onChange={(v) => updateCategory("other", "gifts_annual", v)} />
            </FieldGroup>
            <FieldGroup label="Miscellaneous" htmlFor="exp-misc">
              <CurrencyInput id="exp-misc" value={data.other.miscellaneous_monthly || null} onChange={(v) => updateCategory("other", "miscellaneous_monthly", v)} />
            </FieldGroup>
          </div>
        </CategorySection>
      </div>

      <div className="flex justify-between text-sm font-medium pt-2">
        <span className="text-gray-700 dark:text-gray-300">Total monthly expenses</span>
        <span className="text-gray-900 dark:text-gray-100">{fmt(grandTotal)}/mo</span>
      </div>
    </StepShell>
  );
}
