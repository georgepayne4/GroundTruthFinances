# Mortgage

For many UK users, a home is the largest financial decision they'll ever make. This page tells you whether you're ready, what you can afford, and how to structure the mortgage.

!!! info "Not applicable?"
    If your profile has no mortgage intent (no `target_property_value`), this page shows only existing mortgage details if applicable.

## Readiness checklist

Three outcomes:

- **Ready** — you can proceed
- **Blockers** — specific issues to resolve first (e.g., "deposit short by £12,000", "debt-to-income too high")
- **Strengths** — what you have going for you

Use blockers as a to-do list.

## Borrowing capacity

- **Income used** — the income the lender will consider (typically primary + partner + some bonus/side)
- **Income multiple** — e.g., 4.5× for a joint application with no dependants
- **Max borrowing gross** — the naive multiple
- **Max borrowing adjusted** — after affordability stress tests
- **Required mortgage** — target property value minus deposit
- **Can borrow enough?** — binary

## Deposit

- **Required at preferred LTV** — the deposit you need (e.g., 15% for an 85% LTV mortgage)
- **Available for deposit** — from your profile's `savings.deposit_available`
- **Gap** — shortfall
- **Months to save gap** — at current surplus, how long to close the gap

## Monthly repayment

- **Monthly repayment** — principal + interest
- **Replaces rent** — how much of your current housing cost it replaces
- **Net monthly change** — the delta to your cashflow
- **Post-mortgage surplus** — what's left after housing

If post-mortgage surplus is negative, the property is unaffordable at this price point.

## Affordability

- **Repayment-to-income** — monthly payment / net monthly income
- **Stress test** — same ratio if rates rise by 3% (most UK lenders stress at +3%)
- **Affordable?** — passes the 45% rule of thumb
- **Stress test passes?** — binary

## LTV bands

A table showing repayment, interest, and monthly payment at different LTVs (95%, 90%, 85%, 80%, 75%, 60%). Each band represents a rate tier — LTV below 75% typically gets the best rate, and below 60% rarely saves more.

Use this to see: *"If I scrape together another £10k for a 15% deposit, do I save enough interest to make it worthwhile?"* — usually yes.

## Overpayment scenarios

For each extra £100-500/month in overpayments:

- **New payoff years** — total term
- **Months saved** — vs original term
- **Total interest saved** — lifetime savings
- **Exceeds 10% limit?** — most fixed-rate UK mortgages cap annual overpayments at 10% of the balance; exceeding triggers ERC penalties

## What mortgage does not show

- **Product selection** — GroundTruth uses indicative rates, not live product data. See a broker for actual deals.
- **Leaseholder ground rent / service charge impact** — include these in your `expenses.housing` for accuracy
- **Shared ownership stamp duty quirks** — supported but use the shared ownership profile flag
