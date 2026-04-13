export interface PersonalData {
  age: number | null;
  name: string;
  retirement_age: number | null;
  dependents: number;
  risk_profile: "conservative" | "moderate" | "aggressive" | "very_aggressive";
  employment_type: "employed" | "self_employed" | "contractor" | "mixed";
  has_will: boolean;
  has_lpa: boolean;
}

export interface IncomeData {
  primary_gross_annual: number | null;
  partner_gross_annual: number;
  rental_income_monthly: number;
  side_income_monthly: number;
  bonus_annual_expected: number;
}

export interface ExpenseCategory {
  [key: string]: number;
}

export interface ExpensesData {
  housing: {
    rent_monthly: number;
    council_tax_monthly: number;
    utilities_monthly: number;
    insurance_monthly: number;
  };
  transport: {
    car_payment_monthly: number;
    fuel_monthly: number;
    public_transport_monthly: number;
  };
  living: {
    groceries_monthly: number;
    dining_out_monthly: number;
    subscriptions_monthly: number;
    clothing_monthly: number;
    personal_care_monthly: number;
  };
  other: {
    phone_monthly: number;
    gym_monthly: number;
    holidays_annual: number;
    gifts_annual: number;
    miscellaneous_monthly: number;
  };
}

export interface SavingsData {
  emergency_fund: number;
  general_savings: number;
  isa_balance: number;
  pension_balance: number;
  pension_employer_contribution_pct: number;
  pension_personal_contribution_pct: number;
  lisa_balance: number;
  other_investments: number;
}

export interface DebtItem {
  id: string;
  name: string;
  type: "student_loan" | "student_loan_postgrad" | "credit_card" | "personal_loan" | "car_loan";
  balance: number;
  interest_rate: number;
  minimum_payment_monthly: number;
}

export interface GoalItem {
  id: string;
  name: string;
  target_amount: number;
  deadline_years: number;
  priority: number;
  category: "safety_net" | "property" | "education" | "lifestyle" | "general";
  fromTemplate?: string;
}

export interface MortgageData {
  enabled: boolean;
  target_property_value: number;
  preferred_deposit_pct: number;
  preferred_term_years: number;
  joint_application: boolean;
}

export interface LifeEventItem {
  id: string;
  year_offset: number;
  description: string;
  income_change_annual: number;
  one_off_expense: number;
  monthly_expense_change: number;
}

export interface WizardState {
  personal: PersonalData;
  income: IncomeData;
  expenses: ExpensesData;
  savings: SavingsData;
  debts: DebtItem[];
  goals: GoalItem[];
  mortgage: MortgageData;
  lifeEvents: LifeEventItem[];
}

export const INITIAL_STATE: WizardState = {
  personal: {
    age: null,
    name: "",
    retirement_age: null,
    dependents: 0,
    risk_profile: "moderate",
    employment_type: "employed",
    has_will: false,
    has_lpa: false,
  },
  income: {
    primary_gross_annual: null,
    partner_gross_annual: 0,
    rental_income_monthly: 0,
    side_income_monthly: 0,
    bonus_annual_expected: 0,
  },
  expenses: {
    housing: { rent_monthly: 0, council_tax_monthly: 0, utilities_monthly: 0, insurance_monthly: 0 },
    transport: { car_payment_monthly: 0, fuel_monthly: 0, public_transport_monthly: 0 },
    living: { groceries_monthly: 0, dining_out_monthly: 0, subscriptions_monthly: 0, clothing_monthly: 0, personal_care_monthly: 0 },
    other: { phone_monthly: 0, gym_monthly: 0, holidays_annual: 0, gifts_annual: 0, miscellaneous_monthly: 0 },
  },
  savings: {
    emergency_fund: 0,
    general_savings: 0,
    isa_balance: 0,
    pension_balance: 0,
    pension_employer_contribution_pct: 0.03,
    pension_personal_contribution_pct: 0.05,
    lisa_balance: 0,
    other_investments: 0,
  },
  debts: [],
  goals: [],
  mortgage: {
    enabled: false,
    target_property_value: 0,
    preferred_deposit_pct: 0.10,
    preferred_term_years: 25,
    joint_application: false,
  },
  lifeEvents: [],
};

export const STEP_LABELS = [
  "Personal",
  "Income",
  "Expenses",
  "Savings",
  "Debts",
  "Goals",
  "Mortgage",
  "Life Events",
  "Review",
] as const;

export const REQUIRED_STEPS = 4;
export const TOTAL_STEPS = STEP_LABELS.length;
