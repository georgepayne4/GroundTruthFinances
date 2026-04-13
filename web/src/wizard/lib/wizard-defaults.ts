import type { ExpensesData, WizardState } from "./wizard-types";

/** Simplified UK tax/NI estimate for expense defaulting only. Not used for real calculations. */
export function estimateNetMonthly(grossAnnual: number): number {
  const pa = 12570;
  const basicThresh = 50270;
  const higherThresh = 125140;
  const basicRate = 0.20;
  const higherRate = 0.40;
  const additionalRate = 0.45;
  const niRate = 0.08;
  const niThreshold = 12570;
  const niUpperLimit = 50270;
  const niUpperRate = 0.02;

  let tax = 0;
  if (grossAnnual > higherThresh) {
    tax += (grossAnnual - higherThresh) * additionalRate;
    tax += (higherThresh - basicThresh) * higherRate;
    tax += (basicThresh - pa) * basicRate;
  } else if (grossAnnual > basicThresh) {
    tax += (grossAnnual - basicThresh) * higherRate;
    tax += (basicThresh - pa) * basicRate;
  } else if (grossAnnual > pa) {
    tax += (grossAnnual - pa) * basicRate;
  }

  let ni = 0;
  if (grossAnnual > niUpperLimit) {
    ni += (grossAnnual - niUpperLimit) * niUpperRate;
    ni += (niUpperLimit - niThreshold) * niRate;
  } else if (grossAnnual > niThreshold) {
    ni += (grossAnnual - niThreshold) * niRate;
  }

  return Math.max(0, Math.round((grossAnnual - tax - ni) / 12));
}

export function getExpenseDefaults(grossAnnual: number): ExpensesData {
  const net = estimateNetMonthly(grossAnnual);

  return {
    housing: {
      rent_monthly: Math.round(net * 0.28),
      council_tax_monthly: 150,
      utilities_monthly: Math.round(net * 0.04),
      insurance_monthly: 30,
    },
    transport: {
      car_payment_monthly: 0,
      fuel_monthly: Math.round(net * 0.04),
      public_transport_monthly: Math.round(net * 0.04),
    },
    living: {
      groceries_monthly: Math.round(net * 0.10),
      dining_out_monthly: Math.round(net * 0.04),
      subscriptions_monthly: 50,
      clothing_monthly: Math.round(net * 0.02),
      personal_care_monthly: 30,
    },
    other: {
      phone_monthly: 35,
      gym_monthly: 35,
      holidays_annual: Math.round(grossAnnual * 0.03),
      gifts_annual: 500,
      miscellaneous_monthly: Math.round(net * 0.03),
    },
  };
}

export function getTotalMonthlyExpenses(expenses: ExpensesData): number {
  const housing = Object.values(expenses.housing).reduce((a, b) => a + b, 0);
  const transport = Object.values(expenses.transport).reduce((a, b) => a + b, 0);
  const living = Object.values(expenses.living).reduce((a, b) => a + b, 0);
  const otherMonthly =
    expenses.other.phone_monthly +
    expenses.other.gym_monthly +
    expenses.other.miscellaneous_monthly +
    expenses.other.holidays_annual / 12 +
    expenses.other.gifts_annual / 12;
  return housing + transport + living + otherMonthly;
}

export interface TemplateGoal {
  key: string;
  name: string;
  description: string;
  getTarget: (state: WizardState) => number;
  deadline_years: number;
  priority: number;
  category: "safety_net" | "property" | "lifestyle";
}

export const TEMPLATE_GOALS: TemplateGoal[] = [
  {
    key: "emergency_fund",
    name: "Build emergency fund",
    description: "6 months of expenses as a financial safety net",
    getTarget: (state) => Math.round(getTotalMonthlyExpenses(state.expenses) * 6) || 10000,
    deadline_years: 2,
    priority: 1,
    category: "safety_net",
  },
  {
    key: "house_deposit",
    name: "Save for house deposit",
    description: "10% deposit based on 5x your income",
    getTarget: (state) => Math.round((state.income.primary_gross_annual || 50000) * 5 * 0.10),
    deadline_years: 5,
    priority: 2,
    category: "property",
  },
  {
    key: "retirement",
    name: "Comfortable retirement",
    description: "Target pension pot for £30k/year income in retirement",
    getTarget: (state) => Math.max(0, 750000 - state.savings.pension_balance),
    deadline_years: 40,
    priority: 3,
    category: "lifestyle",
  },
];
