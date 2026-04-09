# GroundTruth Financial Planning Platform

A comprehensive UK financial planning platform combining an advisor-grade calculation engine, REST API, and React dashboard. Analyses income, tax, debt, pensions, mortgages, insurance, and estate planning — then scores your financial health and tells you exactly what to do next.

## What It Does

GroundTruth runs a 16-stage analysis pipeline across your complete financial picture:

| Stage | What It Calculates |
|-------|-------------------|
| Validation | Data quality checks with severity-graded flags |
| Cashflow | UK tax/NI (England + Scotland), surplus/deficit, savings rate, spending benchmarks |
| Debt | Payoff timelines, avalanche/snowball strategies, student loan write-off intelligence, credit card utilisation |
| Goals | Priority-weighted surplus allocation, inflation-adjusted targets, LISA bonus projections |
| Investments | Portfolio projections, pension adequacy, employer match optimisation, fee drag, glide path, drawdown vs annuity |
| Mortgage | Borrowing capacity, LTV bands, product comparison, overpayment modelling, shared ownership, stress tests |
| Insurance | Life/income protection/critical illness gaps, pension-cross-referenced coverage |
| Life Events | Year-by-year simulation with milestones, child costs, equity tracking |
| Scoring | Composite 0-100 score across 7 weighted categories with grade (A+ to F) |
| Scenarios | Job loss runway, interest rate shock, market drawdown, inflation spike |
| Sensitivity | Parameter sweeps across income, rates, contributions, property prices |
| Estate | IHT liability, nil-rate bands, spousal exemption, gifting strategy |
| Insights | Surplus deployment plan, tax optimisation, risk warnings, positive reinforcements |
| Narrative | Full Markdown advisor letter generated from structured data |

## Platform Components

### Engine (Python)
The core calculation engine — 18 pure-function modules, no shared state. Processes a YAML/JSON profile and returns a comprehensive analysis report.

### REST API (FastAPI)
Full-featured API with:
- `POST /api/v1/analyse` — Run complete analysis
- `POST /api/v1/validate` — Validate profile structure
- `GET /api/v1/assumptions` — Current financial assumptions
- `GET /api/v1/history` — Historical run tracking
- `POST /api/v1/whatif` — Interactive what-if scenarios
- `POST /api/v1/compare` — Side-by-side profile comparison
- `POST /api/v1/compare/branch` — Scenario branching
- `POST /api/v1/cashflow/drift` — Planned vs actual spending
- `POST /api/v1/export/{id}/{format}` — CSV, XLSX, PDF exports
- WebSocket `/ws/analyse` — Real-time streaming analysis

Per-user API key authentication, audit logging, rate limiting.

### Web Dashboard (React)
React 18 + TypeScript + TailwindCSS dashboard with:
- Financial health score gauge with grade
- Monthly cashflow breakdown chart
- Category score breakdown with progress bars
- Priority action recommendations
- Profile JSON editor with live analysis
- WCAG 2.1 AA accessible, colour-blind safe palette

### Open Banking (TrueLayer)
Connect UK bank accounts for:
- Automatic transaction sync and categorisation
- Income verification from salary credits
- Planned vs actual spending drift detection
- Expense auto-population from real spending data

### Bank CSV Import
Offline alternative to Open Banking — import CSV exports from Monzo, Starling, Barclays, HSBC, Nationwide, Lloyds, NatWest.

## Quick Start

### CLI Mode

```bash
# Install dependencies
pip install -r requirements.txt

# Run with the included sample profile
python main.py

# Run with verbose logging
python main.py --verbose

# Import a bank CSV
python main.py --bank-csv path/to/statement.csv
```

### API Mode

```bash
# Install dependencies
pip install -r requirements.txt

# Start the API server
uvicorn api.main:app --reload

# API docs available at http://localhost:8000/docs
```

### Web Dashboard

```bash
cd web
npm install
npm run dev
# Dashboard at http://localhost:5173 (proxies API to localhost:8000)
```

### Development

```bash
# Run tests (504 tests)
python -m pytest --tb=short -q

# Lint
ruff check .

# Run with coverage
python -m pytest --cov=engine

# Full check (lint + test)
make check
```

## Project Structure

```
main.py                          CLI entry point
config/
  sample_input.yaml              Example financial profile
  assumptions.yaml               Tax bands, rates, weights (HMRC 2025/26, 315 lines)
  category_rules.yaml            Bank transaction categorisation rules
engine/
  pipeline.py                    Shared 16-stage pipeline orchestration
  pipeline_streaming.py          Generator-based streaming pipeline
  cashflow.py                    Income tax, NI, surplus, benchmarks
  tax.py                         UK tax calculations (income, NI, CGT, dividends, pension)
  debt.py                        Repayment strategies, write-off intelligence
  goals.py                       Goal feasibility and surplus allocation
  investments.py                 Portfolio projections, pension adequacy, fees, glide path
  mortgage.py                    Borrowing capacity, product comparison, overpayment
  insurance.py                   Insurance gap assessment
  life_events.py                 Multi-year trajectory simulation
  scoring.py                     Financial health scoring (7 categories)
  scenarios.py                   Stress scenario modelling
  sensitivity.py                 Parameter sensitivity analysis
  estate.py                      IHT and estate planning
  insights.py                    Advisor-style recommendations
  narrative.py                   Markdown report generation
  report.py                      Report assembly and JSON output
  import_csv.py                  Bank CSV parser and categoriser
  history.py                     Run history and diffing
  assumption_updater.py          Auto-update from HMRC/BoE/ONS APIs
  providers.py                   Account provider abstraction (CSV, Open Banking)
  loader.py                      YAML loading and normalisation
  validator.py                   Input validation (severity-graded flags)
  schemas.py                     Pydantic validation for assumptions.yaml
  types.py                       TypedDict definitions
  exceptions.py                  Custom exception hierarchy
  utils.py                       Shared utilities
api/
  main.py                        FastAPI application
  models.py                      Pydantic request/response models
  dependencies.py                Auth, rate limiting, dependency injection
  exports.py                     CSV/XLSX/PDF report generation
  websocket.py                   WebSocket streaming endpoint
  whatif.py                      What-If explorer
  comparison.py                  Profile comparison and branching
  cashflow_actual.py             Planned vs actual drift detection
  database/
    models.py                    SQLAlchemy ORM models
    session.py                   Database session management
    crud.py                      CRUD operations
  banking/
    router.py                    Open Banking API endpoints (11 routes)
    truelayer.py                 TrueLayer API client
    encryption.py                Fernet token encryption
    sync.py                      Account and transaction sync
    crud.py                      Banking CRUD operations
    income.py                    Income verification
    expenses.py                  Expense summarisation
  notifications/
    router.py                    Notification API endpoints
    triggers.py                  Score change, goal deadline, tax year triggers
    channels.py                  In-app, email, webhook delivery
    crud.py                      Notification CRUD
web/
  src/
    App.tsx                      React application root
    lib/api.ts                   Typed API client
    components/
      Dashboard.tsx              Main dashboard with profile editor
      ScoreGauge.tsx             SVG score gauge with grade
      MetricCard.tsx             Key metric display card
      CashflowBar.tsx            Recharts cashflow bar chart
      CategoryScores.tsx         Score breakdown with progress bars
      PriorityActions.tsx        Priority action list
tests/
  conftest.py                    Shared fixtures (22 test files, 504 tests)
```

## Profile Format

Profiles are YAML or JSON with these sections:

| Section | Description |
|---------|-------------|
| `personal` | Age, retirement age, risk profile, employment type, tax region |
| `income` | Primary salary, partner income, side income, bonuses, rental, dividends |
| `expenses` | Housing, transport, living costs (monthly/annual) |
| `debts` | Balance, rate, type; credit cards with utilisation and payment behaviour |
| `savings` | Emergency fund, ISA, LISA, pension balances, contribution rates, fees |
| `accounts` | Multi-account balance tracking (overrides savings fields) |
| `goals` | Target amount, deadline, priority, category |
| `mortgage` | Target property, deposit, term, joint application, deposit sources |
| `life_events` | Planned changes by year offset (income, expenses, milestones) |
| `insurance` | Current coverage (life, income protection, critical illness) |
| `partner` | Partner financial details for joint planning |

See `config/sample_input.yaml` for a complete example.

## Assumptions

All financial parameters are centralised in `config/assumptions.yaml` (315 lines) with source comments:
- Tax bands, NI thresholds, personal allowance (HMRC 2025/26)
- Scottish income tax bands (6 rates)
- Investment returns by risk profile, inflation rates
- Mortgage products, LTV tiers, stamp duty bands
- State pension, pension annual allowance with taper
- Scoring weights, insurance cost estimates, child costs by age
- Student loan plans (2, 3, postgrad), ISA/LISA limits

Auto-updated from HMRC, BoE, and ONS APIs via `engine/assumption_updater.py`.

## Requirements

- Python 3.10+
- Node.js 18+ (for web dashboard)
- See `requirements.txt` for Python dependencies
- See `web/package.json` for frontend dependencies

## Roadmap

See `roadmap.md` for the forward plan. Current status:
- **v5 (Engine Foundation):** Complete
- **v6 (Web + Open Banking):** Complete
- **v7 (Production Hardening):** Next — tech debt, integration tests, security, Docker
- **v8 (Intelligence Engine):** Monte Carlo, lifetime cashflow, tax-optimal withdrawal
- **v9 (Consumer Launch):** Full UI, auth, onboarding, pricing, deployment

## License

Private. Not yet open source.
