import { useState } from "react";
import type { SavingsData } from "../lib/wizard-types";
import StepShell from "../components/StepShell";
import FieldGroup from "../components/FieldGroup";
import CurrencyInput from "../components/CurrencyInput";
import PercentInput from "../components/PercentInput";
import { ChevronDown } from "lucide-react";

interface SavingsStepProps {
  data: SavingsData;
  onChange: (data: Partial<SavingsData>) => void;
  onNext: () => void;
  onBack: () => void;
}

export default function SavingsStep({ data, onChange, onNext, onBack }: SavingsStepProps) {
  const [showMore, setShowMore] = useState(
    data.isa_balance > 0 || data.lisa_balance > 0 || data.other_investments > 0 || data.general_savings > 0,
  );

  return (
    <StepShell
      title="Savings & Investments"
      description="Your current savings, pension, and investment balances."
      onNext={onNext}
      onBack={onBack}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <FieldGroup label="Emergency fund" htmlFor="sav-emergency" helpText="Cash set aside for unexpected expenses">
          <CurrencyInput
            id="sav-emergency"
            value={data.emergency_fund || null}
            onChange={(v) => onChange({ emergency_fund: v })}
            min={0}
          />
        </FieldGroup>

        <FieldGroup label="Pension balance" htmlFor="sav-pension" helpText="Total across all pension pots">
          <CurrencyInput
            id="sav-pension"
            value={data.pension_balance || null}
            onChange={(v) => onChange({ pension_balance: v })}
            min={0}
          />
        </FieldGroup>

        <FieldGroup label="Your pension contribution" htmlFor="sav-pension-personal" helpText="Employee % of gross salary (auto-enrolment min: 5%)">
          <PercentInput
            id="sav-pension-personal"
            value={data.pension_personal_contribution_pct}
            onChange={(v) => onChange({ pension_personal_contribution_pct: v })}
            max={100}
          />
        </FieldGroup>

        <FieldGroup label="Employer pension contribution" htmlFor="sav-pension-employer" helpText="Employer % of gross salary (auto-enrolment min: 3%)">
          <PercentInput
            id="sav-pension-employer"
            value={data.pension_employer_contribution_pct}
            onChange={(v) => onChange({ pension_employer_contribution_pct: v })}
            max={100}
          />
        </FieldGroup>
      </div>

      <button
        type="button"
        onClick={() => setShowMore(!showMore)}
        className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
      >
        <ChevronDown size={16} className={`transition-transform ${showMore ? "rotate-180" : ""}`} />
        ISA, LISA & other investments
      </button>

      {showMore && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <FieldGroup label="General savings" htmlFor="sav-general">
            <CurrencyInput
              id="sav-general"
              value={data.general_savings || null}
              onChange={(v) => onChange({ general_savings: v })}
              min={0}
            />
          </FieldGroup>
          <FieldGroup label="ISA balance" htmlFor="sav-isa">
            <CurrencyInput
              id="sav-isa"
              value={data.isa_balance || null}
              onChange={(v) => onChange({ isa_balance: v })}
              min={0}
            />
          </FieldGroup>
          <FieldGroup label="LISA balance" htmlFor="sav-lisa" helpText="Lifetime ISA (25% bonus on contributions)">
            <CurrencyInput
              id="sav-lisa"
              value={data.lisa_balance || null}
              onChange={(v) => onChange({ lisa_balance: v })}
              min={0}
            />
          </FieldGroup>
          <FieldGroup label="Other investments" htmlFor="sav-other" helpText="GIA, crypto, etc.">
            <CurrencyInput
              id="sav-other"
              value={data.other_investments || null}
              onChange={(v) => onChange({ other_investments: v })}
              min={0}
            />
          </FieldGroup>
        </div>
      )}
    </StepShell>
  );
}
