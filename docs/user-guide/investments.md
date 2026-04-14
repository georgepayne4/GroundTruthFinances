# Investments

This page covers your portfolio, pension, and long-term wealth trajectory.

## Current portfolio

Total invested split across:

- **ISA** — tax-free growth and withdrawals
- **LISA** — 25% government bonus, 25% exit penalty before 60 (unless first home under £450k)
- **Pension** — tax relief on contributions, taxable on withdrawal
- **Other investments** — GIA, crypto, etc.

## Risk profile

Your stated profile (conservative, balanced, aggressive, etc.) maps to an expected annual return drawn from `config/assumptions.yaml`. GroundTruth then computes:

- **Expected return** — long-run geometric mean
- **Historical volatility** — annualised standard deviation
- **Max drawdown** — worst historical peak-to-trough
- **Worst year** — worst single calendar year
- **Negative year probability** — how often this profile loses money in any given year

If your risk profile is aggressive but your time horizon is short (or vice versa), see the risk mismatch detection on the [Goals](goals.md) page.

## Expected return after fees

**Net return = Gross return − platform fees − fund fees − advice fees**

A 1.5% fee drag over 25 years compounds to losing 30%+ of your terminal wealth. GroundTruth computes this explicitly:

- **Fee drag over term** — pounds lost to fees in today's money
- **Fee comparison** — your fees vs low-cost alternatives (Vanguard, iShares)

If you're paying more than 0.5% total, the recommendation usually is: switch.

## Growth projections

Five-year snapshots showing:

- **Nominal value** — face value at each horizon
- **Real value** — today's pounds after inflation
- **Total contributions** — what you put in
- **Investment growth** — what the market added

Monte Carlo projections (if enabled in your plan tier) add percentile bands — 10th, 50th, 90th — so you see the range of outcomes, not just the mean.

## Pension analysis

The pension block is the most important block on this page for most users:

- **Current balance** — what's in your pot now
- **Annual contributions** — employee + employer combined
- **Projected at retirement** (nominal and real) — what you'll have
- **Tax-free lump sum** (PCLS) — 25% up to the £268,275 lifetime cap
- **Annual income net** — what the remaining pot sustains (4% rule or Guyton-Klinger)
- **Income replacement ratio** — retirement income as % of current net income
- **Adequate?** — whether the projection hits the 70% replacement target
- **Fund longevity** — how many years the pot lasts at the projected withdrawal rate

## Employer match

If your profile includes an employer match and you're contributing below the match threshold, you're turning down free money. GroundTruth flags this as a priority action on the [Home](home.md) page.

## What investments does not show

- **Tax-optimal withdrawal sequencing** — handled by the withdrawal module; see the advisor insights
- **Monte Carlo full distribution** — the API returns this, but the dashboard shows summary statistics; use the JSON export for full detail
