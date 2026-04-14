# Technical Architecture

This page describes how GroundTruth is built. Written for engineers extending the system.

## High level

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│  React web app  │    │  CLI (main.py)   │    │  Third parties  │
│  TypeScript +   │    │  Python          │    │  TrueLayer,     │
│  Vite + Tailwind│    │                  │    │  Clerk, HMRC    │
└────────┬────────┘    └─────────┬────────┘    └────────┬────────┘
         │                       │                      │
         │  HTTPS + WebSocket    │                      │
         │                       │                      │
         ▼                       ▼                      ▼
┌──────────────────────────────────────────────────────────────────┐
│                         FastAPI (api/)                           │
│  Dual auth (Clerk JWT + API key) · Rate limit · Audit log        │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│                     Engine pipeline (engine/)                    │
│  22 pure-function modules orchestrated by pipeline.py            │
└──────────────────────────┬───────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────────────┐
│         SQLAlchemy persistence (SQLite dev / Postgres prod)      │
└──────────────────────────────────────────────────────────────────┘
```

## Pipeline architecture

The engine is a **pure-function pipeline**. Each module takes a dict (profile + intermediate results), returns a dict, and has no shared state.

```
YAML/JSON input
  │
  ▼
loader.py         Parse and normalise input
  │
  ▼
validator.py      Severity-graded flags; no silent errors
  │
  ▼
cashflow.py       Income, tax, NI, surplus, savings rate
  │
  ▼
debt.py           Payoff strategies, student loan intelligence
  │
  ▼
goals.py          Priority-weighted surplus allocation
  │
  ▼
investments.py    Portfolio projections, pension adequacy
  │
  ▼
monte_carlo.py    GBM simulation (optional)
  │
  ▼
lifetime_cashflow.py   Year-by-year multi-phase projection
  │
  ▼
withdrawal.py     Tax-optimal drawdown sequencing
  │
  ▼
risk_profiling.py Per-goal capacity/need assessment
  │
  ▼
mortgage.py       Borrowing, LTV, overpayment
  │
  ▼
insurance.py      Coverage gap analysis
  │
  ▼
life_events.py    Scheduled change simulation
  │
  ▼
scoring.py        Composite 0-100 score
  │
  ▼
scenarios.py      Stress tests, compound scenario trees
  │
  ▼
sensitivity.py    Parameter sweeps
  │
  ▼
estate.py         IHT, gift strategies, RNRB
  │
  ▼
insights.py       Priority actions, recommendations
  │
  ▼
narrative.py      Markdown advisor letter
  │
  ▼
report.py         Final JSON + meta assembly
```

## Module invariants

1. **Pure functions.** Dict in, dict out. No global state, no mutation of inputs.
2. **Private helpers are private.** No module imports `_private` functions from another module.
3. **Public API is the top-level function.** Everything else is implementation detail.
4. **No hardcoded constants.** Every parameter reads from `config/assumptions.yaml`.
5. **Single source of truth.** If a value lives in assumptions, it cannot also live in code.
6. **No silent exceptions.** Log and re-raise, or handle explicitly.

## API layer (`api/`)

| File | Responsibility |
|------|---------------|
| `main.py` | FastAPI app, endpoint definitions, middleware |
| `models.py` | Pydantic request/response schemas |
| `dependencies.py` | Dual auth, rate limiting, DI |
| `clerk_auth.py` | Clerk JWT verification via JWKS |
| `exports.py` | CSV/XLSX/PDF generation |
| `websocket.py` | Streaming analysis endpoint (authenticated) |
| `whatif.py` | What-if parameter modifications |
| `comparison.py` | Profile comparison and branching |
| `cashflow_actual.py` | Planned vs actual drift |
| `database/` | SQLAlchemy ORM, sessions, CRUD |
| `banking/` | TrueLayer Open Banking integration |
| `notifications/` | In-app, email, webhook notifications |

### Authentication architecture

```
Incoming request
  │
  ├─ Authorization: Bearer <jwt> ──▶ clerk_auth.verify_clerk_token
  │                                    │
  │                                    ├─ Fetch JWKS from Clerk
  │                                    ├─ Verify RS256 signature
  │                                    └─ Return claims (sub, etc.)
  │                                            │
  │                                            ▼
  │                                    get_or_create_user_by_clerk_id
  │
  └─ X-API-Key: <key> ──▶ hash and lookup in User.api_key_hash
                                          │
                                          ▼
                                    get_user_by_key_hash
```

Both paths resolve to the same `User` model. Downstream endpoints treat them identically.

## Database model

SQLAlchemy ORM. Core tables:

| Table | Purpose |
|-------|---------|
| `users` | Identity, auth, soft-delete (`deleted_at`) |
| `profiles` | YAML content (encrypted at rest via Fernet), ownership |
| `reports` | Generated analysis output (JSON) |
| `runs` | Historical snapshots with extracted metrics |
| `assumptions` | Versioned assumption sets by tax year |
| `bank_connections` | Open Banking tokens (encrypted) |
| `notifications` | In-app notification queue |
| `notification_preferences` | Per-user delivery settings |
| `audit_log` | Every API call with user, endpoint, status |

### Encryption at rest

- **Profiles** use Fernet symmetric encryption (`api/banking/encryption.py`).
- **Bank tokens** use the same Fernet infrastructure.
- **Reports** are stored plaintext (they're derived data).
- Encryption key lives in `.env` (`FERNET_KEY`), never in the repo.

## Frontend (`web/`)

React 19 + TypeScript + Vite + TailwindCSS 4.

```
web/src/
  App.tsx                  Router root
  main.tsx                 ClerkProvider wrap
  lib/
    api.ts                 Typed API client
    AuthInit.tsx           Bridges Clerk getToken into api.ts
    report-context.tsx     Report state (React Context)
  components/
    Layout.tsx             App shell (header, sidebar, content)
    ProtectedRoute.tsx     Auth guard (dev-mode passthrough)
    DisclaimerBanner.tsx   Persistent disclaimer strip
    Footer.tsx             Terms/Privacy/Contact
  pages/
    (one per dashboard section)
  wizard/
    9-step guided onboarding flow
```

### State management

- **Report state** — React Context (`report-context.tsx`). Single source of truth for the current analysis result.
- **Auth state** — Clerk provides `useAuth()`, `useUser()`. No custom auth state.
- **Wizard state** — Wizard Context with localStorage persistence (30-day expiry).

### API client pattern

`api.ts` is a plain TypeScript module (no React dependencies). A bridge component (`AuthInit.tsx`) uses `useAuth().getToken` and injects it into `api.ts` via `setTokenProvider(fn)`. This keeps the API client testable and framework-agnostic.

## Streaming architecture

Long analyses stream via WebSocket (`/ws/analyse`). Each pipeline stage yields a message:

```json
{ "stage": "cashflow", "status": "done", "payload": { ... } }
```

`engine/pipeline_streaming.py` is a generator-based variant of `pipeline.py`. Same modules, different orchestration.

## Configuration flow

```
config/assumptions.yaml
  │
  ▼
engine/loader.py                 (loads and validates)
  │
  ▼
pipeline.py / pipeline_streaming.py
  │
  ├──▶ Every module receives assumptions as argument
  │
  ▼
engine/report.py                 (meta.legal, meta.assumptions_version)
  │
  ▼
api/exports.py                   (CSV/XLSX disclaimer rows)
```

No module reads `assumptions.yaml` directly. Reads happen once at the entry point; the resulting dict is passed down.

## Deployment topology (planned v9.8)

```
Cloudflare CDN  ────▶  web/ static assets (Vite build)
                                │
                                ▼
                       Fly.io or Railway
                       ┌────────────────────────────┐
                       │  FastAPI (api/)            │
                       │  Uvicorn workers           │
                       └─────────┬──────────────────┘
                                 │
                       ┌─────────┴──────────────────┐
                       │                            │
                       ▼                            ▼
              Managed PostgreSQL            Redis (sessions,
              (daily backups)               WebSocket state)
                       │
                       ▼
              Sentry (errors, traces)
```

Not yet shipped. See `roadmap.md` v9.8.

## Testing

697 tests across 29 files. Structure:

- `tests/test_*.py` per engine module — unit tests for pure functions
- `tests/test_integration.py` — cross-module pipeline tests
- `tests/test_api.py` — FastAPI endpoint tests via `TestClient`
- `tests/test_database.py` — ORM and migration tests
- `tests/test_websocket.py` — streaming endpoint tests

Run:

```bash
python -m pytest --tb=short -q
```

Pre-commit hook requirements:

- `ruff check .` — lint (zero warnings)
- `python -m pytest` — all tests pass
- `cd web && npx tsc --noEmit` — TypeScript compiles

## Observability

- **Logging:** every module has `logger = logging.getLogger(__name__)`. File handler at DEBUG, optional console at INFO.
- **Audit log:** every authenticated API call persisted with user_id, endpoint, method, status.
- **Sentry:** planned for v9.8.
- **Metrics:** planned via Prometheus or similar.

## What this architecture optimises for

- **Correctness.** Pure functions, explicit assumptions, typed contracts.
- **Readability.** One module per domain, short files, docstrings on public API.
- **Testability.** Unit tests are trivial because there's no shared state.
- **Extensibility.** Adding a new engine module means adding one file and wiring it into `pipeline.py`.

## What it deliberately does not do

- **ORM-style input abstraction.** Profiles are dicts. We don't have `Profile` / `Income` / `Expense` classes. This is a choice — the domain is data, not behaviour.
- **Microservices.** The engine is monolithic by design. Splitting modules into services would be complexity for no benefit.
- **Custom DI framework.** FastAPI's `Depends` and Python's `functools` cover what we need.
