# Cashflow

Cashflow is the foundation of every other number on the dashboard. If the cashflow is wrong, everything downstream is wrong.

## Income

| Field | What it includes |
|-------|------------------|
| Primary gross annual | Salary before tax/NI, plus bonuses, plus commission |
| Partner gross annual | Partner's equivalent |
| Other income | Rental, dividends, interest, side income |

GroundTruth calculates tax and NI using HMRC 2025/26 rates (England or Scotland depending on your `tax_region`), with full handling of:

- Personal allowance taper above £100k (loses £1 for every £2 over)
- NI primary threshold (£12,570) and upper earnings limit (£50,270)
- Dividend allowance (£500) and rates (8.75% / 33.75% / 39.35%)
- Pension contribution relief at marginal rate
- Scottish six-band income tax

## Deductions

- **Income tax** and **NI** on earned income
- **Other income tax** (dividends, savings interest above PSA)
- **Pension contributions** — both personal (tax-relieved) and employer

## Net income

Annual and monthly take-home after all deductions. This is what actually lands in your bank account.

## Expenses

The expense waterfall shows monthly spending by category. The category breakdown is drawn from your profile's `expenses` section:

- Housing (rent/mortgage, council tax, utilities, insurance)
- Transport (car, fuel, public transport)
- Food (groceries, dining out)
- Living (subscriptions, personal care, entertainment)
- Other (anything not in the above)

## Surplus

**Surplus = Net income − Expenses − Minimum debt servicing**

This is the amount available each month to deploy toward goals, debt overpayments, pension boosts, or savings. If surplus is negative, you're drawing down wealth — the dashboard will flag this clearly.

## Savings rate

Two definitions, both shown:

- **Basic savings rate** = (Net income − Expenses) / Net income. The simplest read.
- **Effective savings rate** = (Net income − Expenses + Pension contributions) / (Net income + Pension contributions). Includes retirement savings.

For UK earners, 20%+ effective is healthy. 30%+ is aggressive. Below 10% warrants scrutiny.

## Spending benchmarks

The comparisons section shows each expense category as a percentage of net income alongside typical benchmarks (e.g., housing 25-30%, food 10-15%). A red "above benchmark" flag doesn't mean you're overspending — it means your profile differs from the population norm. Interpret with context.

## What cashflow does not show

- **Where surplus should go** — see the [Home](home.md) priority actions or the [Goals](goals.md) page
- **Expense category trends over time** — future feature (v6 drift detection shows planned vs actual)
