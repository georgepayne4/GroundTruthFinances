# REVIEW.md — Attention Items and Honest Assessment

**Last updated:** 2026-04-09 | **Covers:** v5.0 through v5.3-02

---

## Roadmap Deviations

| Planned | Actual | Impact |
|---------|--------|--------|
| v5.3-01 specified `/sensitivity` and `/scenario` as separate endpoints | Not implemented — sensitivity/scenarios only run as part of `/analyse` | Low. Can add standalone endpoints later if consumers need them. |
| v5.3-01 specified Pydantic models generated from v5.1-02 TypedDicts | Models written from scratch, not derived from TypedDicts | Minor duplication risk — API models and engine TypedDicts could drift. |
| TD-01 "audit all try/except blocks" | Not fully audited — some bare catches may remain | Low. Engine modules are well-structured but a grep for bare `except:` is overdue. |
| TD-02 "logger.info at entry/exit of all public functions" | Not systematically applied to all modules | Low. Logging works but coverage is inconsistent across older modules. |
| TD-09 "remove silent fallbacks" | Partially done. Many `.get(key, default)` remain in engine modules | Medium. Validator catches most issues, but engine modules still silently default. |
| v5.1-04 specified mypy --strict | mypy not enforced in CI or locally | Medium. Type annotations exist but aren't checked. TypedDicts are advisory only. |
| v5.1-06 "fix bonus tax" | Done in TD-06, not v5.1-06 — numbering shifted | None. Work was completed, just under a different label. |
| v5.3-02 specified PostgreSQL as API-mode backend | SQLAlchemy models are DB-agnostic; tested with SQLite only. No PostgreSQL tested yet. | Low for now. PostgreSQL will work via DATABASE_URL — just needs `psycopg2` or `asyncpg` and a real PG instance. |
| v5.3-02 specified migrating v5.2-05 SQLite history into PostgreSQL | No migration script for existing history.db data | Medium. Existing CLI users with history.db will need a one-time data migration tool. |

---

## Corners Cut

1. **API auth is a single shared API key** — No per-user auth, no token expiry, no rate limiting. The dev default key is hardcoded in tests. Fine for local/dev; must not ship to production like this.

2. **No CORS configuration** — API will reject browser requests from a frontend. Needs explicit CORS middleware before any web UI work.

3. **No request validation beyond Pydantic** — The API accepts any dict as `profile`. A malformed profile will hit the engine and may produce confusing errors rather than clean 400 responses.

4. **Subscription detection is keyword-based** — Simple merchant name matching. Will miss unusual merchants and may false-positive on one-off payments to subscription-like names. Roadmap v7.0-02 plans ML replacement.

5. **Income verification uses rough net/gross ratio bands** — Compares bank credits against declared gross using hardcoded 0.60-0.75 ratio estimates. Doesn't account for student loan deductions, salary sacrifice, or pension contributions that reduce take-home. Could flag false discrepancies.

6. **Trend detection is naive** — `_detect_trend()` uses a simple first-half/second-half comparison with a 15% threshold. Not statistically robust — small sample sizes (2-3 months) can trigger false trends.

7. **Bank CSV parsers are untested against real bank exports** — Format definitions are based on documented formats, not validated against actual downloaded CSVs from each bank. Edge cases (international transactions, pending items, refunds) may break parsing.

8. **No pagination on API history endpoint** — Returns up to 100 rows max. Fine now but won't scale if history grows large.

9. **`_run_pipeline()` duplicates `main.py` orchestration** — The API's pipeline runner mirrors the CLI's but they're separate code paths. A change to the pipeline must be made in both places.

10. **No PostgreSQL integration test** — v5.3-02 SQLAlchemy models are DB-agnostic but only tested against SQLite. PostgreSQL-specific behaviour (e.g., timezone handling, string collation) untested.

11. **No data migration from SQLite history.db** — Users who have been running the CLI with `--history` will need a migration path to bring existing runs into the new schema. Not yet built.

12. **Profile storage has no encryption** — YAML content stored as plaintext in the database. Contains financial data. Needs encryption at rest before multi-user deployment.

---

## Weaknesses

1. **Limited integration tests** — 329 tests, but only one API-level test exercises the full pipeline. A module interface change could still break the pipeline while unit tests pass.

2. **Assumptions staleness is a warning, not a block** — If `assumptions.yaml` is a year out of date, the engine still runs with stale tax bands. Users may not notice the warning in a long report.

3. **No input sanitisation for narrative output** — Profile field values (names, descriptions) are interpolated into Markdown/text output. A malicious profile name could inject Markdown formatting. Low risk for CLI; higher risk when reports are rendered in a web UI.

4. **SQLite history has no migration mechanism** — Schema changes require manual intervention or data loss. v5.3-02 (PostgreSQL + Alembic) fixes this, but current SQLite users have no upgrade path.

5. **No graceful degradation on partial profiles** — If a section is present but malformed (e.g., `expenses: "none"`), the engine may crash rather than skip the section.

6. **Category rules are YAML-file dependent** — `config/category_rules.yaml` must exist for bank CSV parsing. No fallback or embedded defaults if the file is missing.

---

## Tech Debt (Not Covered by Roadmap)

Items that need attention but are not addressed by any planned v5.3–v7.0 work item. These will silently degrade correctness, maintainability, or security if left indefinitely.

### Code Quality

1. **Hardcoded `basic_thresh = 50270` in `investments.py:1028`** — This is the only tax threshold not read from `assumptions.yaml`. If the basic rate threshold changes this line will silently produce wrong pension AA tax charge estimates.

2. **`insurance.py:398-399` uses `0.70` as a gross-to-net ratio** — Rough estimate used in survivor security analysis. Doesn't account for actual tax/NI situation. Should use the cashflow module's real net income when available.

3. **`life_events.py:439` caps effective tax rate at `0.60`** — Hardcoded ceiling on deduction ratio. Should reference assumptions or at minimum be named as a constant.

4. **`life_events.py:278` uses `0.8` as net worth dip threshold** — Hardcoded 20% drop trigger for milestone warnings. Should be configurable in `assumptions.yaml` under simulation params.

5. **`_run_pipeline()` exists in both `main.py` and `api/main.py`** — Two independent pipeline orchestration paths. Any new module or parameter change must be applied in both. Extract to `engine/pipeline.py`.

### Private API Boundary Violations

6. **`api/main.py` imports `engine.loader._normalise_profile`** — The underscore-prefixed function is private. The API should use a public `normalise_profile()` or the loader should expose it without the underscore.

7. **`api/database/crud.py` imports `engine.history._extract_metrics`** — Same issue. `_extract_metrics` should be promoted to public or its logic duplicated.

8. **`engine/validator.py:366` imports `engine.loader._ACCOUNT_TYPE_MAPPING`** — Cross-module private import. Should be a public constant or moved to a shared module.

### Testing Gaps

9. **No test runs the CLI `main.py` end-to-end** — API has an integration test via TestClient but the CLI pipeline (`python main.py`) is only manually verified. A subprocess-based test would catch orchestration regressions.

10. **Bank CSV parsers have zero real-file tests** — All tests use synthetic CSV strings. Need fixture files from actual bank exports (redacted) to validate format detection and edge cases.

11. **mypy is configured but never run** — Type annotations are decorative. Enabling `mypy --strict` on `engine/` would catch dict key typos and wrong return types. Likely to surface 50+ issues on first run.

### Configuration and Defaults

12. **Silent `.get()` defaults mask missing data** — Over 100 `.get(key, 0)` calls across engine modules. If the validator fails to flag a missing field, the engine silently uses 0 and produces misleading results. TD-09 was planned but only partially addressed.

13. **`config/category_rules.yaml` has no embedded fallback** — If the file is missing, bank CSV import crashes. Should ship a default ruleset inline or raise a clear error pointing to the file.

14. **No schema version in `assumptions.yaml`** — Staleness is checked by `effective_to` date, but there's no structural version. Adding a new required key to assumptions breaks old files silently.

### Security and Data

15. **API dev key `"dev-key-change-me"` is used in test assertions** — If someone deploys without setting `GROUNDTRUTH_API_KEY`, the dev key is live. API should refuse to start if the env var matches the dev default.

16. **No rate limiting on any endpoint** — A single client can hammer `/analyse` (which runs the full 15-stage pipeline). CPU-bound denial of service.

17. **Profile YAML stored as plaintext in `profiles` table** — Financial data including income, debts, and balances. Needs column-level encryption or application-level envelope encryption before any multi-user deployment.

18. **No audit logging** — API has no record of who called which endpoint, when. Required for compliance and debugging when multi-user isolation is added (v5.3-04).

---

## What's Working Well

- Pure function architecture makes modules genuinely independent and testable
- 329 tests passing with good coverage on critical paths (tax, cashflow, scoring, database)
- Validator catches most input issues before they reach the engine
- Backward compatibility maintained — old profiles still work
- Assumptions.yaml is comprehensive with source comments
- API design is clean and follows REST conventions
- Bank CSV parser handles 7 UK bank formats with auto-detection

---

## Priority Actions Before v5.3-03

1. **Extract `_run_pipeline()` to a shared module** — eliminates CLI/API divergence risk
2. **Add CORS middleware to the API** — trivial to add, blocks all frontend work without it
3. **Build SQLite-to-SQLAlchemy history migration script** — one-time tool for existing CLI users
4. **Test against real PostgreSQL instance** — verify timezone handling, constraint behaviour
