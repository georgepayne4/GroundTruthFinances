# Assumptions Guide

Every calculation GroundTruth performs depends on a set of assumptions: tax bands, inflation rates, expected returns, scoring weights, benchmark thresholds. These are centralised in `config/assumptions.yaml` — the single source of truth.

## Why assumptions matter

Financial projections are functions of inputs and assumptions. The input is your profile. The assumption is everything else: the rate of inflation, the return on equities, the taper of personal allowance above £100k, the band at which higher-rate tax kicks in.

Changing an assumption changes the output. A 1% shift in expected equity returns compounds to tens of thousands of pounds over a 30-year horizon.

GroundTruth makes assumptions **explicit, sourced, and configurable** — never buried in code.

## The assumptions file

Located at `config/assumptions.yaml` (419 lines). Every value has a comment citing its source.

Structure (top-level keys):

```yaml
tax:                    # HMRC 2025/26 income tax, NI, dividend, CGT
scotland:               # Scottish six-band income tax
pension:                # Annual allowance, taper, state pension, lifetime cap
isa:                    # Annual allowances (ISA, LISA, JISA)
investment_returns:     # Expected return by risk profile
inflation:              # CPI projection
mortgage:               # Stamp duty bands, LTV tiers, stress-test rates
scoring:                # Category weights and threshold tables
insurance:              # Cost estimates by age/cover
child_costs:            # Cost per year by age band
student_loans:          # Plan 1/2/3 thresholds and rates
lifetime_cashflow:      # Phase definitions
withdrawal:             # Drawdown sequencing rules
iht:                    # Nil-rate bands, RNRB taper, gift strategy
scenarios:              # Compound scenario definitions
legal:                  # Disclaimers, regulatory classification
```

## Key assumption categories

### Tax (HMRC 2025/26)

- **Personal allowance:** £12,570 (tapered above £100k)
- **Basic rate:** 20% on £12,570-£50,270
- **Higher rate:** 40% on £50,270-£125,140
- **Additional rate:** 45% above £125,140
- **NI primary threshold:** £12,570
- **NI upper earnings limit:** £50,270
- **NI main rate:** 8%; above UEL: 2%
- **Dividend allowance:** £500
- **Savings allowance:** £1,000 (basic rate) / £500 (higher rate)
- **CGT allowance:** £3,000
- **CGT rates:** 10/18% basic / 20/24% higher

### Scotland

Six income tax bands starting at 19% (starter) up to 48% (top). Personal allowance rules align with rUK.

### Pensions

- **Annual allowance:** £60,000 (tapered down to £10,000 above £260k adjusted income)
- **Tax-free lump sum (PCLS):** 25% up to £268,275
- **State pension (full new):** £11,502/year (2025/26)
- **Minimum pension age:** 55 rising to 57 in 2028

### Investment returns

Default expected real returns by risk profile:

| Profile | Real return p.a. | Volatility |
|---------|-----------------:|-----------:|
| Conservative | 2.5% | 8% |
| Moderate | 4.5% | 13% |
| Aggressive | 6.0% | 18% |
| Very aggressive | 7.0% | 22% |

Sourced from long-run UK equity/gilt/cash return studies (Credit Suisse Global Investment Returns Yearbook, Barclays Equity-Gilt Study).

### Inflation

CPI assumed at 2.0% (Bank of England target). Projections inflate goal targets and deflate nominal future values.

### Mortgage

- **Stamp duty bands:** England 2025/26 (5% first-time buyer threshold £425k)
- **LTV tiers:** 95%, 90%, 85%, 80%, 75%, 60% with indicative rate premiums
- **Stress test:** +3% above product rate (FCA standard)
- **Income multiple (LTI):** 4.5× for most lenders, 5.5× for high earners

### Scoring weights

Sum to 100%. Adjustable for experimentation but changes should be deliberate:

```yaml
scoring:
  weights:
    cashflow: 20
    emergency_fund: 15
    debt: 15
    goals: 15
    investments: 15
    insurance: 10
    retirement: 10
```

## Staleness detection

Assumptions have effective dates. If the current date is past an assumption's `effective_to`, it's stale. Endpoints flag this:

```bash
curl http://localhost:8000/api/v1/assumptions/status
```

Returns per-category staleness status. Stale assumptions continue to work — but you should update them at the next tax year rollover (April 6 in the UK).

## Auto-update

`engine/assumption_updater.py` fetches current tax bands, rates, and state pension figures from:

- **HMRC API** — tax bands, NI thresholds, allowances
- **Bank of England** — base rate, inflation
- **ONS** — CPI, wage growth

Run manually:

```bash
python -m engine.assumption_updater
```

Or via the API diff endpoint:

```bash
curl -X POST http://localhost:8000/api/v1/assumptions/diff \
  -H "Content-Type: application/json" \
  -d @proposed-assumptions.yaml
```

This returns a diff showing every changed value without committing. Review before applying.

## Verifying assumptions

Every assumption has a source comment. Example:

```yaml
tax:
  personal_allowance: 12570  # HMRC 2025/26
  basic_rate: 0.20           # HMRC 2025/26
  basic_threshold: 50270     # HMRC 2025/26
```

To verify, check the source (HMRC website for tax, BoE for rates, PLSA for pension adequacy targets). All UK-government figures are public.

## When to change assumptions

- **Annual:** after the Spring Budget (March) and Autumn Statement (November), check for announced changes
- **Tax year rollover:** April 6 — update all `HMRC 2025/26` style comments
- **Rate changes:** after Bank of England MPC decisions, update base rate
- **Scoring calibration:** if users systematically score too high or too low, recalibrate thresholds (with documentation)

## Invariants

- Every assumption has a source comment.
- No assumption is duplicated — if a value appears in `assumptions.yaml`, it must never also appear as a default in Python code. Engine code reads from assumptions; it never defines its own fallback.
- Adding a new assumption requires updating this guide.

See `CLAUDE.md` in the repository for the full assumptions policy.
