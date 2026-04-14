# Getting Started

This guide takes you from zero to your first financial analysis in ten minutes.

## 1. Sign up

Visit the GroundTruth sign-in page and create an account with Google or email/password. Authentication is handled by [Clerk](https://clerk.com) — no financial data is shared with them.

!!! note "Dev mode"
    If you're running GroundTruth locally without a Clerk publishable key, the frontend runs in dev mode and skips authentication. API calls fall back to an API key header.

## 2. Build your profile

You have three options:

### Option A — Guided wizard (recommended for first-timers)

From the sidebar, click **Wizard**. The 9-step wizard asks for:

1. **Personal** — age, retirement age, employment type, tax region
2. **Income** — salary, partner income, side income
3. **Expenses** — housing, transport, living costs (with smart defaults from income bracket)
4. **Savings** — emergency fund, ISA, LISA, pension balances and contributions
5. **Debts** — credit cards, loans, student loan (optional)
6. **Goals** — template picker: emergency fund, house deposit, retirement (optional)
7. **Mortgage** — target property, deposit, term (optional)
8. **Life events** — planned changes by year (optional)
9. **Review** — completeness score and run analysis

Progress saves to your browser automatically. You can leave and resume within 30 days.

### Option B — YAML/JSON profile editor

From the sidebar, click **Settings**. Paste a profile in the editor and click **Analyse**. See the [Profile Guide](profile-guide.md) for the complete schema.

### Option C — Import from bank CSV

If you bank with Monzo, Starling, Barclays, HSBC, Nationwide, Lloyds, or NatWest, export a statement CSV and import it. GroundTruth will auto-populate income and expenses from real transaction data.

Run the CLI:

```bash
python main.py --bank-csv path/to/statement.csv
```

## 3. Run your first analysis

Click **Analyse**. In under two seconds you'll see:

- Your **financial health score** (0-100, graded A+ to F)
- **Monthly surplus** — the gap between income and essential spending
- **Net worth** trajectory and priority actions

Navigate through the sidebar pages for deeper analysis — cashflow breakdown, debt strategies, goal feasibility, investment projections, mortgage readiness, stress scenarios.

## 4. Export your data

From the **Profile** page:

- **Download my data** — full JSON export of everything GroundTruth holds about you (GDPR right to access)
- **PDF/CSV/XLSX** reports — under the export buttons on each analysis page

## 5. Re-run regularly

Financial plans age. Re-run when:

- Income or essential expenses change materially (>10%)
- Tax year rolls over (assumptions refresh automatically on the backend)
- You pay off a debt, hit a goal, or change risk appetite
- Life events happen — job change, house purchase, kids, inheritance

## Troubleshooting

**Analysis fails with validation errors.**  
The validator returns severity-graded flags. Fix anything tagged `error` (the pipeline won't run with errors). `warning` and `info` flags are hints — the analysis still runs.

**My score dropped unexpectedly.**  
Open the **History** view (sidebar) and diff against a previous run. GroundTruth tracks timestamped snapshots so you can see exactly what changed.

**Dashboard shows empty state.**  
Your profile didn't save or didn't load. Check the Settings page — if the JSON is present, click Analyse. If empty, re-run the wizard.

**Questions about what a specific number means.**  
Every score, recommendation, and projection is explained in the [User Guide](user-guide/index.md).
