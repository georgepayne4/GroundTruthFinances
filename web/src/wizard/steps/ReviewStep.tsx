import type { WizardState } from "../lib/wizard-types";
import { calculateCompleteness } from "../lib/wizard-completeness";
import { getTotalMonthlyExpenses } from "../lib/wizard-defaults";
import CompletenessScore from "../components/CompletenessScore";

function fmt(n: number | null | undefined): string {
  if (n == null) return "-";
  return n.toLocaleString("en-GB", { style: "currency", currency: "GBP", maximumFractionDigits: 0 });
}

interface ReviewStepProps {
  state: WizardState;
  onEdit: (step: number) => void;
  onSubmit: () => void;
  loading: boolean;
  error: string | null;
}

interface SectionProps {
  title: string;
  step: number;
  onEdit: (step: number) => void;
  children: React.ReactNode;
}

function Section({ title, step, onEdit, children }: SectionProps) {
  return (
    <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 uppercase tracking-wide">{title}</h3>
        <button
          type="button"
          onClick={() => onEdit(step)}
          className="text-xs font-medium text-gray-500 dark:text-gray-400 hover:text-gray-900 dark:hover:text-gray-100 transition-colors"
        >
          Edit
        </button>
      </div>
      <div className="space-y-1 text-sm">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-600 dark:text-gray-400">{label}</span>
      <span className="font-medium text-gray-900 dark:text-gray-100">{value}</span>
    </div>
  );
}

export default function ReviewStep({ state, onEdit, onSubmit, loading, error }: ReviewStepProps) {
  const completeness = calculateCompleteness(state);
  const monthlyExpenses = getTotalMonthlyExpenses(state.expenses);

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-6 shadow-sm">
        <div className="flex items-start justify-between mb-6">
          <div>
            <h2 className="text-lg font-bold text-gray-900 dark:text-gray-100">Review your profile</h2>
            <p className="text-sm text-gray-600 dark:text-gray-400">Check your details, then run your analysis.</p>
          </div>
          <CompletenessScore score={completeness} showLabel={false} />
        </div>

        {error && (
          <div role="alert" className="mb-4 rounded-lg bg-red-50 dark:bg-red-950 border border-red-200 dark:border-red-800 px-4 py-3 text-sm text-red-800 dark:text-red-200">
            {error}
          </div>
        )}

        <div className="space-y-4">
          <Section title="Personal" step={0} onEdit={onEdit}>
            <Row label="Name" value={state.personal.name || "-"} />
            <Row label="Age" value={state.personal.age != null ? String(state.personal.age) : "-"} />
            <Row label="Retirement age" value={state.personal.retirement_age != null ? String(state.personal.retirement_age) : "67 (default)"} />
            <Row label="Risk profile" value={state.personal.risk_profile} />
            <Row label="Employment" value={state.personal.employment_type.replace("_", " ")} />
          </Section>

          <Section title="Income" step={1} onEdit={onEdit}>
            <Row label="Gross salary" value={fmt(state.income.primary_gross_annual)} />
            {state.income.partner_gross_annual > 0 && <Row label="Partner salary" value={fmt(state.income.partner_gross_annual)} />}
            {state.income.side_income_monthly > 0 && <Row label="Side income" value={`${fmt(state.income.side_income_monthly)}/mo`} />}
            {state.income.rental_income_monthly > 0 && <Row label="Rental income" value={`${fmt(state.income.rental_income_monthly)}/mo`} />}
            {state.income.bonus_annual_expected > 0 && <Row label="Expected bonus" value={fmt(state.income.bonus_annual_expected)} />}
          </Section>

          <Section title="Expenses" step={2} onEdit={onEdit}>
            <Row label="Total monthly" value={`${fmt(monthlyExpenses)}/mo`} />
          </Section>

          <Section title="Savings" step={3} onEdit={onEdit}>
            <Row label="Emergency fund" value={fmt(state.savings.emergency_fund)} />
            <Row label="Pension" value={fmt(state.savings.pension_balance)} />
            <Row label="Pension contributions" value={`${(state.savings.pension_personal_contribution_pct * 100).toFixed(0)}% + ${(state.savings.pension_employer_contribution_pct * 100).toFixed(0)}% employer`} />
            {state.savings.isa_balance > 0 && <Row label="ISA" value={fmt(state.savings.isa_balance)} />}
            {state.savings.lisa_balance > 0 && <Row label="LISA" value={fmt(state.savings.lisa_balance)} />}
          </Section>

          {state.debts.length > 0 && (
            <Section title={`Debts (${state.debts.length})`} step={4} onEdit={onEdit}>
              {state.debts.map((d) => (
                <Row key={d.id} label={d.name || d.type} value={fmt(d.balance)} />
              ))}
            </Section>
          )}

          {state.goals.length > 0 && (
            <Section title={`Goals (${state.goals.length})`} step={5} onEdit={onEdit}>
              {state.goals.map((g) => (
                <Row key={g.id} label={g.name} value={`${fmt(g.target_amount)} in ${g.deadline_years}yr`} />
              ))}
            </Section>
          )}

          {state.mortgage.enabled && (
            <Section title="Mortgage" step={6} onEdit={onEdit}>
              <Row label="Property value" value={fmt(state.mortgage.target_property_value)} />
              <Row label="Deposit" value={`${(state.mortgage.preferred_deposit_pct * 100).toFixed(0)}%`} />
              <Row label="Term" value={`${state.mortgage.preferred_term_years} years`} />
            </Section>
          )}

          {state.lifeEvents.length > 0 && (
            <Section title={`Life Events (${state.lifeEvents.length})`} step={7} onEdit={onEdit}>
              {state.lifeEvents.map((e) => (
                <Row key={e.id} label={e.description || "Event"} value={`Year ${e.year_offset}`} />
              ))}
            </Section>
          )}
        </div>

        <div className="mt-8 pt-5 border-t border-gray-100 dark:border-gray-800 flex justify-end">
          <button
            type="button"
            onClick={onSubmit}
            disabled={loading || state.personal.age == null || (state.income.primary_gross_annual ?? 0) <= 0}
            aria-busy={loading}
            className="rounded-lg bg-gray-900 dark:bg-gray-100 px-8 py-2.5 text-sm font-medium text-white dark:text-gray-900 hover:bg-gray-700 dark:hover:bg-gray-300 focus:outline-none focus:ring-2 focus:ring-gray-900 dark:focus:ring-gray-100 focus:ring-offset-2 disabled:opacity-50 transition-colors"
          >
            {loading ? "Analysing..." : "Run Analysis"}
          </button>
        </div>
      </div>
    </div>
  );
}
