import { useState } from "react";
import type { PersonalData } from "../lib/wizard-types";
import StepShell from "../components/StepShell";
import FieldGroup from "../components/FieldGroup";
import SelectField from "../components/SelectField";
import ToggleField from "../components/ToggleField";
import { ChevronDown } from "lucide-react";

interface PersonalStepProps {
  data: PersonalData;
  onChange: (data: Partial<PersonalData>) => void;
  onNext: () => void;
}

const RISK_OPTIONS = [
  { value: "conservative", label: "Conservative — Prioritise capital preservation" },
  { value: "moderate", label: "Moderate — Balanced growth and safety" },
  { value: "aggressive", label: "Aggressive — Maximise growth, accept volatility" },
  { value: "very_aggressive", label: "Very Aggressive — Highest growth potential" },
];

const EMPLOYMENT_OPTIONS = [
  { value: "employed", label: "Employed" },
  { value: "self_employed", label: "Self-employed" },
  { value: "contractor", label: "Contractor" },
  { value: "mixed", label: "Mixed income" },
];

export default function PersonalStep({ data, onChange, onNext }: PersonalStepProps) {
  const [showMore, setShowMore] = useState(false);

  const ageError =
    data.age != null && (data.age < 16 || data.age > 100) ? "Age must be between 16 and 100" : undefined;
  const retirementError =
    data.retirement_age != null && data.age != null && data.retirement_age <= data.age
      ? "Retirement age must be greater than current age"
      : undefined;

  const canProceed = data.age != null && data.age >= 16 && data.age <= 100;

  return (
    <StepShell
      title="About you"
      description="We need a few basics to get started. Only your age is required."
      onNext={onNext}
      canProceed={canProceed}
    >
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
        <FieldGroup label="Your name" htmlFor="personal-name" helpText="Optional — personalises your report">
          <input
            id="personal-name"
            type="text"
            value={data.name}
            onChange={(e) => onChange({ name: e.target.value })}
            placeholder="e.g. Sarah"
            className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
          />
        </FieldGroup>

        <FieldGroup label="Age" htmlFor="personal-age" error={ageError} required>
          <input
            id="personal-age"
            type="number"
            inputMode="numeric"
            value={data.age ?? ""}
            onChange={(e) => onChange({ age: e.target.value === "" ? null : Number(e.target.value) })}
            min={16}
            max={100}
            placeholder="e.g. 30"
            required
            aria-required="true"
            aria-invalid={!!ageError}
            aria-describedby={ageError ? "personal-age-error" : undefined}
            className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
          />
        </FieldGroup>

        <FieldGroup label="Target retirement age" htmlFor="personal-retirement" error={retirementError} helpText="Default: 67 (UK state pension age)">
          <input
            id="personal-retirement"
            type="number"
            inputMode="numeric"
            value={data.retirement_age ?? ""}
            onChange={(e) => onChange({ retirement_age: e.target.value === "" ? null : Number(e.target.value) })}
            min={data.age ? data.age + 1 : 17}
            max={100}
            placeholder="67"
            aria-invalid={!!retirementError}
            className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
          />
        </FieldGroup>

        <FieldGroup label="Dependents" htmlFor="personal-dependents" helpText="Children or others financially reliant on you">
          <input
            id="personal-dependents"
            type="number"
            inputMode="numeric"
            value={data.dependents || ""}
            onChange={(e) => onChange({ dependents: e.target.value === "" ? 0 : Number(e.target.value) })}
            min={0}
            max={20}
            placeholder="0"
            className="w-full px-3 py-2 text-sm border border-gray-300 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:border-transparent"
          />
        </FieldGroup>
      </div>

      <FieldGroup label="Risk profile" htmlFor="personal-risk">
        <SelectField
          id="personal-risk"
          value={data.risk_profile}
          onChange={(v) => onChange({ risk_profile: v as PersonalData["risk_profile"] })}
          options={RISK_OPTIONS}
        />
      </FieldGroup>

      <FieldGroup label="Employment type" htmlFor="personal-employment">
        <SelectField
          id="personal-employment"
          value={data.employment_type}
          onChange={(v) => onChange({ employment_type: v as PersonalData["employment_type"] })}
          options={EMPLOYMENT_OPTIONS}
        />
      </FieldGroup>

      {/* Expandable estate planning section */}
      <button
        type="button"
        onClick={() => setShowMore(!showMore)}
        className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300 transition-colors"
      >
        <ChevronDown size={16} className={`transition-transform ${showMore ? "rotate-180" : ""}`} />
        Estate planning
      </button>

      {showMore && (
        <div className="space-y-3 pl-1">
          <ToggleField id="personal-will" label="I have a valid will" checked={data.has_will} onChange={(v) => onChange({ has_will: v })} />
          <ToggleField id="personal-lpa" label="I have a Lasting Power of Attorney" checked={data.has_lpa} onChange={(v) => onChange({ has_lpa: v })} />
        </div>
      )}
    </StepShell>
  );
}
