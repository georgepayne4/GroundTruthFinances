import type { WizardState } from "./wizard-types";

export function buildProfile(state: WizardState): Record<string, unknown> {
  const profile: Record<string, unknown> = {};

  // Personal
  const personal: Record<string, unknown> = { age: state.personal.age };
  if (state.personal.name) personal.name = state.personal.name;
  if (state.personal.retirement_age != null) personal.retirement_age = state.personal.retirement_age;
  if (state.personal.dependents > 0) personal.dependents = state.personal.dependents;
  personal.risk_profile = state.personal.risk_profile;
  personal.employment_type = state.personal.employment_type;
  if (state.personal.has_will) personal.has_will = true;
  if (state.personal.has_lpa) personal.has_lpa = true;
  profile.personal = personal;

  // Income
  const income: Record<string, unknown> = {
    primary_gross_annual: state.income.primary_gross_annual || 0,
  };
  if (state.income.partner_gross_annual > 0) income.partner_gross_annual = state.income.partner_gross_annual;
  if (state.income.rental_income_monthly > 0) income.rental_income_monthly = state.income.rental_income_monthly;
  if (state.income.side_income_monthly > 0) income.side_income_monthly = state.income.side_income_monthly;
  if (state.income.bonus_annual_expected > 0) income.bonus_annual_expected = state.income.bonus_annual_expected;
  profile.income = income;

  // Expenses
  profile.expenses = {
    housing: { ...state.expenses.housing },
    transport: { ...state.expenses.transport },
    living: { ...state.expenses.living },
    other: { ...state.expenses.other },
  };

  // Savings
  const savings: Record<string, unknown> = {};
  if (state.savings.emergency_fund > 0) savings.emergency_fund = state.savings.emergency_fund;
  if (state.savings.general_savings > 0) savings.general_savings = state.savings.general_savings;
  if (state.savings.isa_balance > 0) savings.isa_balance = state.savings.isa_balance;
  if (state.savings.pension_balance > 0) savings.pension_balance = state.savings.pension_balance;
  if (state.savings.pension_employer_contribution_pct > 0)
    savings.pension_employer_contribution_pct = state.savings.pension_employer_contribution_pct;
  if (state.savings.pension_personal_contribution_pct > 0)
    savings.pension_personal_contribution_pct = state.savings.pension_personal_contribution_pct;
  if (state.savings.lisa_balance > 0) savings.lisa_balance = state.savings.lisa_balance;
  if (state.savings.other_investments > 0) savings.other_investments = state.savings.other_investments;
  profile.savings = savings;

  // Debts (only if non-empty)
  if (state.debts.length > 0) {
    profile.debts = state.debts.map(({ name, type, balance, interest_rate, minimum_payment_monthly }) => ({
      name,
      type,
      balance,
      interest_rate,
      minimum_payment_monthly,
    }));
  }

  // Goals (only if non-empty)
  if (state.goals.length > 0) {
    profile.goals = state.goals.map(({ name, target_amount, deadline_years, priority, category }) => ({
      name,
      target_amount,
      deadline_years,
      priority,
      category,
    }));
  }

  // Mortgage (only if enabled)
  if (state.mortgage.enabled && state.mortgage.target_property_value > 0) {
    profile.mortgage = {
      target_property_value: state.mortgage.target_property_value,
      preferred_deposit_pct: state.mortgage.preferred_deposit_pct,
      preferred_term_years: state.mortgage.preferred_term_years,
      joint_application: state.mortgage.joint_application,
    };
  }

  // Life events (only if non-empty)
  if (state.lifeEvents.length > 0) {
    profile.life_events = state.lifeEvents.map(
      ({ year_offset, description, income_change_annual, one_off_expense, monthly_expense_change }) => ({
        year_offset,
        description,
        income_change_annual,
        one_off_expense,
        monthly_expense_change,
      }),
    );
  }

  return profile;
}
