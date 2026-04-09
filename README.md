# GroundTruth Financial Planning Engine

A modular, advisor-grade UK financial planning engine. Analyses structured financial profiles and generates comprehensive reports with scoring, projections, and actionable recommendations.

## What It Does

GroundTruth takes a YAML financial profile (income, expenses, debts, savings, goals, mortgage plans, and life events) and runs it through a 15-stage analysis pipeline:

1. **Input validation** — catches data quality issues with severity-graded flags
2. **Cashflow analysis** — UK tax/NI calculation (including Scottish bands), surplus/deficit, savings rate, spending benchmarks
3. **Debt analysis** — per-debt payoff timelines, avalanche/snowball strategies, student loan write-off intelligence, credit card utilisation tracking
4. **Goal feasibility** — priority-weighted surplus allocation, inflation-adjusted targets, prerequisite checks
5. **Investment analysis** — portfolio projections, pension adequacy, employer match optimisation, fee drag analysis, salary sacrifice modelling
6. **Mortgage readiness** — borrowing capacity, deposit analysis, product comparison, shared ownership, stress tests
7. **Insurance gap assessment** — pension-cross-referenced coverage analysis
8. **Life event simulation** — year-by-year trajectory with milestones and childcare tax relief
9. **Financial health scoring** — composite 0-100 score across 7 weighted categories
10. **Stress scenarios** — job loss runway, interest rate shock, market drawdown
11. **Estate analysis** — IHT liability, nil-rate bands, planning actions
12. **Sensitivity analysis** — parameter sweeps across income, rates, and contributions
13. **Advisor insights** — surplus deployment plan, tax optimisation, risk warnings, review schedule
14. **Narrative report** — Markdown advisor letter generated from structured data
15. **Report assembly** — structured JSON + Markdown output with optional history recording

### Bank Data Integration (v5.2)

When provided with a bank statement CSV, the engine additionally:

- **Auto-categorises** transactions using keyword matching with confidence scoring
- **Detects subscriptions** with price drift alerting
- **Identifies direct debits and standing orders** as committed expenses
- **Verifies declared income** against observed salary credits
- **Generates expense micro-insights** with per-category analysis and monthly trends
- **Merges bank-derived data** into the profile before running the full pipeline

### Run History (v5.2)

Each engine run is optionally recorded in a local SQLite database. You can list past runs, diff any two snapshots, and track score progression over time.

## Quick Start

```bash
# Install dependencies
pip install pyyaml pydantic

# Run with the included sample profile
python main.py

# Run with a custom profile
python main.py --profile path/to/profile.yaml

# Verbose logging to console
python main.py --verbose
```

### Bank CSV Import

```bash
# Preview a bank CSV (prints a YAML expenses block)
python main.py --import-csv path/to/statement.csv

# Merge bank CSV into profile and run full pipeline
python main.py --bank-csv path/to/statement.csv

# Override profile expenses with bank-derived values
python main.py --bank-csv statement.csv --bank-csv-override
```

Supported banks: Monzo, Starling, Barclays, HSBC, Nationwide, Lloyds, NatWest.

### Run History

```bash
# List recent runs
python main.py --history

# Diff the two most recent runs
python main.py --diff

# Diff specific runs by ID
python main.py --diff 3 7

# Skip history recording for this run
python main.py --no-history
```

## Output

Reports are saved to `outputs/`:
- `report.json` — structured JSON with all analysis results
- `report.md` — narrative advisor letter in Markdown
- `history.db` — SQLite run history (auto-created, gitignored)
- `engine.log` — debug log

## Project Structure

```
main.py                          Pipeline entry point and CLI
config/
  sample_input.yaml              Example financial profile (Alex Morgan)
  assumptions.yaml               Tax bands, rates, scoring weights (HMRC 2025/26)
  category_rules.yaml            Bank transaction categorisation keywords
engine/
  loader.py                      YAML loading, normalisation, bank data merging
  validator.py                   Advisor validation layer (severity-graded flags)
  cashflow.py                    Income tax, NI, surplus, benchmarks
  debt.py                        Repayment strategies, write-off intelligence
  goals.py                       Goal feasibility and surplus allocation
  investments.py                 Portfolio projections, pension adequacy
  mortgage.py                    Borrowing capacity, product comparison
  insurance.py                   Insurance gap assessment
  life_events.py                 Multi-year trajectory simulation
  scoring.py                     Financial health scoring (7 categories)
  scenarios.py                   Stress scenario modelling
  estate.py                      IHT and estate planning
  sensitivity.py                 Parameter sensitivity analysis
  insights.py                    Advisor-style recommendations and insights
  narrative.py                   Markdown report generation
  report.py                      Report assembly and JSON output
  import_csv.py                  Bank CSV parser, categoriser, subscription detector
  history.py                     SQLite-backed run history and diffing
  tax.py                         UK income tax and NI calculations
  schemas.py                     Pydantic validation for assumptions.yaml
  types.py                       TypedDict definitions for module results
  exceptions.py                  Custom exception hierarchy
  utils.py                       Shared utilities
tests/
  conftest.py                    Shared fixtures
  test_cashflow.py               Cashflow analysis tests
  test_debt.py                   Debt analysis and credit card model tests
  test_expense_insights.py       Expense micro-insights and trend detection tests
  test_history.py                Run history and diffing tests
  test_import_csv.py             CSV parsing, subscriptions, income verification tests
  test_integration.py            End-to-end pipeline test
  test_investments.py            Investment analysis tests
  test_loader.py                 Account aggregation and normalisation tests
  test_scoring.py                Scoring tests
  test_tax.py                    UK tax calculation tests
  test_validator.py              Validation and credit utilisation tests
```

## Profile Format

Profiles are YAML files with these sections:

| Section | Description |
|---------|-------------|
| `personal` | Name, age, retirement age, risk profile, employment type |
| `income` | Primary salary, partner income, side income, bonuses |
| `expenses` | Housing, transport, living, and other costs (monthly/annual) |
| `debts` | Balance, rate, minimum payment, type; credit cards with utilisation fields |
| `savings` | Emergency fund, general, ISA, LISA, pension balances and contributions |
| `accounts` | Multi-account balance tracking (optional, overrides savings fields) |
| `goals` | Target amount, deadline, priority, category for each goal |
| `mortgage` | Target property value, deposit preference, term |
| `life_events` | Planned income/expense changes by year offset |

See `config/sample_input.yaml` for a complete example.

## Assumptions

All financial assumptions (tax bands, NI thresholds, inflation rates, investment returns, scoring weights, mortgage criteria) are centralised in `config/assumptions.yaml` with source comments (e.g., `# HMRC 2025/26`). Override without changing code.

Validated at load time via Pydantic schemas (`engine/schemas.py`).

## Testing

```bash
# Run full suite (293 tests)
python -m pytest

# Run with coverage
python -m pytest --cov=engine

# Run a specific test file
python -m pytest tests/test_history.py -v
```

## Requirements

- Python 3.10+
- PyYAML
- Pydantic 2.0+
- pytest (dev)
- ruff (dev)
