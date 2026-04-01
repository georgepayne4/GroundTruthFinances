# GroundTruth Financial Planning Engine

A modular, advisor-grade financial planning engine that analyses structured financial profiles and generates comprehensive reports with scoring, projections, and actionable recommendations.

## What It Does

GroundTruth takes a YAML financial profile (income, expenses, debts, savings, goals, mortgage plans, and upcoming life events) and runs it through an 11-stage analysis pipeline:

1. **Input validation** — catches data quality issues without blocking analysis
2. **Cashflow analysis** — UK-style tax/NI calculation, surplus/deficit, savings rate
3. **Debt analysis** — per-debt payoff timelines, avalanche/snowball strategies, extra payment scenarios
4. **Goal feasibility** — priority-weighted surplus allocation, inflation-adjusted targets
5. **Investment analysis** — portfolio projections, pension adequacy, income replacement ratio
6. **Mortgage readiness** — borrowing capacity, deposit analysis, affordability stress tests
7. **Life event simulation** — year-by-year financial trajectory with planned events
8. **Financial health scoring** — composite 0–100 score across 7 weighted categories
9. **Advisor insights** — plain-language priorities, risk warnings, and next steps
10. **Report assembly** — structured JSON output

## Quick Start

```bash
# Install dependency
pip install pyyaml

# Run with the included sample profile
python main.py

# Run with a custom profile
python main.py --profile path/to/profile.yaml

# Custom assumptions too
python main.py --profile profile.yaml --assumptions assumptions.yaml
```

The report is saved to `outputs/report.json`.

## Project Structure

```
├── main.py                  # Pipeline entry point
├── config/
│   ├── sample_input.yaml    # Example financial profile (Alex Morgan, age 31)
│   └── assumptions.yaml     # Tax bands, inflation rates, scoring weights, etc.
├── engine/
│   ├── loader.py            # YAML loading and normalisation
│   ├── validator.py         # Advisor validation layer
│   ├── cashflow.py          # Income tax, NI, surplus calculation
│   ├── debt.py              # Repayment strategies and payoff simulation
│   ├── goals.py             # Goal feasibility and surplus allocation
│   ├── investments.py       # Portfolio projections and pension adequacy
│   ├── mortgage.py          # Borrowing capacity and readiness assessment
│   ├── life_events.py       # Multi-year trajectory simulation
│   ├── scoring.py           # Financial health scoring (7 categories)
│   ├── insights.py          # Advisor-style recommendations
│   └── report.py            # Report assembly and JSON output
└── outputs/
    └── report.json          # Generated report (gitignored)
```

## Profile Format

Profiles are YAML files with these sections:

| Section | Description |
|---------|-------------|
| `personal` | Name, age, retirement age, risk profile, salary growth outlook |
| `income` | Primary salary, partner income, side income, investments |
| `expenses` | Housing, transport, living, and other costs (monthly/annual) |
| `debts` | Balance, interest rate, minimum payment, and type for each debt |
| `savings` | Emergency fund, general savings, ISA, pension balances and contributions |
| `goals` | Target amount, deadline, priority, and category for each goal |
| `mortgage` | Target property value, deposit preference, term, joint application |
| `life_events` | Planned income/expense changes by year offset |

See `config/sample_input.yaml` for a complete example.

## Assumptions

All financial assumptions (tax bands, inflation rates, investment returns, scoring weights, mortgage criteria) are centralised in `config/assumptions.yaml` and can be overridden without changing code.

## Requirements

- Python 3.9+
- PyYAML
