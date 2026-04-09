# CLAUDE.md — GroundTruth Financial Planning Platform

## Project Overview

UK personal financial planning engine. Python, YAML-driven, CLI-first.
See `roadmap.md` for the full v5+ plan.

## Commit Rules

- Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- Single-line messages. No co-author trailers. No multi-line bodies.
- Never commit broken code. Run `python main.py` against `config/sample_input.yaml` before committing.
- **Before every push**: run `ruff check .` (entire codebase) and `python -m pytest --tb=short -q`. CI runs both — push only when both pass locally.
- Group related changes into logical commits. Don't split one feature across commits unless necessary.

## File Rules

- Never commit planning/notes files (IMPROVEMENTS.md, roadmap.md, or any non-README .md) unless explicitly asked.
- Changes to `config/sample_input.yaml` must also be applied to `config/george_input.yaml`.
- Do not run `george_input.yaml` unless explicitly needed. Use `sample_input.yaml` for routine testing.
- `config/george_input.yaml` is in `.gitignore` — it contains real personal financial data.

## Code Standards

- Production-grade. Write code as if shipping to thousands of users.
- Pure functions (dict in, dict out). `_private` helpers. Docstrings on public functions only.
- All magic numbers in `config/assumptions.yaml`, not in code. Assumptions.yaml is the single source of truth — never duplicate config values in code or other files.
- New profile fields are always optional with sensible defaults (backward compatibility).
- No dead code. Delete unused functions, imports, and variables immediately. Never comment out code.
- No speculative abstractions — but design interfaces that can grow.
- Import ordering: stdlib -> third-party -> local. Enforced by isort (when CI is set up).

## Language and Tooling

- Python is the current engine language but not a constraint. If another language or tool is demonstrably better for a component (e.g., TypeScript for web frontend, Rust for computation-heavy simulation, Go for API performance), use it with justification.
- Justify means: state what Python lacks and what the alternative provides. No change for novelty.
- The engine core should remain cohesive — don't fragment into 5 languages. But a polyglot stack with clear boundaries (e.g., Python engine + TypeScript UI + Go API gateway) is fine.

## Tooling Notes

- `gh` CLI is not installed. Use `git` commands and the GitHub API via `curl`/`httpx` for any GitHub operations (checking CI status, creating PRs, etc.).
- CI status can be checked via: `curl -s -H "Accept: application/vnd.github+json" https://api.github.com/repos/georgepayne4/GroundTruthFinances/actions/runs?per_page=3`

## Deprecation Policy

- No deprecation warnings until the project has external consumers (v5.3 API).
- Remove immediately. No commented-out code, no `_deprecated_` prefixes, no shims.
- When external API exists: one version deprecation notice, then remove.

## Error Handling

- Custom exceptions in `engine/exceptions.py`. Hierarchy:
  - `GroundTruthError` (base) -> `ProfileError`, `AssumptionError`, `CalculationError`, `ReportError`
  - `ProfileError` -> `MissingSectionError`, `InvalidFieldError`
- Validation layer (`validator.py`) handles soft errors via flags — never raise for recoverable issues.
- Engine modules raise `CalculationError` only for truly unrecoverable states.
- Never silently swallow exceptions. Log and re-raise or handle explicitly.
- At system boundaries (YAML load, file write): catch specific exceptions, wrap in domain exceptions.

## Input Validation

- All inputs must be validated before processing. This applies to:
  - Profile YAML (via `validator.py`)
  - Assumptions YAML (schema validation — TD-09)
  - Future: API request bodies (via Pydantic models)
- Never trust input data in engine modules. Validator ensures completeness; engine can assert.

## Logging

- Every engine module has `logger = logging.getLogger(__name__)`.
- `main.py` configures: file handler (DEBUG -> `outputs/engine.log`), optional console (`--verbose`).
- `logger.info()` for module entry/exit and key metrics.
- `logger.debug()` for intermediate calculation detail.
- `logger.warning()` for recoverable anomalies.
- Never use `print()` for diagnostic output — `print()` is the CLI user interface only.

## Security

- Never log sensitive financial data (balances, income, names) at INFO level. PII only at DEBUG.
- No credentials, API keys, or personal data in committed files.
- `george_input.yaml` must never be committed.

## Module Boundaries

- Modules must not import `_private` functions from other modules.
- Known violation: `life_events.py` imports `mortgage._monthly_repayment`. Fix by extracting to shared utility.
- Public API per module = the single top-level function. Everything else is private.

## Assumptions Config

- Changes to `config/assumptions.yaml` should include a source comment (e.g., `# HMRC 2025/26`).
- All financial parameters must be configurable. No hardcoded rates, thresholds, or limits in engine code.

## Domain Expertise

Apply simultaneous expertise as:
- **Senior fintech engineer** — architecture, performance, security, API design
- **Chartered financial planner** — UK tax optimisation, pension strategy, estate planning
- **Mortgage advisor** — LTV analysis, affordability, product selection, stress testing
- **Investment analyst** — portfolio construction, risk management, fee analysis, withdrawal strategy

All financial logic is UK-specific until explicitly told otherwise. Flag anything that wouldn't generalise internationally in `roadmap.md` or a separate notes file.

## Output Style

- Very concise. No preamble, no filler. Lead with action.
- Brief recap after work (1-2 lines). No full justifications.
- Minimise token usage — user is on Claude Pro with Opus usage caps.
- Maximise work output per session. Batch efficiently.

## Model Usage Guidance

- **Opus** — Architecture decisions, financial calculation logic, new module design, complex refactors
- **Sonnet** — Mechanical tasks: renaming, formatting, repetitive edits, running tests, simple bug fixes
- Use `/compact` or `/clear` to reduce context when switching tasks

## Architecture Context

```
YAML inputs -> loader -> validator -> cashflow -> debt -> goals -> investments
-> mortgage -> insurance -> life_events -> scoring -> scenarios -> sensitivity
-> estate -> insights -> narrative -> report (JSON + Markdown)
```

Pipeline architecture. Modules are pure functions. No shared state, no database (yet).
See `roadmap.md` for the phased evolution toward API, database, and web UI.

## Testing

- No test suite exists yet (v5.1 priority).
- Until unit tests exist: verify changes by running `python main.py` with sample_input.yaml.
- When tests exist: run full suite before committing.

## Branch Strategy

- Work on `master` directly until the platform reaches deployable state.
- Switch to feature branches when scope warrants JIRA-style tickets.

## Session Continuity

- Before a session ends or when usage limits approach, write a `SESSION.md` file in the project root capturing:
  - **Last completed item** (e.g., "TD-06 done, TD-07 in progress")
  - **Current working state** (files modified but uncommitted, branch state)
  - **Next action** (exact next step to resume, not vague)
  - **Blockers or decisions pending** (anything needing user input)
- This file is the handoff document. A new session reads it first and resumes without asking "where were we?"
- Keep it short — a checklist, not an essay. Overwrite each session, don't append.
- `SESSION.md` is a working file. Add to `.gitignore`.

## Version Cadence

Versions are roadmap milestones, not calendar deadlines. Push through the roadmap session by session. Push and switch to branch methodology when the platform reaches deployable state. Ship working increments.
