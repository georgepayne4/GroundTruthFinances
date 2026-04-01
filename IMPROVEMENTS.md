# GroundTruth Finances — Improvement Plan (Phase 3)

This document is a comprehensive implementation guide for the next session. It contains all context needed to complete every improvement without needing to re-analyse the codebase.

## Project State Summary

**Repo:** https://github.com/georgepayne4/GroundTruthFinances
**Engine version:** 2.0.0 (4,699 lines across 17 files)
**Last commit:** `abf5b9e` — "Add advisor-grade features..."

### Architecture

```
main.py                  — Pipeline orchestrator (14 steps)
config/
  assumptions.yaml       — All financial parameters (tax, inflation, rates, thresholds)
  sample_input.yaml      — Example profile (Alex Morgan)
  george_input.yaml      — Real profile (George Payne, age 26, £71k salary)
engine/
  loader.py              — YAML loading, normalisation, computed fields (_total_liquid, _net_worth)
  validator.py           — Input validation, cross-field checks
  cashflow.py            — Tax/NI calculation, surplus, savings rate
  debt.py                — Student loan (income-contingent) + standard debt analysis
  goals.py               — Feasibility, LISA bonus projection, surplus allocation
  investments.py         — Portfolio projections, pension adequacy, state pension
  mortgage.py            — Borrowing capacity, LTV tiers, stamp duty, acquisition costs
  life_events.py         — Year-by-year trajectory simulation
  insurance.py           — Life/income protection/critical illness gap assessment
  scenarios.py           — Stress tests (job loss, rate shock, market, inflation, income cut)
  scoring.py             — 7-category composite score (age-adjusted)
  insights.py            — Advisor insights, tax optimisation, conflict detection
  report.py              — JSON report assembly
```

### Data Flow

```
Profile YAML → loader → validator → cashflow → debt → goals → investments
  → mortgage → insurance → life_events → scoring → scenarios → insights → report
```

Each module receives `profile` and `assumptions` dicts plus outputs from prior modules. Results are assembled into `outputs/report.json`.

### Key Design Patterns
- All financial parameters in `assumptions.yaml` (never hardcoded in engine)
- Profile YAML has computed fields added by loader (prefixed with `_`)
- Each engine module returns a dict consumed by downstream modules and the report
- Insights are template-driven: condition checks → formatted strings
- `main.py` prints a console summary; full detail is in the JSON report

### User Profile Context (George Payne)
- Age 26, single, no dependents, £71k gross salary
- Very aggressive risk profile
- Student loans: Plan 2 (£29.5k) + Plan 3 (£7.8k) — income-contingent
- Credit cards: 2x Amex at 34.6% APR (£990 total)
- Savings: S&S ISA General Pot £12k (JP Morgan), Rainy Day Pot £4.2k (JP Morgan), LISA £20.5k
- Pension: £20.7k, 3% personal + 6% employer
- Goals: emergency fund (1yr), travel fund (2yr), first home £450k (3yr), investment fund (5yr)
- Life events: promotion Y1, travel break Y2, home purchase Y3, child Y5, childcare Y6

---

## PHASE 3A: FINANCIAL ADVISOR IMPROVEMENTS

### FA-1: Tax on pension withdrawal

**Problem:** `investments.py` projects retirement income at `pension_real × 4%` but doesn't deduct income tax. 75% of pension withdrawals are taxable as income. The projected £63k/yr income would actually be ~£50k after tax.

**Implementation:**
1. In `investments.py`, after calculating `estimated_annual_pension_income`:
   - Calculate 25% tax-free lump sum option: `pension_at_retirement_real × 0.25`
   - Remaining 75% = drawdown pot
   - Apply income tax bands to the annual drawdown income (reuse `_calculate_income_tax` from `cashflow.py` or create shared helper)
   - State pension is also taxable — add it to the taxable income calculation
   - Report both gross and net retirement income
2. Add to return dict: `tax_free_lump_sum`, `annual_income_gross`, `annual_income_net`, `effective_tax_rate_in_retirement`
3. Update `insights.py` `_investment_insights` to reference net income, not gross

**Files:** `engine/investments.py`, `engine/insights.py`
**Consider:** Extract `_calculate_income_tax` from `cashflow.py` into a shared `engine/tax.py` utility to avoid duplication.

---

### FA-2: "What would it take" calculator

**Problem:** Goals classified as "unreachable" just say "extend deadline or increase income" — not actionable. Premium advisors quantify the gap.

**Implementation:**
1. In `goals.py`, for each goal with feasibility != "on_track", calculate:
   - `income_increase_needed`: additional monthly income to close the gap
   - `expense_reduction_needed`: monthly expense cut to close the gap
   - `extended_deadline_months`: how many months the deadline needs to be pushed out at current surplus
   - `combined_adjustment`: "earn £X more + save £Y = achievable"
2. Add these fields to each goal's analysis dict
3. Update `insights.py` `_goal_insights` to include: "To make '{goal}' achievable, you would need to either earn £X more per month, cut expenses by £Y, or extend the deadline to {Z} months."

**Files:** `engine/goals.py`, `engine/insights.py`

---

### FA-3: Childcare tax relief (Tax-Free Childcare)

**Problem:** Life events include childcare costs (£2,400/mo from Year 6) but don't model the 20% government top-up available through Tax-Free Childcare (worth up to £2,000/year per child).

**Implementation:**
1. Add to `assumptions.yaml`:
   ```yaml
   childcare:
     tax_free_childcare_pct: 0.20
     max_government_topup_per_child: 2000
     eligible_age_max: 11
   ```
2. In `life_events.py`, when processing events with `monthly_expense_change` > 0 and description containing "childcare" (or add a new event field `type: childcare`):
   - Calculate government top-up: `min(annual_childcare × 0.20, max_topup × num_children)`
   - Reduce effective annual expense by the top-up amount
3. Add to `insights.py` `_tax_optimisation_insights`: flag Tax-Free Childcare eligibility when dependents > 0 or childcare events exist. Quantify the saving.
4. Add 30 hours free childcare (3-4 year olds) as an additional assumption

**Files:** `config/assumptions.yaml`, `engine/life_events.py`, `engine/insights.py`

---

### FA-4: Windfall / inheritance life events

**Problem:** Life events only model outflows (expenses, income changes). There's no way to model an inheritance, gift, redundancy payout, or other lump-sum inflow.

**Implementation:**
1. Add `one_off_income` field to life event schema (alongside existing `one_off_expense`)
2. In `life_events.py` `simulate_life_events`, when processing events:
   ```python
   one_off_income = ev.get("one_off_income", 0)
   state.liquid_savings += one_off_income
   ```
3. Update `sample_input.yaml` with an example:
   ```yaml
   - year_offset: 7
     description: "Expected inheritance"
     one_off_income: 50000
   ```
4. Update conflict detection in `insights.py` to account for inflows when calculating aggregate feasibility

**Files:** `engine/life_events.py`, `config/sample_input.yaml`, `engine/insights.py`

---

### FA-5: Quarterly review accountability

**Problem:** The report is a one-shot snapshot. Premium advisors build in review triggers.

**Implementation:**
1. Add a new section to the report output: `review_schedule`
2. In `insights.py`, add `_generate_review_triggers`:
   - Next review date: 3 months from generation date
   - Key metrics to re-check: surplus, emergency fund months, debt balances, goal progress %
   - Trigger conditions: "If savings rate drops below 15%, investigate immediately"
   - Milestone alerts: "By Q2, credit card debt should be cleared. If not, review spending."
   - Calculate specific targets for each quarter based on trajectory
3. Add to report via `report.py`

**Files:** `engine/insights.py`, `engine/report.py`

---

### FA-6: Employer pension match optimisation

**Problem:** George contributes 3% personal with 6% employer. Many schemes offer matching tiers (e.g. employer matches up to 5%). The engine doesn't check if increasing personal contributions would unlock more employer money.

**Implementation:**
1. Add optional `pension_employer_match_cap_pct` field to profile savings section
2. In `investments.py`, if personal < match_cap, calculate:
   - Additional personal contribution to max the match
   - Free employer money being left on the table
   - Net cost after tax relief
3. Add to `insights.py` tax optimisation: "You're contributing 3% but your employer will match up to X%. Increasing to X% costs you £Y/month after tax relief but gains £Z/month in employer contributions."

**Files:** `engine/investments.py`, `engine/insights.py`, profile YAML schema

---

### FA-7: Estate & inheritance tax modelling

**Problem:** No IHT awareness. For property owners, the nil-rate band (£325k) + residence nil-rate (£175k) = £500k threshold matters.

**Implementation:**
1. Add to `assumptions.yaml`:
   ```yaml
   inheritance_tax:
     nil_rate_band: 325000
     residence_nil_rate: 175000
     rate: 0.40
     spousal_exemption: true
   ```
2. New function in `insights.py` or new `engine/estate.py`:
   - Project estate value at life expectancy (property + investments + pension death benefits - debts)
   - Calculate potential IHT liability
   - Flag if estate exceeds nil-rate band
   - Suggest will/LPA if not in place (add `has_will` and `has_lpa` to profile personal section)
3. Add estate planning insights

**Files:** New `engine/estate.py` or add to `insights.py`, `config/assumptions.yaml`, profile schema

---

### FA-8: Self-employment support

**Problem:** No handling of self-employed income (Class 2/4 NI, quarterly payments, business expenses).

**Implementation:**
1. Add `employment_type` to profile personal section: `employed | self_employed | contractor | mixed`
2. In `cashflow.py`:
   - If self-employed: apply Class 4 NI (9% on profits £12,570-£50,270, 2% above) instead of employee NI
   - Add Class 2 NI (£3.45/week if profits > £12,570)
   - Allow business expenses deduction from gross income
   - Calculate quarterly tax payments and their cashflow impact
3. Add `business_expenses_annual` to income section of profile
4. Update `mortgage.py`: flag self-employed status (lenders require 2-3 years accounts)

**Files:** `engine/cashflow.py`, `engine/mortgage.py`, `config/assumptions.yaml`, profile schema

---

### FA-9: Bonus / variable income handling

**Problem:** No way to model "base £60k + 10-20% bonus." Variable income affects mortgage affordability, tax band, and savings capacity.

**Implementation:**
1. Add to profile income section:
   ```yaml
   bonus_annual_low: 5000
   bonus_annual_expected: 10000
   bonus_annual_high: 15000
   ```
2. In `cashflow.py`: calculate three scenarios (low/expected/high) for surplus
3. In `mortgage.py`: lenders typically use base salary only, or base + average of last 2-3 years bonus. Add logic to use conservative bonus assumption for borrowing capacity.
4. In `insights.py`: "Your bonus adds £5-15k/year. Direct this to [highest priority goal]. Do not factor bonus into recurring commitments."

**Files:** `engine/cashflow.py`, `engine/mortgage.py`, `engine/insights.py`, profile schema

---

### FA-10: Spending trend & benchmark analysis

**Problem:** Expenses are a single snapshot. No comparison to averages or identification of optimisation opportunities.

**Implementation:**
1. Add UK average spending benchmarks to `assumptions.yaml`:
   ```yaml
   expense_benchmarks:
     housing_pct_of_net: 0.33
     transport_pct_of_net: 0.12
     food_pct_of_net: 0.11
     discretionary_pct_of_net: 0.15
   ```
2. In `cashflow.py` or `insights.py`, compare each expense category to benchmarks as % of net income
3. Flag categories significantly above benchmark: "Your housing costs are 38% of net income vs 33% average. This is the largest drag on your savings capacity."
4. Quantify savings if each over-benchmark category were reduced to benchmark level

**Files:** `engine/insights.py` or `engine/cashflow.py`, `config/assumptions.yaml`

---

## PHASE 3B: MORTGAGE ADVISOR IMPROVEMENTS

### MA-1: Mortgage product comparison (fixed vs tracker)

**Problem:** Single estimated rate used. No comparison of product types.

**Implementation:**
1. Add to `assumptions.yaml`:
   ```yaml
   mortgage_products:
     two_year_fix: { rate: 0.045, fee: 999 }
     five_year_fix: { rate: 0.048, fee: 999 }
     tracker: { rate: 0.042, margin_above_base: 0.01 }
     svr: { rate: 0.075 }
   ```
2. In `mortgage.py`, add `_compare_products` function:
   - For each product: monthly payment, total cost over product term, total cost if held to full mortgage term (switching to SVR after)
   - Break-even analysis between fee vs no-fee products
   - Show cost of 2-year fix + remortgage every 2 years vs 5-year fix
3. Add product comparison section to mortgage output dict
4. Update insights: "A 5-year fix at 4.8% costs £X more per month but protects you from rate rises. Given your tight post-mortgage surplus, stability may be worth more than the £Y saving."

**Files:** `engine/mortgage.py`, `config/assumptions.yaml`, `engine/insights.py`

---

### MA-2: Mortgage overpayment modelling

**Problem:** No modelling of voluntary overpayments (most lenders allow 10%/year penalty-free).

**Implementation:**
1. In `mortgage.py`, add `_overpayment_analysis` function:
   - Input: mortgage amount, rate, term, monthly overpayment amount
   - Calculate: new payoff date, total interest saved, years saved
   - Test scenarios: £100, £200, £500/month overpayment
   - Check against 10% annual overpayment limit (flag if overpayment exceeds)
2. Add to mortgage output and insights
3. Similar structure to `_simulate_extra_payments` in `debt.py` — consider extracting shared amortisation logic

**Files:** `engine/mortgage.py`, `engine/insights.py`

---

### MA-3: Remortgage cliff-edge modelling

**Problem:** What happens when a fixed rate ends? SVR is typically 7-8%. The engine doesn't model this transition.

**Implementation:**
1. In `mortgage.py` `_compare_products` (from MA-1):
   - For each fixed product, model what happens at end of fixed period
   - Show SVR payment shock: "When your 2-year fix ends, your payment jumps from £X to £Y (+£Z/month)"
   - Calculate total cost including remortgage at each renewal point
   - Factor in arrangement fees at each remortgage
2. In `insights.py`: "Budget for remortgage costs every 2-5 years. Set a diary reminder 3 months before your fix ends."

**Files:** `engine/mortgage.py`, `engine/insights.py`

---

### MA-4: Equity growth projection

**Problem:** After purchase, the engine doesn't track how property appreciation + mortgage paydown builds equity.

**Implementation:**
1. In `life_events.py`, after a home purchase event:
   - Track property value growing at housing inflation (4%/year from assumptions)
   - Track mortgage balance reducing via amortisation
   - Calculate equity = property value - mortgage balance at each year
   - Add equity to net worth calculation (currently only liquid + investments - debt)
2. Add `property_value` and `mortgage_balance` and `equity` fields to timeline entries
3. Update `insights.py`: "By Year 10, your property equity is projected to be £X, representing Y% of your net worth."

**Files:** `engine/life_events.py`, `engine/insights.py`

---

### MA-5: Shared Ownership modelling

**Problem:** George's borrowing capacity (£296k) is below his £382k mortgage requirement. Shared Ownership is a legitimate alternative.

**Implementation:**
1. In `mortgage.py`, when `can_borrow_enough` is False, add `_shared_ownership_analysis`:
   - Calculate: what share % is affordable (typically 25-75%)
   - Show: deposit needed on the share, mortgage on the share, rent on the unowned portion
   - Total monthly cost: mortgage + rent + service charge
   - Staircasing: cost to buy additional shares over time
2. Add shared ownership assumptions to `assumptions.yaml`:
   ```yaml
   shared_ownership:
     rent_on_unowned_pct: 0.0275    # 2.75% of unowned share per year
     service_charge_monthly: 150
     min_share_pct: 0.25
   ```
3. Add to mortgage output and insights as an alternative path

**Files:** `engine/mortgage.py`, `config/assumptions.yaml`, `engine/insights.py`

---

### MA-6: Employment type impact on mortgage

**Problem:** Self-employed / contractors face different lender criteria but the engine treats everyone the same.

**Implementation:**
1. Read `employment_type` from profile (added in FA-8)
2. In `mortgage.py`:
   - If self-employed: flag that 2-3 years of accounts required
   - Adjust income multiple (some lenders use 4.0x for self-employed vs 4.5x)
   - Note: net profit used, not turnover
   - If contractor: flag that day rate × 48 weeks × income multiple may be used
3. Add to blockers if self-employed with insufficient history
4. Add to insights: lender-specific guidance

**Files:** `engine/mortgage.py`, `engine/insights.py`

---

### MA-7: Credit score awareness

**Problem:** Credit card balances and multiple applications affect mortgage rates.

**Implementation:**
1. In `mortgage.py`, add credit score risk factors:
   - High credit utilisation (balance / limit > 30%) — flag as negative
   - Multiple recent credit applications — flag
   - Any missed payments — flag
   - Add `credit_utilisation_pct` to profile debts for credit cards
2. Add qualitative credit score warning to mortgage insights
3. Suggest: "Pay credit card balances to zero before mortgage application. Close unused cards 6 months before applying."

**Files:** `engine/mortgage.py`, `engine/insights.py`, profile schema

---

### MA-8: Deposit source documentation

**Problem:** Lenders require evidence of deposit source. Gifted deposits have restrictions.

**Implementation:**
1. Add `deposit_sources` to profile savings or mortgage section:
   ```yaml
   deposit_sources:
     saved: 32528
     gifted: 0
     inherited: 0
   ```
2. In `mortgage.py`: flag if gifted > 0 (requires gifted deposit letter, some lenders don't accept)
3. In `insights.py`: "Ensure you have 3-6 months of bank statements showing savings buildup. Lenders will ask for source of deposit documentation."

**Files:** `engine/mortgage.py`, `engine/insights.py`, profile schema

---

## PHASE 3C: INVESTMENT ADVISOR IMPROVEMENTS

### IA-1: Fee impact modelling

**Problem:** Returns are applied gross. A 1% annual fee on £50k growing at 8% costs ~£175k over 40 years. This is the biggest silent wealth destroyer.

**Implementation:**
1. Add `platform_fee_pct` and `fund_ocf_pct` (ongoing charge figure) to profile savings section:
   ```yaml
   investment_fees:
     isa_platform_fee: 0.0025     # 0.25% (e.g. Vanguard)
     isa_fund_ocf: 0.0012         # 0.12% (e.g. FTSE Global All Cap)
     pension_platform_fee: 0.003
     pension_fund_ocf: 0.002
   ```
2. In `investments.py`:
   - Deduct total fees from expected return: `net_return = gross_return - platform_fee - fund_ocf`
   - Project with and without fees to show the drag
   - Add `fee_drag_over_term` to output: total £ lost to fees over projection period
3. Add to insights: "Investment fees will cost you £X over your working life at current rates. Switching to a low-cost platform could save £Y."
4. Add fee comparison scenarios: current fees vs low-cost (0.15% total) vs high-cost (1.5% total)

**Files:** `engine/investments.py`, `engine/insights.py`, profile schema, `config/assumptions.yaml`

---

### IA-2: Time-horizon-based allocation

**Problem:** One risk profile applied to everything. Your ISA (needed in 3 years for house deposit) should be lower risk than your pension (42 years away).

**Implementation:**
1. In `investments.py`, separate analysis by account type:
   - **Pension (42 years):** Very aggressive appropriate — 90%+ equity
   - **LISA (3 years, earmarked for house):** Should be conservative — 80%+ bonds/cash
   - **ISA General Pot (medium term):** Depends on purpose — moderate
   - **Emergency fund (immediate access):** Must be cash — 100% cash/money market
2. For each account, suggest an allocation based on its time horizon:
   ```python
   if years_to_use <= 2: "cash/money_market"
   elif years_to_use <= 5: "conservative"
   elif years_to_use <= 10: "moderate"
   else: "aggressive" or match risk profile
   ```
3. Add per-account allocation suggestions to output
4. Flag mismatches: "Your emergency fund is in a S&S ISA (market-exposed). Move this to a cash savings account or money market fund."

**Files:** `engine/investments.py`, `engine/insights.py`

---

### IA-3: Emergency fund placement warning

**Problem:** George's Rainy Day Pot (£4,205) is in a JP Morgan S&S ISA — market-exposed. An emergency fund should be instantly accessible and not subject to market risk.

**Implementation:**
1. In `insights.py` or `scoring.py`, check if emergency fund is flagged as market-exposed
2. Add `emergency_fund_type` to profile: `cash | money_market | stocks_and_shares`
3. If stocks_and_shares: add risk warning: "Your emergency fund is invested in equities. A 20% market drop would reduce your buffer from £4,205 to £3,364 at exactly the moment you might need it. Move to a cash or money market account."
4. In scoring: penalise emergency fund score if market-exposed (e.g. -10 points)

**Files:** `engine/insights.py`, `engine/scoring.py`, profile schema

---

### IA-4: Tax-efficient withdrawal sequencing

**Problem:** In retirement, the order you draw from accounts matters hugely for tax. ISA withdrawals are tax-free, pension is 75% taxable, general accounts trigger CGT.

**Implementation:**
1. In `investments.py`, add `_retirement_withdrawal_strategy`:
   - Model optimal drawdown order:
     1. Use pension tax-free lump sum first (25%)
     2. Draw from taxable accounts up to personal allowance
     3. Draw from pension to fill basic rate band
     4. Use ISA to top up (tax-free)
   - Compare naive (all pension) vs optimised strategy
   - Show annual tax saving from optimised sequencing
2. Add withdrawal strategy section to pension_analysis output
3. Add to insights: "By drawing from your ISA and pension strategically, you could save £X/year in retirement tax compared to drawing solely from your pension."

**Files:** `engine/investments.py`, `engine/insights.py`

---

### IA-5: Glide path / age-based de-risking

**Problem:** Static allocation forever. A 26-year-old with 90% equity is fine, but the same allocation at 60 is dangerous.

**Implementation:**
1. In `investments.py`, add `_glide_path_projection`:
   - Define target allocations at key ages: 30 (90% equity), 40 (80%), 50 (65%), 60 (50%), retirement (40%)
   - Project portfolio growth with allocation shifting over time
   - Show the year-by-year allocation change
   - Compare static vs glide path returns (glide path has lower expected return but lower variance)
2. Add to `assumptions.yaml`:
   ```yaml
   glide_path:
     - { age: 30, equity_pct: 0.90 }
     - { age: 40, equity_pct: 0.80 }
     - { age: 50, equity_pct: 0.65 }
     - { age: 60, equity_pct: 0.50 }
     - { age: 67, equity_pct: 0.40 }
   ```
3. Add to insights: "Consider setting up a lifecycle/target-date fund that automatically de-risks as you approach retirement."

**Files:** `engine/investments.py`, `config/assumptions.yaml`, `engine/insights.py`

---

### IA-6: Rebalancing guidance

**Problem:** No guidance on when or how to rebalance a portfolio back to target allocation.

**Implementation:**
1. In `investments.py`, add rebalancing section:
   - Define threshold bands (e.g. rebalance when any asset class drifts >5% from target)
   - Explain calendar rebalancing (annual) vs threshold rebalancing
   - Tax implications: rebalancing within ISA/pension is tax-free; in taxable account triggers CGT
   - Suggest "Bed and ISA": sell in taxable account, rebuy in ISA (crystallises gains within CGT allowance)
2. Add to insights as investment recommendation

**Files:** `engine/investments.py`, `engine/insights.py`

---

### IA-7: Dividend reinvestment & pound-cost averaging

**Problem:** Not modelled or mentioned. These are fundamental investment concepts.

**Implementation:**
1. In `investments.py` growth projections, add a note explaining the assumption (returns assume reinvestment)
2. In `insights.py`, add investment education insights:
   - "Regular monthly investing (pound-cost averaging) reduces the impact of market timing. Set up a standing order to your ISA."
   - "Ensure dividend reinvestment is enabled on all accounts — compounding is the most powerful force in long-term investing."
3. Add a comparison: lump sum vs monthly investing over the projection period (using same total contribution)

**Files:** `engine/investments.py`, `engine/insights.py`

---

### IA-8: Portfolio risk metrics

**Problem:** Just a label (moderate/aggressive). No quantification of volatility or downside risk.

**Implementation:**
1. Add historical risk data to model portfolios in `investments.py`:
   ```python
   MODEL_PORTFOLIOS = {
       "conservative": {
           "allocation": {...},
           "expected_return": 0.04,
           "historical_volatility": 0.06,
           "max_drawdown": -0.15,
           "worst_year": -0.10,
       },
       ...
   }
   ```
2. Add to output: volatility, worst-case year, max drawdown, probability of negative return in any given year
3. Add to insights: "With your very aggressive profile, expect your portfolio to lose value in roughly 1 out of every 4 years. The worst single-year loss could be around 30%. This is normal and expected."

**Files:** `engine/investments.py`, `engine/insights.py`

---

### IA-9: Drawdown vs annuity comparison

**Problem:** Only 4% SWR modelled. Annuities provide guaranteed income and may be appropriate for some.

**Implementation:**
1. Add annuity rate assumptions to `assumptions.yaml`:
   ```yaml
   annuity:
     rate_per_10k_age_60: 550     # £550/year per £10k pot at age 60
     rate_per_10k_age_65: 620
     rate_per_10k_age_67: 660
     rate_per_10k_age_70: 720
   ```
2. In `investments.py`, calculate:
   - Annuity income from pension pot at retirement age
   - Compare to 4% SWR drawdown income
   - Show pros/cons: annuity (guaranteed, no investment risk, but no inheritance) vs drawdown (flexible, inheritable, but market risk)
3. Add to pension_analysis output and insights

**Files:** `engine/investments.py`, `config/assumptions.yaml`, `engine/insights.py`

---

### IA-10: ESG / ethical investing awareness

**Problem:** Not mentioned. Many investors have ethical preferences.

**Implementation:**
1. Add `esg_preference` to profile personal section: `none | preferred | required`
2. In `investments.py`, if ESG preferred/required:
   - Note slightly different return assumptions (ESG funds have historically tracked conventional closely)
   - Suggest ESG fund alternatives for each asset class
3. Add to insights: "ESG/ethical fund options are available for all major asset classes with comparable long-term returns."

**Files:** `engine/investments.py`, `engine/insights.py`, profile schema

---

### IA-11: ISA contribution tracking

**Problem:** ISA balance tracked but annual contribution limit (£20k) not enforced or tracked.

**Implementation:**
1. Add `isa_contributions_this_year` and `lisa_contributions_this_year` to profile savings
2. In `investments.py`:
   - Calculate remaining ISA allowance: £20k - contributions
   - Calculate remaining LISA allowance: £4k - contributions
   - Flag if projected savings exceed ISA allowance (need to use taxable account for excess)
3. Add to insights: "You have £X remaining ISA allowance this tax year. Prioritise filling this before the April deadline."

**Files:** `engine/investments.py`, `engine/insights.py`, profile schema

---

### IA-12: Tax-loss harvesting

**Problem:** Not considered. Selling losses to offset gains within CGT rules.

**Implementation:**
1. In `insights.py` tax optimisation, add:
   - If user has investments outside ISA/pension with unrealised losses:
   - "Consider selling loss-making investments to crystallise losses. These can be offset against gains in the current or future tax years."
   - "Bed and ISA: sell taxable holdings (crystallise gain within CGT allowance), rebuy inside ISA for tax-free growth."
2. This is primarily an insight/education item, not a calculation

**Files:** `engine/insights.py`

---

## IMPLEMENTATION ORDER

Suggested order to maximise impact and minimise conflicts:

### Batch 1 — Structural changes (do first, other tasks depend on these)
1. **FA-4** — Windfall/inheritance life events (adds `one_off_income` field)
2. **FA-8** — Self-employment support (adds `employment_type`, shared tax utility)
3. **FA-1** — Tax on pension withdrawal (extract shared tax helper from cashflow.py)

### Batch 2 — Investment engine overhaul (biggest gap area)
4. **IA-1** — Fee impact modelling
5. **IA-2** — Time-horizon-based allocation
6. **IA-3** — Emergency fund placement warning
7. **IA-5** — Glide path / de-risking
8. **IA-8** — Portfolio risk metrics
9. **IA-4** — Tax-efficient withdrawal sequencing
10. **IA-9** — Drawdown vs annuity comparison

### Batch 3 — Mortgage depth
11. **MA-1** — Product comparison (fixed vs tracker)
12. **MA-2** — Overpayment modelling
13. **MA-3** — Remortgage cliff-edge
14. **MA-4** — Equity growth projection
15. **MA-5** — Shared Ownership

### Batch 4 — Financial advisor refinements
16. **FA-2** — "What would it take" calculator
17. **FA-3** — Childcare tax relief
18. **FA-5** — Quarterly review triggers
19. **FA-6** — Employer pension match optimisation
20. **FA-9** — Bonus / variable income
21. **FA-10** — Spending benchmark analysis

### Batch 5 — Nice-to-haves
22. **FA-7** — Estate / IHT modelling
23. **MA-6** — Employment type mortgage impact
24. **MA-7** — Credit score awareness
25. **MA-8** — Deposit source documentation
26. **IA-6** — Rebalancing guidance
27. **IA-7** — Dividend reinvestment / pound-cost averaging
28. **IA-10** — ESG awareness
29. **IA-11** — ISA contribution tracking
30. **IA-12** — Tax-loss harvesting

---

## TESTING

After each batch, run both profiles to verify no regressions:
```bash
python main.py                                    # sample_input
python main.py --profile config/george_input.yaml  # george_input
```

Check that:
- No Python errors
- Report generates successfully
- New sections appear in report.json
- Console output shows new analysis steps
- Scoring hasn't shifted unexpectedly (compare before/after)

## COMMIT CONVENTION

One commit per batch (or per task if large). Single-line commit messages:
```
Add pension tax, windfall events, self-employment support
Add investment fee modelling, time-horizon allocation, glide path
```
