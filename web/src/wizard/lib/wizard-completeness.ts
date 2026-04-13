import type { WizardState } from "./wizard-types";

export function calculateCompleteness(state: WizardState): number {
  let score = 0;

  // Personal (20 points)
  if (state.personal.age != null) score += 8;
  if (state.personal.name) score += 2;
  if (state.personal.retirement_age != null) score += 4;
  if (state.personal.risk_profile) score += 3;
  if (state.personal.employment_type) score += 3;

  // Income (25 points)
  if ((state.income.primary_gross_annual ?? 0) > 0) score += 15;
  if (state.income.partner_gross_annual > 0) score += 4;
  if (state.income.side_income_monthly > 0 || state.income.rental_income_monthly > 0) score += 3;
  if (state.income.bonus_annual_expected > 0) score += 3;

  // Expenses (20 points)
  const hasHousing = Object.values(state.expenses.housing).some((v) => v > 0);
  const hasTransport = Object.values(state.expenses.transport).some((v) => v > 0);
  const hasLiving = Object.values(state.expenses.living).some((v) => v > 0);
  const hasOther = Object.values(state.expenses.other).some((v) => v > 0);
  const catCount = [hasHousing, hasTransport, hasLiving, hasOther].filter(Boolean).length;
  if (catCount > 0) score += 10;
  if (catCount === 4) score += 10;
  else if (catCount >= 2) score += 5;

  // Savings (15 points)
  if (state.savings.emergency_fund > 0) score += 4;
  if (state.savings.pension_balance > 0) score += 4;
  if (state.savings.pension_personal_contribution_pct > 0) score += 3;
  if (state.savings.isa_balance > 0 || state.savings.lisa_balance > 0) score += 4;

  // Optional sections (20 points)
  if (state.debts.length > 0) score += 5;
  if (state.goals.length > 0) score += 5;
  if (state.mortgage.enabled) score += 5;
  if (state.lifeEvents.length > 0) score += 5;

  return score;
}

export function completenessLabel(score: number): string {
  if (score < 40) return "Add expenses and savings for more accurate analysis";
  if (score < 70) return "Good profile. Add debts or goals for a more complete picture.";
  return "Great profile! You'll get comprehensive analysis.";
}

export function completenessColor(score: number): string {
  if (score < 40) return "text-red-600 dark:text-red-400";
  if (score < 70) return "text-amber-600 dark:text-amber-400";
  return "text-teal-600 dark:text-teal-400";
}
