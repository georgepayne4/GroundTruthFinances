# Profile Guide

This is the reference for every field in a GroundTruth profile. Profiles are YAML (preferred) or JSON. See `config/sample_input.yaml` in the repository for a full working example.

The wizard generates valid profiles automatically. Use this guide when hand-editing profiles or calling the API directly.

## Top-level sections

| Section | Required? | Purpose |
|---------|-----------|---------|
| `personal` | Yes | Age, retirement, risk, employment, tax region |
| `income` | Yes | All sources of gross income |
| `expenses` | Yes | Monthly and annual spending by category |
| `debts` | Optional | List of outstanding liabilities |
| `savings` | Yes | Emergency fund, ISA, LISA, pension, fees |
| `accounts` | Optional | Per-account balance tracking (overrides `savings`) |
| `goals` | Optional | List of targets with deadlines and priorities |
| `mortgage` | Optional | Mortgage intent and property target |
| `life_events` | Optional | Scheduled future changes |
| `insurance` | Optional | Current coverage levels |
| `partner` | Optional | Partner's financial details for joint planning |

## `personal`

```yaml
personal:
  name: "Alex Morgan"
  age: 31
  retirement_age: 65
  dependents: 0
  risk_profile: "moderate"         # conservative | moderate | aggressive | very_aggressive
  salary_growth_outlook: "average" # low | average | high
  employment_type: "employed"      # employed | self_employed | contractor | mixed
  tax_region: "england"            # england | scotland
  has_will: false
  has_lpa: false
```

- `risk_profile` drives expected return and volatility from `assumptions.yaml`. Pick honestly — a moderate investor claiming aggressive returns is just a moderate investor with an optimism problem.
- `tax_region` controls whether English or Scottish income tax bands apply.
- `has_will` / `has_lpa` affect the estate scoring category.

## `income`

```yaml
income:
  primary_gross_annual: 58000
  partner_gross_annual: 0
  rental_income_monthly: 0
  side_income_monthly: 350
  investment_income_annual: 200
  bonus_annual_low: 0
  bonus_annual_expected: 0
  bonus_annual_high: 0
```

All figures are **gross** (before tax and NI). Bonuses use three-point estimates — GroundTruth uses `expected` in the central projection and the low/high range in scenarios.

## `expenses`

Nested by category. Monthly fields default to monthly values; `_annual` suffix for annual.

```yaml
expenses:
  housing:
    rent_monthly: 1100
    council_tax_monthly: 145
    utilities_monthly: 160
    insurance_monthly: 30
  transport:
    car_payment_monthly: 0
    fuel_monthly: 80
    public_transport_monthly: 140
  living:
    groceries_monthly: 350
    dining_out_monthly: 120
    subscriptions_monthly: 65
    clothing_monthly: 50
    personal_care_monthly: 30
  other:
    phone_monthly: 35
    gym_monthly: 40
    holidays_annual: 2000
    gifts_annual: 500
    miscellaneous_monthly: 100
```

**Tip:** The single biggest source of profile error is under-reporting discretionary spending. If your actual bank statement says £500/month on dining out, enter £500 — not the £300 you'd prefer to spend. GroundTruth's job is to show reality, not flatter it.

## `debts`

A list of liabilities. Each entry:

```yaml
- name: "Credit Card"
  type: "credit_card"               # see list below
  balance: 3200
  interest_rate: 0.219              # 21.9% APR as a decimal
  minimum_payment_monthly: 95
  # Credit card extras (optional):
  statement_balance: 3200
  current_balance: 3200
  credit_limit: 5000
  payment_behaviour: "minimum"      # full | minimum | fixed_amount
  monthly_spend: 200
```

### Debt types

| Type | Treatment |
|------|-----------|
| `credit_card` | Revolver logic — utilisation, payment behaviour |
| `personal_loan` | Fixed-term amortising |
| `auto_loan` | Fixed-term amortising |
| `student_loan` | Plan 2 — 30yr write-off, 9% above threshold |
| `student_loan_postgrad` | Plan 3 — 30yr write-off, 6% above £21k |
| `student_loan_plan1` | Plan 1 — 25yr write-off |
| `mortgage` | Treated separately from unsecured debt |
| `other` | Generic fixed-rate |

## `savings`

```yaml
savings:
  emergency_fund: 4200
  emergency_fund_type: "cash"       # cash | easy_access | notice | fixed
  general_savings: 2800
  isa_balance: 6500
  lisa_balance: 0
  pension_balance: 18000
  pension_employer_contribution_pct: 0.05
  pension_personal_contribution_pct: 0.05
  pension_employer_match_cap_pct: 0.05
  other_investments: 0
  investment_fees:
    isa_platform_fee: 0.0015
    isa_fund_ocf: 0.0022
    pension_platform_fee: 0.003
    pension_fund_ocf: 0.002
  isa_contributions_this_year: 0
  lisa_contributions_this_year: 0
```

Contribution percentages are **of gross salary**. The employer match cap is the employer's maximum — if you contribute 8% but employer caps at 5%, employer adds 5% not 8%.

## `accounts` (optional)

When present, accounts override the `savings` fields they map to — becoming the single source of truth.

```yaml
accounts:
  - name: "Chase Easy Access Saver"
    type: "easy_access"
    balance: 4200
    maps_to: "emergency_fund"
  - name: "Trading 212 ISA"
    type: "stocks_and_shares_isa"
    balance: 6500
  - name: "Workplace Pension - Aviva"
    type: "pension"
    balance: 18000
```

Mapping rules:

- `current` / `easy_access` / `savings` → `general_savings` (unless `maps_to` overrides)
- `isa` / `stocks_and_shares_isa` / `cash_isa` → `isa_balance`
- `lisa` → `lisa_balance`
- `pension` → `pension_balance`
- `investment` → `other_investments`

## `goals`

```yaml
goals:
  - name: "Build 6-month emergency fund"
    target_amount: 14000
    deadline_years: 2
    priority: "high"                # high | medium | low
    category: "safety_net"
```

### Goal categories

| Category | Default treatment |
|----------|-------------------|
| `safety_net` | Cash/easy access, no market risk |
| `property` | LISA bonus eligible if first home under £450k |
| `retirement` | Pension/LISA, long horizon |
| `education` | ISA, medium horizon |
| `lifestyle` | GIA/ISA depending on horizon |
| `debt_payoff` | Not a savings goal — consumed by debt module |

## `mortgage`

```yaml
mortgage:
  target_property_value: 280000
  preferred_deposit_pct: 0.15
  preferred_term_years: 30
  joint_application: false
  first_time_buyer: true
  shared_ownership: false
  share_pct: 1.0
```

`target_property_value` is the purchase price, not the mortgage amount. GroundTruth computes the mortgage as `target × (1 - preferred_deposit_pct)`.

## `life_events`

A list of scheduled future changes.

```yaml
life_events:
  - year_offset: 1
    description: "Salary increase after promotion"
    income_change_annual: 4000
  - year_offset: 4
    description: "Purchase first home"
    one_off_expense: 45000
    monthly_expense_change: 200
  - year_offset: 5
    description: "First child"
    monthly_expense_change: 800
  - year_offset: 6
    description: "Childcare costs"
    monthly_expense_change: 2000
    type: "childcare"
```

### Event fields

- `year_offset` — years from today (1 = next year)
- `income_change_annual` — permanent change to annual income
- `monthly_expense_change` — permanent change to monthly expenses
- `one_off_income` — single-year income boost (inheritance, bonus)
- `one_off_expense` — single-year expense (house deposit, wedding)
- `type` — semantic tag (e.g., `childcare`, `retirement`, `sabbatical`)

Changes are permanent from `year_offset` onward unless followed by an opposite event (e.g., retirement zeroing income).

## `insurance` (optional)

```yaml
insurance:
  life_cover_amount: 300000
  income_protection_monthly: 2500
  critical_illness_amount: 100000
```

If omitted, GroundTruth assumes zero coverage and flags the gap.

## `partner` (optional)

Partner details for joint planning. Mirrors the top-level structure but scoped to the partner.

```yaml
partner:
  age: 30
  income:
    primary_gross_annual: 45000
  savings:
    pension_balance: 12000
    pension_employer_contribution_pct: 0.04
    pension_personal_contribution_pct: 0.04
```

## Validation

Before analysis, the validator checks every field. Three severity levels:

- **Error** — blocks analysis (e.g., negative income, missing required section)
- **Warning** — analysis runs but results may be unreliable (e.g., expenses > income)
- **Info** — hint or suggestion (e.g., "no emergency fund set")

Fix errors, triage warnings, ignore info flags unless they're relevant.

## Backward compatibility

Any new field added to GroundTruth will be **optional with a sensible default** — old profiles keep working without edits. This is a project invariant.
