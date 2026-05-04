import { useCallback, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { WizardProvider, useWizard } from "./WizardContext";
import { useReport } from "../lib/report-context";
import { buildProfile } from "./lib/wizard-to-profile";
import { getExpenseDefaults } from "./lib/wizard-defaults";
import { REQUIRED_STEPS } from "./lib/wizard-types";
import ProgressBar from "./components/ProgressBar";
import PersonalStep from "./steps/PersonalStep";
import IncomeStep from "./steps/IncomeStep";
import ExpensesStep from "./steps/ExpensesStep";
import SavingsStep from "./steps/SavingsStep";
import DebtsStep from "./steps/DebtsStep";
import GoalsStep from "./steps/GoalsStep";
import MortgageStep from "./steps/MortgageStep";
import LifeEventsStep from "./steps/LifeEventsStep";
import ReviewStep from "./steps/ReviewStep";

const REVIEW_STEP = 8;

function WizardInner() {
  const wizard = useWizard();
  const { analyse, setProfileJson, loading, error } = useReport();
  const navigate = useNavigate();
  const [expenseDefaultsApplied, setExpenseDefaultsApplied] = useState(false);
  // True when the user opened a step via the Review/Summary edit action.
  // While set, Next and Back both return straight to the summary instead of
  // walking through subsequent steps — so a typo fix is one click, not seven.
  const [editingFromSummary, setEditingFromSummary] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  const scrollToTop = () => scrollRef.current?.scrollIntoView({ behavior: "smooth" });

  const returnToSummary = useCallback(() => {
    setEditingFromSummary(false);
    wizard.setCurrentStep(REVIEW_STEP);
    scrollToTop();
  }, [wizard]);

  const goNext = useCallback(() => {
    // Apply expense defaults when moving from Income (1) to Expenses (2)
    if (wizard.currentStep === 1 && !expenseDefaultsApplied && wizard.state.income.primary_gross_annual) {
      const allZero = Object.values(wizard.state.expenses.housing).every((v) => v === 0);
      if (allZero) {
        wizard.updateExpenses(getExpenseDefaults(wizard.state.income.primary_gross_annual));
        setExpenseDefaultsApplied(true);
      }
    }
    // Auto-enable mortgage if property goal was added
    if (wizard.currentStep === 5 && wizard.state.goals.some((g) => g.category === "property") && !wizard.state.mortgage.enabled) {
      wizard.updateMortgage({
        enabled: true,
        target_property_value: wizard.state.goals.find((g) => g.category === "property")?.target_amount
          ? Math.round((wizard.state.income.primary_gross_annual || 50000) * 5)
          : 0,
      });
    }
    if (editingFromSummary) {
      returnToSummary();
      return;
    }
    wizard.setCurrentStep(wizard.currentStep + 1);
    scrollToTop();
  }, [wizard, expenseDefaultsApplied, editingFromSummary, returnToSummary]);

  const goBack = useCallback(() => {
    if (editingFromSummary) {
      returnToSummary();
      return;
    }
    wizard.setCurrentStep(wizard.currentStep - 1);
    scrollToTop();
  }, [wizard, editingFromSummary, returnToSummary]);

  const goTo = useCallback((step: number) => {
    wizard.setCurrentStep(step);
    scrollToTop();
  }, [wizard]);

  const editFromSummary = useCallback((step: number) => {
    setEditingFromSummary(true);
    goTo(step);
  }, [goTo]);

  const handleSubmit = useCallback(async () => {
    const profile = buildProfile(wizard.state);
    setProfileJson(JSON.stringify(profile, null, 2));
    try {
      await analyse(profile);
      wizard.clearSavedDraft();
      navigate("/");
    } catch {
      // error is set in ReportProvider
    }
  }, [wizard, analyse, setProfileJson, navigate]);

  const isOptional = (step: number) => step >= REQUIRED_STEPS && step < 8;

  return (
    <div ref={scrollRef}>
      {/* Resume banner */}
      {wizard.resumable && (
        <div className="mb-4 rounded-lg bg-blue-50 dark:bg-blue-950 border border-blue-200 dark:border-blue-800 px-4 py-3 flex items-center justify-between">
          <span className="text-sm text-blue-800 dark:text-blue-200">
            You have a saved profile from {new Date(wizard.resumable.lastSaved).toLocaleDateString("en-GB")}.
          </span>
          <div className="flex gap-2">
            <button
              type="button"
              onClick={wizard.acceptResume}
              className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-700 transition-colors"
            >
              Resume
            </button>
            <button
              type="button"
              onClick={wizard.reset}
              className="rounded-lg px-4 py-1.5 text-xs font-medium text-blue-700 dark:text-blue-300 hover:bg-blue-100 dark:hover:bg-blue-900 transition-colors"
            >
              Start Fresh
            </button>
          </div>
        </div>
      )}

      <ProgressBar
        currentStep={wizard.currentStep}
        completeness={wizard.completeness}
        onStepClick={goTo}
        visitedSteps={wizard.visitedSteps}
      />

      {editingFromSummary && wizard.currentStep !== REVIEW_STEP && (
        <div className="mb-4 rounded-lg bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 px-4 py-3 flex items-center justify-between">
          <span className="text-sm text-amber-800 dark:text-amber-200">
            Editing from summary — Next or Back will return you to the summary.
          </span>
          <button
            type="button"
            onClick={returnToSummary}
            className="rounded-lg bg-amber-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-amber-700 transition-colors"
          >
            Back to summary
          </button>
        </div>
      )}

      {wizard.currentStep === 0 && (
        <PersonalStep data={wizard.state.personal} onChange={wizard.updatePersonal} onNext={goNext} />
      )}
      {wizard.currentStep === 1 && (
        <IncomeStep data={wizard.state.income} onChange={wizard.updateIncome} onNext={goNext} onBack={goBack} />
      )}
      {wizard.currentStep === 2 && (
        <ExpensesStep data={wizard.state.expenses} onChange={wizard.updateExpenses} onNext={goNext} onBack={goBack} hasDefaults={expenseDefaultsApplied} />
      )}
      {wizard.currentStep === 3 && (
        <SavingsStep data={wizard.state.savings} onChange={wizard.updateSavings} onNext={goNext} onBack={goBack} />
      )}
      {wizard.currentStep === 4 && (
        <DebtsStep data={wizard.state.debts} onChange={wizard.setDebts} onNext={goNext} onBack={goBack} onSkip={goNext} />
      )}
      {wizard.currentStep === 5 && (
        <GoalsStep data={wizard.state.goals} wizardState={wizard.state} onChange={wizard.setGoals} onNext={goNext} onBack={goBack} onSkip={goNext} />
      )}
      {wizard.currentStep === 6 && (
        <MortgageStep data={wizard.state.mortgage} onChange={wizard.updateMortgage} onNext={goNext} onBack={goBack} onSkip={goNext} />
      )}
      {wizard.currentStep === 7 && (
        <LifeEventsStep data={wizard.state.lifeEvents} onChange={wizard.setLifeEvents} onNext={goNext} onBack={goBack} onSkip={goNext} />
      )}
      {wizard.currentStep === REVIEW_STEP && (
        <ReviewStep state={wizard.state} onEdit={editFromSummary} onSubmit={handleSubmit} loading={loading} error={error} />
      )}
    </div>
  );
}

export default function WizardPage() {
  return (
    <WizardProvider>
      <WizardInner />
    </WizardProvider>
  );
}
