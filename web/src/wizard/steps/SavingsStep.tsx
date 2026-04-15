import { useState } from "react";
import type { SavingsData } from "../lib/wizard-types";
import StepShell from "../components/StepShell";
import FieldGroup from "../components/FieldGroup";
import CurrencyInput from "../components/CurrencyInput";
import PercentInput from "../components/PercentInput";
import { ChevronDown } from "lucide-react";
import { validateNumber, hasErrors } from "../lib/validation";

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

  const errors = {
    emergency: validateNumber(data.emergency_fund, { min: 0, max: 10_000_000, label: "Emergency fund" }),
    pension: validateNumber(data.pension_balance, { min: 0, max: 100_000_000, label: "Pension balance" }),
    pensionSelf:
      data.pension_personal_contribution_pct < 0 || data.pension_personal_contribution_pct > 1
        ? "Personal contribution must be between 0 and 100%"
        : undefined,
    pensionEmp:
      data.pension_employer_contribution_pct < 0 || data.pension_employer_contribution_pct > 1
        ? "Employer contribution must be between 0 and 100%"
        : undefined,
    general: showMore
      ? validateNumber(data.general_savings, { min: 0, max: 10_000_000, label: "General savings" })
      : undefined,
    isa: showMore ? validateNumber(data.isa_balance, { min: 0, max: 10_000_000, label: "ISA balance" }) : undefined,
    lisa: showMore ? validateNumber(data.lisa_balance, { min: 0, max: 10_000_000, label: "LISA balance" }) : undefined,
    other: showMore ? validateNumber(data.other_investments, { min: 0, max: 100_000_000, label: "Other investments" }) : undefined,
  };

  const canProceed = !hasErrors(errors);

  return (
    <StepShell
      title="Savings & Investments"
      description="Your current savings, pension, and investment balances."
      onNext={onNext}
      onBack={onBack}
      canProceed={canProceed}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <FieldGroup label="Emergency fund" htmlFor="sav-emergency" error={errors.emergency} helpText={errors.emergency ? undefined : "Cash set aside for unexpected expenses"}>
          <CurrencyInput
            id="sav-emergency"
            value={data.emergency_fund || null}
            onChange={(v) => onChange({ emergency_fund: v })}
            min={0}
            error={errors.emergency}
          />
        </FieldGroup>

        <FieldGroup label="Pension balance" htmlFor="sav-pension" error={errors.pension} helpText={errors.pension ? undefined : "Total across all pension pots"}>
          <CurrencyInput
            id="sav-pension"
            value={data.pension_balance || null}
            onChange={(v) => onChange({ pension_balance: v })}
            min={0}
            error={errors.pension}
          />
        </FieldGroup>

        <FieldGroup label="Your pension contribution" htmlFor="sav-pension-personal" error={errors.pensionSelf} helpText={errors.pensionSelf ? undefined : "Employee % of gross salary (auto-enrolment min: 5%)"}>
          <PercentInput
            id="sav-pension-personal"
            value={data.pension_personal_contribution_pct}
            onChange={(v) => onChange({ pension_personal_contribution_pct: v })}
            max={100}
            error={errors.pensionSelf}
          />
        </FieldGroup>

        <FieldGroup label="Employer pension contribution" htmlFor="sav-pension-employer" error={errors.pensionEmp} helpText={errors.pensionEmp ? undefined : "Employer % of gross salary (auto-enrolment min: 3%)"}>
          <PercentInput
            id="sav-pension-employer"
            value={data.pension_employer_contribution_pct}
            onChange={(v) => onChange({ pension_employer_contribution_pct: v })}
            max={100}
            error={errors.pensionEmp}
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
          <FieldGroup label="General savings" htmlFor="sav-general" error={errors.general}>
            <CurrencyInput
              id="sav-general"
              value={data.general_savings || null}
              onChange={(v) => onChange({ general_savings: v })}
              min={0}
              error={errors.general}
            />
          </FieldGroup>
          <FieldGroup label="ISA balance" htmlFor="sav-isa" error={errors.isa}>
            <CurrencyInput
              id="sav-isa"
              value={data.isa_balance || null}
              onChange={(v) => onChange({ isa_balance: v })}
              min={0}
              error={errors.isa}
            />
          </FieldGroup>
          <FieldGroup label="LISA balance" htmlFor="sav-lisa" error={errors.lisa} helpText={errors.lisa ? undefined : "Lifetime ISA (25% bonus on contributions)"}>
            <CurrencyInput
              id="sav-lisa"
              value={data.lisa_balance || null}
              onChange={(v) => onChange({ lisa_balance: v })}
              min={0}
              error={errors.lisa}
            />
          </FieldGroup>
          <FieldGroup label="Other investments" htmlFor="sav-other" error={errors.other} helpText={errors.other ? undefined : "GIA, crypto, etc."}>
            <CurrencyInput
              id="sav-other"
              value={data.other_investments || null}
              onChange={(v) => onChange({ other_investments: v })}
              min={0}
              error={errors.other}
            />
          </FieldGroup>
        </div>
      )}
    </StepShell>
  );
}
