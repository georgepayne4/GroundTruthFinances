import type { MortgageData } from "../lib/wizard-types";
import StepShell from "../components/StepShell";
import FieldGroup from "../components/FieldGroup";
import CurrencyInput from "../components/CurrencyInput";
import PercentInput from "../components/PercentInput";
import ToggleField from "../components/ToggleField";

interface MortgageStepProps {
  data: MortgageData;
  onChange: (data: Partial<MortgageData>) => void;
  onNext: () => void;
  onBack: () => void;
  onSkip: () => void;
}

export default function MortgageStep({ data, onChange, onNext, onBack, onSkip }: MortgageStepProps) {
  return (
    <StepShell
      title="Mortgage"
      description="Planning to buy a property? Add details for affordability and readiness analysis."
      onNext={onNext}
      onBack={onBack}
      onSkip={() => {
        onChange({ enabled: false });
        onSkip();
      }}
    >
      <ToggleField
        id="mortgage-enabled"
        label="I'm planning to buy a property"
        checked={data.enabled}
        onChange={(v) => onChange({ enabled: v })}
      />

      {data.enabled && (
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
          <FieldGroup label="Target property value" htmlFor="mortgage-value">
            <CurrencyInput
              id="mortgage-value"
              value={data.target_property_value || null}
              onChange={(v) => onChange({ target_property_value: v })}
              min={0}
              placeholder="e.g. 300000"
            />
          </FieldGroup>
          <FieldGroup label="Deposit percentage" htmlFor="mortgage-deposit" helpText="Minimum 5%, recommended 10-15%">
            <PercentInput
              id="mortgage-deposit"
              value={data.preferred_deposit_pct}
              onChange={(v) => onChange({ preferred_deposit_pct: v })}
              min={0}
              max={100}
            />
          </FieldGroup>
          <FieldGroup label="Mortgage term (years)" htmlFor="mortgage-term">
            <input
              id="mortgage-term"
              type="number"
              inputMode="numeric"
              value={data.preferred_term_years || ""}
              onChange={(e) => onChange({ preferred_term_years: e.target.value === "" ? 25 : Number(e.target.value) })}
              min={5}
              max={40}
              className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
            />
          </FieldGroup>
          <div className="flex items-end pb-1">
            <ToggleField
              id="mortgage-joint"
              label="Joint application (with partner)"
              checked={data.joint_application}
              onChange={(v) => onChange({ joint_application: v })}
            />
          </div>
        </div>
      )}
    </StepShell>
  );
}
