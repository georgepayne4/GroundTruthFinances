import { createContext, useContext, useState, useCallback, useEffect, useRef } from "react";
import type { ReactNode } from "react";
import type { WizardState, DebtItem, GoalItem, LifeEventItem, MortgageData, PersonalData, IncomeData, ExpensesData, SavingsData } from "./lib/wizard-types";
import { INITIAL_STATE, TOTAL_STEPS } from "./lib/wizard-types";
import { calculateCompleteness } from "./lib/wizard-completeness";
import { saveDraft, loadDraft, clearDraft } from "./lib/wizard-storage";

interface WizardContextValue {
  state: WizardState;
  currentStep: number;
  setCurrentStep: (step: number) => void;
  updatePersonal: (data: Partial<PersonalData>) => void;
  updateIncome: (data: Partial<IncomeData>) => void;
  updateExpenses: (data: ExpensesData) => void;
  updateSavings: (data: Partial<SavingsData>) => void;
  setDebts: (data: DebtItem[]) => void;
  setGoals: (data: GoalItem[]) => void;
  updateMortgage: (data: Partial<MortgageData>) => void;
  setLifeEvents: (data: LifeEventItem[]) => void;
  completeness: number;
  visitedSteps: Set<number>;
  resumable: { lastSaved: string } | null;
  acceptResume: () => void;
  reset: () => void;
  clearSavedDraft: () => void;
}

const WizardCtx = createContext<WizardContextValue | null>(null);

export function WizardProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<WizardState>(INITIAL_STATE);
  const [currentStep, setCurrentStepRaw] = useState(0);
  const [visitedSteps, setVisitedSteps] = useState<Set<number>>(new Set([0]));
  const [resumable, setResumable] = useState<{ state: WizardState; currentStep: number; lastSaved: string } | null>(null);
  const saveTimer = useRef<ReturnType<typeof setTimeout>>(null);

  // Check for saved draft on mount
  useEffect(() => {
    const draft = loadDraft();
    if (draft) setResumable(draft);
  }, []);

  // Debounced save
  useEffect(() => {
    if (saveTimer.current) clearTimeout(saveTimer.current);
    saveTimer.current = setTimeout(() => saveDraft(state, currentStep), 500);
    return () => { if (saveTimer.current) clearTimeout(saveTimer.current); };
  }, [state, currentStep]);

  const setCurrentStep = useCallback((step: number) => {
    if (step >= 0 && step < TOTAL_STEPS) {
      setCurrentStepRaw(step);
      setVisitedSteps((prev) => new Set([...prev, step]));
    }
  }, []);

  const updatePersonal = useCallback((data: Partial<PersonalData>) => {
    setState((prev) => ({ ...prev, personal: { ...prev.personal, ...data } }));
  }, []);

  const updateIncome = useCallback((data: Partial<IncomeData>) => {
    setState((prev) => ({ ...prev, income: { ...prev.income, ...data } }));
  }, []);

  const updateExpenses = useCallback((data: ExpensesData) => {
    setState((prev) => ({ ...prev, expenses: data }));
  }, []);

  const updateSavings = useCallback((data: Partial<SavingsData>) => {
    setState((prev) => ({ ...prev, savings: { ...prev.savings, ...data } }));
  }, []);

  const setDebts = useCallback((data: DebtItem[]) => {
    setState((prev) => ({ ...prev, debts: data }));
  }, []);

  const setGoals = useCallback((data: GoalItem[]) => {
    setState((prev) => ({ ...prev, goals: data }));
  }, []);

  const updateMortgage = useCallback((data: Partial<MortgageData>) => {
    setState((prev) => ({ ...prev, mortgage: { ...prev.mortgage, ...data } }));
  }, []);

  const setLifeEvents = useCallback((data: LifeEventItem[]) => {
    setState((prev) => ({ ...prev, lifeEvents: data }));
  }, []);

  const acceptResume = useCallback(() => {
    if (resumable) {
      setState(resumable.state);
      setCurrentStepRaw(resumable.currentStep);
      // Mark all steps up to and including the saved step as visited
      const visited = new Set<number>();
      for (let i = 0; i <= resumable.currentStep; i++) visited.add(i);
      setVisitedSteps(visited);
    }
    setResumable(null);
  }, [resumable]);

  const reset = useCallback(() => {
    setState(INITIAL_STATE);
    setCurrentStepRaw(0);
    setVisitedSteps(new Set([0]));
    setResumable(null);
    clearDraft();
  }, []);

  const clearSavedDraft = useCallback(() => {
    clearDraft();
  }, []);

  const completeness = calculateCompleteness(state);

  return (
    <WizardCtx.Provider
      value={{
        state,
        currentStep,
        setCurrentStep,
        updatePersonal,
        updateIncome,
        updateExpenses,
        updateSavings,
        setDebts,
        setGoals,
        updateMortgage,
        setLifeEvents,
        completeness,
        visitedSteps,
        resumable,
        acceptResume,
        reset,
        clearSavedDraft,
      }}
    >
      {children}
    </WizardCtx.Provider>
  );
}

export function useWizard(): WizardContextValue {
  const ctx = useContext(WizardCtx);
  if (!ctx) throw new Error("useWizard must be used within WizardProvider");
  return ctx;
}
