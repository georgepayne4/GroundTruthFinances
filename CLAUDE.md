# CLAUDE.md — GroundTruth Financial Planning Platform

## Project Overview

UK personal financial planning engine. Python, YAML-driven, CLI-first.
17 engine modules, ~7,600 lines. See `roadmap.md` for the full v5+ plan.

## Commit Rules

- Conventional commits: `feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`
- Single-line messages. No co-author trailers. No multi-line bodies.
- Never commit broken code. Run `python main.py` against `config/sample_input.yaml` before committing.
- Group related changes into logical commits. Don't split one feature across commits unless necessary.

## File Rules

- Never commit planning/notes files (IMPROVEMENTS.md, roadmap.md, or any non-README .md) unless explicitly asked.
- Changes to `config/sample_input.yaml` must also be applied to `config/george_input.yaml`.
- Do not run `george_input.yaml` unless explicitly needed. Use `sample_input.yaml` for routine testing.
- `config/george_input.yaml` is in `.gitignore` — it contains real personal financial data.

## Code Standards

- Production-grade. Write code as if shipping to thousands of users.
- Match existing patterns: pure functions (dict in, dict out), `_private` helpers, docstrings on public functions.
- All magic numbers in `config/assumptions.yaml`, not in code.
- New profile fields are always optional with sensible defaults (backward compatibility).
- Think at scale: modular, testable, extensible. No shortcuts that create tech debt.
- No speculative abstractions — but design interfaces that can grow.
- Best practice code style for a production Python project. Prioritise readability, consistency, and maintainability.

## Error Handling

- Custom exceptions in `engine/exceptions.py`. Use the hierarchy:
  - `GroundTruthError` (base) -> `ProfileError`, `AssumptionError`, `CalculationError`, `ReportError`
  - `ProfileError` -> `MissingSectionError`, `InvalidFieldError`
- Validation layer (`validator.py`) handles soft errors via flags — never raise for recoverable issues.
- Engine modules raise `CalculationError` only for truly unrecoverable states.
- Never silently swallow exceptions. Log and re-raise or handle explicitly.
- At system boundaries (YAML load, file write): catch specific exceptions, wrap in domain exceptions.

## Logging

- Every engine module has `logger = logging.getLogger(__name__)`.
- `main.py` configures logging: file handler (DEBUG to `outputs/engine.log`), optional console (`--verbose`).
- Use `logger.info()` for module entry/exit and key metrics.
- Use `logger.debug()` for intermediate calculation detail.
- Use `logger.warning()` for recoverable anomalies.
- Never use `print()` for diagnostic output — `print()` is the CLI user interface only.

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
- For simple/mechanical tasks, consider whether lower effort is appropriate to conserve quota.
- Maximise work output per session. Batch efficiently.

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

## Version Cadence

Target: one version per month. Rapid development, high quality. Don't compromise standards for speed — but don't over-engineer either. Ship working increments.
