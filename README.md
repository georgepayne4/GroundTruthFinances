# GroundTruth Financial Planning Platform

A comprehensive UK financial planning platform combining an advisor-grade calculation engine, REST API, and React dashboard. Analyses income, tax, debt, pensions, mortgages, insurance, and estate planning — then scores your financial health and tells you exactly what to do next.

## What GroundTruth Is / Is Not

GroundTruth is an **information service** that provides computational analysis of financial data you supply. It is **not** a regulated financial adviser and is not authorised by the FCA to give personal recommendations. Outputs are educational — they surface trade-offs, project scenarios, and flag risks, but they do not constitute advice. For regulated advice, consult a qualified IFA. See the Terms of Service and Privacy Policy pages in the app for full details.

## What It Does

GroundTruth runs a multi-stage analysis pipeline across your complete financial picture:

| Stage | What It Calculates |
|-------|-------------------|
| Validation | Data quality checks with severity-graded flags |
| Cashflow | UK tax/NI (England + Scotland), surplus/deficit, savings rate, spending benchmarks |
| Debt | Payoff timelines, avalanche/snowball strategies, student loan write-off intelligence, credit card utilisation |
| Goals | Priority-weighted surplus allocation, inflation-adjusted targets, LISA bonus projections |
| Investments | Portfolio projections, pension adequacy, employer match optimisation, fee drag, glide path, drawdown vs annuity |
| Monte Carlo | GBM investment simulation with percentile bands and pension probability analysis |
| Lifetime Cashflow | Year-by-year projection across accumulation, pre-retirement, early retirement, and late retirement phases |
| Withdrawal | Tax-optimal drawdown sequencing (ISA/GIA/pension), PCLS timing, state pension deferral analysis |
| Risk Profiling | Per-goal risk capacity/need assessment with mismatch detection |
| Mortgage | Borrowing capacity, LTV bands, product comparison, overpayment modelling, shared ownership, stress tests |
| Insurance | Life/income protection/critical illness gaps, pension-cross-referenced coverage |
| Life Events | Year-by-year simulation with milestones, child costs, equity tracking |
| Scoring | Composite 0-100 score across 7 weighted categories with grade (A+ to F) |
| Scenarios | Job loss runway, interest rate shock, market drawdown, compound scenario trees with probability-weighted outcomes |
| Sensitivity | Parameter sweeps across income, rates, contributions, property prices |
| Estate | IHT liability, nil-rate bands, RNRB taper, spousal exemption, gift strategies, taper relief, charitable rate |
| Insights | Surplus deployment plan, tax optimisation, risk warnings, positive reinforcements |
| Narrative | Full Markdown advisor letter generated from structured data |

## Platform Components

### Engine (Python)
The core calculation engine — 22 pure-function modules, no shared state. Processes a YAML/JSON profile and returns a comprehensive analysis report. 697 tests across 29 test files.

### REST API (FastAPI)
Full-featured API with:
- `POST /api/v1/analyse` — Run complete analysis
- `POST /api/v1/validate` — Validate profile structure
- `GET /api/v1/assumptions` — Current financial assumptions with staleness status
- `GET /api/v1/assumptions/status` — Assumption freshness check
- `POST /api/v1/assumptions/diff` — Dry-run assumption comparison
- `GET /api/v1/history` — Historical run tracking with cursor-based pagination
- `GET /api/v1/health` — Health check endpoint
- `POST /api/v1/whatif` — Interactive what-if scenarios
- `POST /api/v1/compare` — Side-by-side profile comparison
- `POST /api/v1/compare/branch` — Scenario branching
- `POST /api/v1/sensitivity` — Parameter sensitivity analysis
- `POST /api/v1/scenarios` — Stress scenario modelling
- `POST /api/v1/cashflow/drift` — Planned vs actual spending
- `POST /api/v1/export/{id}/{format}` — CSV, XLSX, PDF exports
- WebSocket `/ws/analyse` — Real-time streaming analysis

- `DELETE /api/v1/account` — GDPR account erasure (wipes PII, cascades owned data)
- `GET /api/v1/account/export` — GDPR right to access (full JSON export of all user data)

Dual authentication: Clerk session JWT (primary, for web users) or per-user API key (fallback, for dev/scripts). Audit logging, rate limiting, HTTPS enforcement, request size limits.

### Web Dashboard (React)
React 19 + TypeScript + TailwindCSS 4 multi-page dashboard with:
- **Home** — Financial health score gauge, monthly surplus, net worth trend, priority actions
- **Cashflow** — Income/expense waterfall, category breakdown, spending benchmarks
- **Debt** — Payoff timeline, avalanche order, student loan intelligence, credit utilisation
- **Goals** — Progress bars with feasibility status, what-would-it-take analysis
- **Investments** — Portfolio allocation, pension projection, fee comparison
- **Mortgage** — Readiness checklist, LTV band explorer, overpayment scenarios
- **Life Events** — Timeline with milestones, year-by-year projection with net worth trajectory
- **Scenarios** — Compound scenario tree visualisation, stress test results
- **Settings** — Profile JSON editor with live analysis (power user mode)
- **Guided Onboarding Wizard** — 9-step progressive profile creation with smart defaults, template goals, completeness scoring, and localStorage save/resume
- **Authentication (Clerk)** — Google + email/password sign-in, sign-up, user button, protected routes, profile page with GDPR data export + account deletion
- **Legal pages** — Terms of Service, Privacy Policy (GDPR-compliant, FCA positioning), persistent disclaimer banner, footer with regulatory classification
- Sidebar navigation with active section highlighting
- Dark mode support
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

### Docker

```bash
docker-compose up --build
# API at localhost:8000, dashboard at localhost:5173
```

### Development

```bash
# Run tests (697 tests)
python -m pytest --tb=short -q

# Lint
ruff check .

# TypeScript check
cd web && npx tsc --noEmit

# Run with coverage
python -m pytest --cov=engine
```

## Project Structure

```
main.py                          CLI entry point
config/
  sample_input.yaml              Example financial profile
  assumptions.yaml               Tax bands, rates, weights (HMRC 2025/26, 419 lines)
  category_rules.yaml            Bank transaction categorisation rules
engine/
  pipeline.py                    Shared pipeline orchestration
  pipeline_streaming.py          Generator-based streaming pipeline
  cashflow.py                    Income tax, NI, surplus, benchmarks
  tax.py                         UK tax calculations (income, NI, CGT, dividends, pension)
  debt.py                        Repayment strategies, write-off intelligence
  goals.py                       Goal feasibility and surplus allocation
  investments.py                 Portfolio projections, pension adequacy, fees, glide path
  monte_carlo.py                 GBM investment simulation with confidence bands
  lifetime_cashflow.py           Multi-phase year-by-year cashflow projection
  withdrawal.py                  Tax-optimal drawdown sequencing
  risk_profiling.py              Goal-specific risk capacity/need assessment
  mortgage.py                    Borrowing capacity, product comparison, overpayment
  insurance.py                   Insurance gap assessment
  life_events.py                 Multi-year trajectory simulation
  scoring.py                     Financial health scoring (7 categories)
  scenarios.py                   Stress scenarios and compound scenario trees
  sensitivity.py                 Parameter sensitivity analysis
  estate.py                      IHT, gift strategies, taper relief, RNRB
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
  dependencies.py                Dual auth (Clerk + API key), rate limiting, DI
  clerk_auth.py                  Clerk JWT verification (JWKS, RS256)
  exports.py                     CSV/XLSX/PDF report generation
  websocket.py                   WebSocket streaming endpoint (authenticated)
  whatif.py                      What-If explorer
  comparison.py                  Profile comparison and branching
  cashflow_actual.py             Planned vs actual drift detection
  database/                      SQLAlchemy ORM, sessions, CRUD
  banking/                       Open Banking (TrueLayer) integration
  notifications/                 In-app, email, webhook notifications
web/
  src/
    App.tsx                      React application root with routing
    lib/
      api.ts                     Typed API client with full report interfaces
      report-context.tsx         React Context for report state management
      AuthInit.tsx               Bridges Clerk getToken into api.ts
    components/
      Layout.tsx                 App shell with header, sidebar, responsive layout
      Sidebar.tsx                Navigation sidebar with active section highlighting
      ProtectedRoute.tsx         Clerk auth guard (dev mode passthrough)
      ClerkUserButton.tsx        User menu (sign out, manage account)
      DisclaimerBanner.tsx       Persistent "not financial advice" banner
      Footer.tsx                 Site footer with Terms/Privacy/Contact links
      ScoreGauge.tsx             SVG score gauge with grade
      MetricCard.tsx             Key metric display card
      CashflowBar.tsx            Recharts cashflow bar chart
      CategoryScores.tsx         Score breakdown with progress bars
      PriorityActions.tsx        Priority action list
      PageHeader.tsx             Reusable page header
      EmptyState.tsx             Empty state with call to action
      ThemeToggle.tsx            Dark mode toggle
    pages/
      HomePage.tsx               Dashboard overview
      CashflowPage.tsx           Cashflow detail page
      DebtPage.tsx               Debt analysis page
      GoalsPage.tsx              Goals progress page
      InvestmentsPage.tsx        Investment and pension page
      MortgagePage.tsx           Mortgage readiness and LTV page
      LifeEventsPage.tsx         Life events timeline page
      ScenariosPage.tsx          Stress tests and scenario trees page
      SettingsPage.tsx           JSON profile editor (power user)
      SignInPage.tsx             Clerk sign-in
      SignUpPage.tsx             Clerk sign-up
      ProfilePage.tsx            User info, GDPR data export, account deletion
      TermsPage.tsx              Terms of Service
      PrivacyPage.tsx            Privacy Policy (GDPR, FCA positioning)
    wizard/
      WizardPage.tsx             Guided onboarding wizard (9 steps)
      WizardContext.tsx          Wizard state management and save/resume
      steps/                     Personal, Income, Expenses, Savings, Debts,
                                 Goals, Mortgage, Life Events, Review
      components/                FieldGroup, CurrencyInput, PercentInput,
                                 SelectField, ToggleField, DynamicList,
                                 StepShell, ProgressBar, CompletenessScore,
                                 TemplateGoalPicker
      lib/                       Types, smart defaults, completeness scoring,
                                 localStorage persistence, profile conversion
tests/                           697 tests across 29 test files
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

All financial parameters are centralised in `config/assumptions.yaml` (419 lines) with source comments:
- Tax bands, NI thresholds, personal allowance (HMRC 2025/26)
- Scottish income tax bands (6 rates)
- Investment returns by risk profile, inflation rates, Monte Carlo parameters
- Mortgage products, LTV tiers, stamp duty bands
- State pension, pension annual allowance with taper
- Scoring weights, insurance cost estimates, child costs by age
- Student loan plans (2, 3, postgrad), ISA/LISA limits
- Lifetime cashflow phases, withdrawal sequencing rules
- IHT gift strategies, taper relief thresholds
- Compound scenario definitions (recession, boom, stagflation)

Auto-updated from HMRC, BoE, and ONS APIs via `engine/assumption_updater.py`.

## Documentation

Full documentation lives in `docs/` and is published as a static site via MkDocs.

```bash
# Install docs dependencies
pip install -r requirements-docs.txt

# Preview locally (http://localhost:8000)
mkdocs serve

# Build static site into site/
mkdocs build
```

Sections:

- **Home & Getting Started** — what GroundTruth is, who it's for, first analysis walkthrough
- **User Guide** — non-technical tour of every dashboard page and score
- **Profile Guide** — every field of the profile YAML explained
- **API Reference** — endpoint-by-endpoint with curl/Python examples
- **Assumptions Guide** — every financial parameter, its source, and when it updates
- **Technical Architecture** — pipeline, modules, data flow, deployment topology
- **Contributing** — dev setup, testing conventions, code standards
- **Legal & Compliance** — regulatory classification, GDPR rights, disclaimers

## Requirements

- Python 3.10+
- Node.js 18+ (for web dashboard)
- See `requirements.txt` for Python dependencies
- See `web/package.json` for frontend dependencies
- See `requirements-docs.txt` for MkDocs dependencies

## Roadmap

See `roadmap.md` for the forward plan. Current status:
- **v5 (Engine Foundation):** Complete — 18 modules, REST API, per-user auth, CSV/PDF exports
- **v6 (Web + Open Banking):** Complete — React dashboard, TrueLayer, WebSocket, what-if, notifications, WCAG
- **v7 (Production Hardening):** Complete — Security audit, integration tests, Docker/PostgreSQL, API polish
- **v8 (Intelligence Engine):** Complete — Monte Carlo, lifetime cashflow, withdrawal sequencing, risk profiling, IHT planning, scenario trees
- **v9 (Consumer Launch):** In progress — Multi-page dashboard (done), onboarding wizard (done), Clerk auth (done), legal framework (done), documentation (done), UI overhaul, pricing, deployment

## License

Private. Not yet open source.
