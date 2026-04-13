import { useState } from "react";
import type { IncomeData } from "../lib/wizard-types";
import StepShell from "../components/StepShell";
import FieldGroup from "../components/FieldGroup";
import CurrencyInput from "../components/CurrencyInput";
import { ChevronDown } from "lucide-react";

interface IncomeStepProps {
  data: IncomeData;
  onChange: (data: Partial<IncomeData>) => void;
  onNext: () => void;
  onBack: () => void;
}

export default function IncomeStep({ data, onChange, onNext, onBack }: IncomeStepProps) {
  const [showPartner, setShowPartner] = useState(data.partner_gross_annual > 0);
  const [showOther, setShowOther] = useState(
    data.rental_income_monthly > 0 || data.side_income_monthly > 0 || data.bonus_annual_expected > 0,
  );

  const incomeError =
    data.primary_gross_annual != null && data.primary_gross_annual <= 0
      ? "Enter your gross annual salary"
      : undefined;
  const incomeWarning =
    data.primary_gross_annual != null && data.primary_gross_annual > 0 && data.primary_gross_annual < 10000
      ? "This looks low — is this your annual (not monthly) salary?"
      : undefined;

  const canProceed = data.primary_gross_annual != null && data.primary_gross_annual > 0;

  return (
    <StepShell
      title="Income"
      description="Your gross (before tax) annual salary is essential. Add partner or other income if applicable."
      onNext={onNext}
      onBack={onBack}
      canProceed={canProceed}
    >
      <FieldGroup
        label="Gross annual salary"
        htmlFor="income-primary"
        error={incomeError}
        helpText={incomeWarning || "Your total annual salary before tax and deductions"}
        required
      >
        <CurrencyInput
          id="income-primary"
          value={data.primary_gross_annual}
          onChange={(v) => onChange({ primary_gross_annual: v })}
          min={0}
          placeholder="e.g. 50000"
          required
          aria-describedby={incomeError ? "income-primary-error" : "income-primary-help"}
        />
      </FieldGroup>

      {/* Partner income */}
      <button
        type="button"
        onClick={() => setShowPartner(!showPartner)}
        className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
      >
        <ChevronDown size={16} className={`transition-transform ${showPartner ? "rotate-180" : ""}`} />
        Add partner income
      </button>

      {showPartner && (
        <FieldGroup label="Partner gross annual salary" htmlFor="income-partner">
          <CurrencyInput
            id="income-partner"
            value={data.partner_gross_annual || null}
            onChange={(v) => onChange({ partner_gross_annual: v })}
            min={0}
          />
        </FieldGroup>
      )}

      {/* Other income */}
      <button
        type="button"
        onClick={() => setShowOther(!showOther)}
        className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
      >
        <ChevronDown size={16} className={`transition-transform ${showOther ? "rotate-180" : ""}`} />
        Add other income
      </button>

      {showOther && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <FieldGroup label="Rental income (monthly)" htmlFor="income-rental">
            <CurrencyInput
              id="income-rental"
              value={data.rental_income_monthly || null}
              onChange={(v) => onChange({ rental_income_monthly: v })}
              min={0}
            />
          </FieldGroup>
          <FieldGroup label="Side income (monthly)" htmlFor="income-side">
            <CurrencyInput
              id="income-side"
              value={data.side_income_monthly || null}
              onChange={(v) => onChange({ side_income_monthly: v })}
              min={0}
            />
          </FieldGroup>
          <FieldGroup label="Expected annual bonus" htmlFor="income-bonus">
            <CurrencyInput
              id="income-bonus"
              value={data.bonus_annual_expected || null}
              onChange={(v) => onChange({ bonus_annual_expected: v })}
              min={0}
            />
          </FieldGroup>
        </div>
      )}
    </StepShell>
  );
}
