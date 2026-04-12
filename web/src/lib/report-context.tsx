import { createContext, useContext, useState, useCallback } from "react";
import type { ReactNode } from "react";
import type { Report } from "./api";
import { analyse as apiAnalyse } from "./api";

const SAMPLE_PROFILE = {
  personal: {
    name: "Dashboard Demo",
    age: 30,
    retirement_age: 67,
    dependents: 0,
    risk_profile: "moderate",
    employment_type: "employed",
  },
  income: { primary_gross_annual: 50000 },
  expenses: {
    housing: { rent_monthly: 1000 },
    transport: { fuel_monthly: 150 },
    living: { groceries_monthly: 400 },
  },
  savings: {
    emergency_fund: 5000,
    pension_balance: 15000,
    pension_personal_contribution_pct: 0.05,
    pension_employer_contribution_pct: 0.03,
    isa_balance: 3000,
  },
  debts: [
    {
      name: "Credit Card",
      type: "credit_card",
      balance: 2000,
      interest_rate: 19.9,
      minimum_payment_monthly: 50,
    },
  ],
  goals: [
    { name: "Emergency Fund", target_amount: 10000, deadline_years: 2, priority: 1, category: "savings" },
    { name: "House Deposit", target_amount: 30000, deadline_years: 5, priority: 2, category: "property" },
  ],
};

interface ReportContextValue {
  report: Report | null;
  loading: boolean;
  error: string | null;
  analyse: (profile: Record<string, unknown>) => Promise<void>;
  profileJson: string;
  setProfileJson: (json: string) => void;
}

const ReportContext = createContext<ReportContextValue | null>(null);

export function ReportProvider({ children }: { children: ReactNode }) {
  const [report, setReport] = useState<Report | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [profileJson, setProfileJson] = useState(JSON.stringify(SAMPLE_PROFILE, null, 2));

  const analyse = useCallback(async (profile: Record<string, unknown>) => {
    setLoading(true);
    setError(null);
    try {
      const result = await apiAnalyse(profile);
      setReport(result.report);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Analysis failed");
    } finally {
      setLoading(false);
    }
  }, []);

  return (
    <ReportContext.Provider value={{ report, loading, error, analyse, profileJson, setProfileJson }}>
      {children}
    </ReportContext.Provider>
  );
}

export function useReport(): ReportContextValue {
  const ctx = useContext(ReportContext);
  if (!ctx) throw new Error("useReport must be used within ReportProvider");
  return ctx;
}
