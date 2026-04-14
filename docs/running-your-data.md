# Running Your Own Data

This page is the end-to-end walkthrough for analysing your own finances with GroundTruth — from environment setup to viewing results. It assumes you're running the platform locally (pre-production) with a profile file you've hand-built or edited from the sample.

!!! warning "Real financial data"
    Your profile contains sensitive personal data. Keep it in a file that is **gitignored**. The repo's `.gitignore` already excludes `george_input.yaml` as a convention — if you name your file the same, it won't be committed. Otherwise, add your filename to `.gitignore` explicitly.

## Prerequisites

Before you start, make sure you have:

- Python 3.10+ with the repo's dependencies installed (`pip install -r requirements-dev.txt`)
- Node.js 18+ with the frontend dependencies installed (`cd web && npm install`)
- A `.env` file in the repo root with a Fernet key for profile encryption at rest
- Your financial profile as a YAML file — use `config/sample_input.yaml` as a template; see the [Profile Guide](profile-guide.md) for every field

### Generate a Fernet key (one-off)

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the output into `.env`:

```
FERNET_KEY=<paste-the-key-here>
```

This key encrypts profile content in the database. Without it, encryption falls back to plaintext with a warning. For local testing, either works — but set it so you're testing the real path.

### Optional — Clerk authentication

If you want to test the full auth flow:

- Create a free Clerk project at https://dashboard.clerk.com (test mode)
- Put `VITE_CLERK_PUBLISHABLE_KEY=pk_test_...` in `web/.env.local`
- Put `CLERK_SECRET_KEY=sk_test_...` in `.env`

If you skip Clerk, the frontend runs in dev mode and lets you into the dashboard without signing in. For pre-launch testing, dev mode is fine.

## Option A — CLI only (fastest)

If you just want to see the numbers for your profile without touching the web UI:

```bash
python main.py --profile config/your_profile.yaml
```

Outputs land in `outputs/`:

- **Markdown report** — `outputs/report_<profile_name>_<timestamp>.md` (opens in any text editor)
- **JSON report** — `outputs/report_<profile_name>_<timestamp>.json` (full structured output)
- **Engine log** — `outputs/engine.log` (DEBUG-level trace of the pipeline)

This is the quickest end-to-end test. It exercises the full engine pipeline without auth, API, or frontend overhead. Use it to sanity-check your profile before going through the web UI.

### CLI flags

```bash
python main.py --profile config/your_profile.yaml --verbose   # console logging
python main.py --profile config/your_profile.yaml --bank-csv statement.csv   # merge bank CSV into profile
python main.py --history                                       # list recent runs
python main.py --diff                                          # diff latest two runs
```

## Option B — Full web dashboard

This is the path that mirrors what real users will experience.

### Step 1 — Convert YAML to JSON

The Settings page currently accepts **JSON only**. Convert your YAML profile once:

```bash
python -c "import yaml, json; print(json.dumps(yaml.safe_load(open('config/your_profile.yaml')), default=str, indent=2))" > your_profile.json
```

!!! info "YAML upload support"
    Direct YAML upload (and file picker) in the Settings page is a planned v9.4 UI improvement. Until then, convert with the one-liner above.

### Step 2 — Start the stack

Two terminals:

**Terminal 1 — Backend:**

```bash
uvicorn api.main:app --reload
```

API at http://localhost:8000. Interactive docs at http://localhost:8000/docs.

**Terminal 2 — Frontend:**

```bash
cd web && npm run dev
```

Dashboard at http://localhost:5173. Vite proxies `/api` calls to the backend automatically.

### Step 3 — Sign in (or skip in dev mode)

Open http://localhost:5173:

- **With Clerk configured:** you'll be redirected to `/sign-in`. Create a test account (use a real email you can verify).
- **Without Clerk:** the frontend detects dev mode and loads straight to the dashboard.

### Step 4 — Paste your profile and run analysis

1. Click **Settings** in the sidebar.
2. Paste the contents of `your_profile.json` into the textarea.
3. Click **Run Analysis**.
4. You should land on the **Home** page with your score, grade, and priority actions.

### Step 5 — Explore every page

Work through the sidebar top to bottom. Each page is explained in the [User Guide](user-guide/index.md):

- **Home** — headline score, surplus, net worth, top actions
- **Cashflow** — income/expense waterfall, savings rate, benchmarks
- **Debt** — per-debt payoff timeline, strategy recommendation
- **Goals** — feasibility status, what-would-it-take analysis
- **Investments** — portfolio allocation, pension adequacy, fee drag
- **Mortgage** — readiness checklist, LTV bands, overpayment scenarios
- **Life Events** — year-by-year trajectory with milestones
- **Scenarios** — job loss runway, rate shock, market drawdown, compound trees
- **Profile** — GDPR data export, account deletion

### Step 6 — Test the GDPR export

On the **Profile** page, click **Download my data**. You should receive a JSON file containing every piece of data the platform holds about you — profile, reports, audit log, notifications. Open it in a text editor to confirm your data is there and sensitive fields (bank tokens, if any) are redacted.

!!! danger "Do not click Delete my account yet"
    The **Delete my account** button is immediate and irreversible. It wipes PII, deletes profiles, and signs you out. Only click it when you're done testing.

## Option C — API directly

For scripted testing or integration work:

```bash
# With API key (dev default)
curl -X POST http://localhost:8000/api/v1/analyse \
  -H "X-API-Key: dev-key-change-me" \
  -H "Content-Type: application/json" \
  -d "{\"profile\": $(cat your_profile.json)}" | jq

# With Clerk token (get from browser devtools after signing in)
curl -X POST http://localhost:8000/api/v1/analyse \
  -H "Authorization: Bearer $CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"profile\": $(cat your_profile.json)}" | jq
```

See the [API Reference](api-reference.md) for every endpoint.

## Troubleshooting

**"Invalid JSON" alert when clicking Run Analysis.**  
The Settings page validates JSON syntax. Re-run the YAML→JSON conversion one-liner; if it still fails, check for tabs vs spaces or trailing commas.

**Analysis fails with validation errors.**  
The validator returned `error`-severity flags. Check the browser console or the `outputs/engine.log` file — each flag says which field is wrong. Fix and re-analyse.

**Dashboard shows blank/empty state.**  
The profile didn't persist or analysis didn't complete. Go back to Settings and re-run. If the JSON is empty in the textarea, the report context lost state — paste again.

**Frontend can't reach the API.**  
Check Terminal 1 — the backend must be running on port 8000. Vite dev server proxies `/api` calls to `http://localhost:8000`; if you changed the backend port, update `web/vite.config.ts`.

**Clerk sign-in redirects forever.**  
Check `web/.env.local` has `VITE_CLERK_PUBLISHABLE_KEY` set. Check the Clerk dashboard allowed origins include `http://localhost:5173`.

**Numbers look wrong.**  
Run the CLI path (Option A) in parallel — if the CLI produces the same numbers, the issue is in your profile or assumptions. If the CLI is right but the web dashboard is wrong, the bug is in the API or frontend. Narrow it down before debugging.

## What to check

When running your own data, look for these specific things that could be wrong:

1. **Cashflow surplus sign.** Positive = saving; negative = drawing down. If you expect surplus and see deficit, the expense category totals are probably over-stated.
2. **Tax calculation.** Check the deductions block. Income tax + NI should match your real paycheck within a few pounds. If it's off by more than 2%, check your `tax_region` and pension contribution percentages.
3. **Pension projection.** The projected-at-retirement number is sensitive to risk profile and fees. If it's wildly optimistic or pessimistic, revisit `risk_profile` and `investment_fees`.
4. **Goal feasibility.** If everything is "on track" and you have low savings, the required-monthly math is probably assuming unrealistic growth. Check the assumption for expected return by risk profile.
5. **Score breakdown.** Always read the seven category scores, not just the composite. One catastrophic category (e.g., 15/100 on insurance) hidden by six decent categories can hide a real fire.

If anything looks off, compare against the CLI Markdown report — that's the raw engine output, easier to scan than the dashboard.

## Next steps after your first run

- Export your report (PDF or XLSX buttons where present) for future comparison
- Save your profile file somewhere you'll remember (outside the repo is fine)
- Re-run quarterly — the [History](api-reference.md#history) endpoint lets you diff runs over time
- If something looks wrong in the analysis itself (not just your inputs), flag it — ideally with a minimal reproducing profile in a bug report
