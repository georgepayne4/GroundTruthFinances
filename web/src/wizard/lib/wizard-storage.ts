import type { WizardState } from "./wizard-types";

const STORAGE_KEY = "groundtruth_wizard_draft";
const MAX_AGE_DAYS = 30;

interface WizardDraft {
  version: 1;
  state: WizardState;
  currentStep: number;
  lastSaved: string;
}

export function saveDraft(state: WizardState, currentStep: number): void {
  try {
    const draft: WizardDraft = {
      version: 1,
      state,
      currentStep,
      lastSaved: new Date().toISOString(),
    };
    localStorage.setItem(STORAGE_KEY, JSON.stringify(draft));
  } catch {
    // localStorage full or unavailable — silently ignore
  }
}

export function loadDraft(): { state: WizardState; currentStep: number; lastSaved: string } | null {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;

    const draft: WizardDraft = JSON.parse(raw);
    if (draft.version !== 1) return null;

    const age = Date.now() - new Date(draft.lastSaved).getTime();
    if (age > MAX_AGE_DAYS * 24 * 60 * 60 * 1000) {
      clearDraft();
      return null;
    }

    return { state: draft.state, currentStep: draft.currentStep, lastSaved: draft.lastSaved };
  } catch {
    clearDraft();
    return null;
  }
}

export function clearDraft(): void {
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}
