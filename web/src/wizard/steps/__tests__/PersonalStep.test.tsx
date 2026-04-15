import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PersonalStep from "../PersonalStep";
import type { PersonalData } from "../../lib/wizard-types";

function makeData(overrides: Partial<PersonalData> = {}): PersonalData {
  return {
    age: null,
    name: "",
    retirement_age: null,
    dependents: 0,
    risk_profile: "moderate",
    employment_type: "employed",
    has_will: false,
    has_lpa: false,
    ...overrides,
  };
}

describe("PersonalStep", () => {
  it("renders heading and age input", () => {
    render(<PersonalStep data={makeData()} onChange={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByRole("heading", { name: /about you/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/^age/i)).toBeInTheDocument();
  });

  it("blocks Next when age is missing", () => {
    render(<PersonalStep data={makeData()} onChange={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("shows an inline error when age is out of range", () => {
    render(<PersonalStep data={makeData({ age: 10 })} onChange={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent(/between 16 and 100/i);
    expect(screen.getByRole("button", { name: /next/i })).toBeDisabled();
  });

  it("enables Next when age is valid", () => {
    render(<PersonalStep data={makeData({ age: 30 })} onChange={vi.fn()} onNext={vi.fn()} />);
    expect(screen.getByRole("button", { name: /next/i })).not.toBeDisabled();
  });

  it("calls onChange when age input is typed", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<PersonalStep data={makeData()} onChange={onChange} onNext={vi.fn()} />);
    await user.type(screen.getByLabelText(/^age/i), "3");
    expect(onChange).toHaveBeenCalledWith({ age: 3 });
  });
});
