# Contributing

This guide is for engineers extending GroundTruth. Read `CLAUDE.md` in the repository root for the authoritative standards — this document summarises the most important rules.

## Development setup

### Prerequisites

- Python 3.10+
- Node.js 18+
- Git

### Clone and install

```bash
git clone https://github.com/georgepayne4/GroundTruthFinances.git
cd GroundTruthFinances

# Python backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# Frontend
cd web
npm install
cd ..
```

### Environment variables

Create `.env` in the repo root:

```bash
# Optional — enables Clerk auth
CLERK_SECRET_KEY=sk_test_...
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...

# Required for profile encryption at rest
FERNET_KEY=<generated>

# Optional — enables TrueLayer Open Banking
TRUELAYER_CLIENT_ID=...
TRUELAYER_CLIENT_SECRET=...
```

Generate a Fernet key:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Run the stack locally

```bash
# Backend (from repo root)
uvicorn api.main:app --reload

# Frontend (separate terminal, from web/)
cd web && npm run dev
```

- API: http://localhost:8000 (docs at `/docs`)
- Dashboard: http://localhost:5173 (proxies API to localhost:8000)

### Run the CLI

```bash
python main.py                                      # sample profile
python main.py --bank-csv statement.csv             # CSV import
python main.py --verbose                            # console logging
```

## Before you commit

Every commit must pass:

```bash
ruff check .                          # Python lint (zero warnings)
python -m pytest --tb=short -q        # 697 tests, all green
cd web && npx tsc --noEmit            # TypeScript compiles
```

CI runs these. Push only when all three pass locally.

## Commit rules

- **Conventional commits:** `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- **Single-line messages.** No co-author trailers. No multi-line bodies.
- **Never commit broken code.** Run the sample profile before committing.
- **Group related changes** into one commit. Don't split one feature across multiple commits unless necessary.
- **Version reference:** feature commits should reference the roadmap version, e.g., `feat: add Monte Carlo projections (v8.1)`.

## Code standards

### Python

- **Pure functions.** Dict in, dict out. No global state.
- **`_private` helpers.** Prefix internal functions with underscore; never import across modules.
- **Docstrings on public API** only (the single top-level function per module).
- **Import ordering:** stdlib → third-party → local. Enforced by isort when CI is set up.
- **No dead code.** Delete unused functions, imports, and variables immediately.
- **No speculative abstractions.** Build for current requirements, not hypothetical future ones.
- **Type annotations** on new public functions (we're migrating toward full coverage).

### TypeScript

- **Strict mode.** `noImplicitAny`, `strictNullChecks`.
- **No `any` escapes.** If you genuinely need `unknown`, use `unknown`.
- **Functional components with hooks.** No class components.
- **Tailwind utility classes.** No CSS modules, no styled-components.

### Magic numbers

All financial parameters live in `config/assumptions.yaml`. Zero duplication tolerance:

- If a value appears in `assumptions.yaml`, it must never appear as a default in Python code.
- Engine code reads from the loaded assumptions dict; it does not define fallbacks.
- Adding a new parameter requires adding it to `assumptions.yaml` with a source comment.

### Backward compatibility

New profile fields are always **optional with sensible defaults**. Old profiles must keep working without edits. This is a project invariant.

## Testing

### Requirements for new modules

Every new engine module must include:

- Unit tests for the public function
- At least one integration test touching an upstream or downstream module
- Edge case tests for boundary conditions (zero income, negative balance, etc.)

### Running tests

```bash
python -m pytest                       # full suite
python -m pytest tests/test_cashflow.py  # single file
python -m pytest -k mortgage           # name pattern
python -m pytest --cov=engine          # coverage
```

### Edge-case-first principle

Before writing any financial calculation, identify the edge case that would embarrass the product (zero income, 100-year-old user, £0 pension, negative balance). Write the test for that case first, then the implementation.

### Integration tests are mandatory

Unit tests alone don't catch cross-module bugs. Every pipeline-affecting change needs an integration test that runs the full pipeline on a representative profile.

## Module boundaries

- Modules must not import `_private` functions from other modules.
- Public API per module = the single top-level function. Everything else is private.
- Shared utilities live in `engine/utils.py`.
- If two modules need the same helper, put it in `utils.py` — don't duplicate.

## Error handling

Exception hierarchy in `engine/exceptions.py`:

```
GroundTruthError
├── ProfileError
│   ├── MissingSectionError
│   └── InvalidFieldError
├── AssumptionError
├── CalculationError
└── ReportError
```

Rules:

- **Validator handles soft errors** via severity flags — never raise for recoverable issues.
- **Engine modules raise `CalculationError` only for unrecoverable states.**
- **Never silently swallow exceptions.** Log and re-raise, or handle explicitly.
- **At system boundaries** (YAML load, file write), catch specific exceptions and wrap in domain exceptions.

## Logging

- Every engine module has `logger = logging.getLogger(__name__)`.
- `main.py` configures file handler (DEBUG → `outputs/engine.log`) + optional console (`--verbose`).
- `logger.info()` for module entry/exit and key metrics.
- `logger.debug()` for intermediate calculation detail.
- `logger.warning()` for recoverable anomalies.
- **Never use `print()` for diagnostics** — `print()` is the CLI user interface only.

## Security

- **Never log sensitive financial data** (balances, income, names) at INFO level. PII only at DEBUG.
- **No credentials, API keys, or personal data** in committed files.
- **`config/george_input.yaml` must never be committed** (it's in `.gitignore`).
- **Never commit Clerk keys** — `VITE_CLERK_PUBLISHABLE_KEY` in `web/.env.local`, `CLERK_SECRET_KEY` in `.env`.
- **Secret keys are backend-only.** Never import or reference `sk_*` in `web/` code.

## Documentation

- Every feature commit that changes user-facing capability must update the docs in the same commit.
- Write for the target user: a non-technical professional trying to understand their finances.
- `docs/` is the source of truth for user-facing docs; `CLAUDE.md` is the source of truth for engineering standards.

## Planning

- Use plan mode (`/plan`) before starting any non-trivial implementation task (new features, architectural changes, multi-file refactors).
- Trivial changes (typo fixes, single-line edits, running tests) can proceed directly.

## Pull requests

We work on `master` directly until the platform reaches a deployable state (v9.8 production deployment). After that, feature branches and PRs are mandatory.

Until then:

- Commit directly to `master`
- Before pushing, ensure `ruff`, `pytest`, and `tsc` are clean
- After pushing, pause and add any gaps or shortcuts noticed to `REVIEW.md`

## Domain expertise

When writing financial code, apply simultaneous expertise as:

- **Senior fintech engineer** — architecture, performance, security, API design
- **Chartered financial planner** — UK tax optimisation, pension strategy, estate planning
- **Mortgage advisor** — LTV analysis, affordability, product selection, stress testing
- **Investment analyst** — portfolio construction, risk management, fee analysis, withdrawal strategy

Every calculation should be defensible against equivalent features in Voyant, CashCalc, Emma, or competing platforms. If the approach wouldn't win a £10,000 bet, rethink it.

## Getting help

- **Roadmap:** `roadmap.md` in the repo root
- **Known issues:** `REVIEW.md` in the repo root
- **Session state:** `SESSION.md` (gitignored)
- **Standards:** `CLAUDE.md`
