# UK-Specific Logic Audit

Flags all logic that is specific to UK jurisdiction. For awareness when jurisdiction expansion begins.

## Tax Calculations (`tax.py`)
- Income tax bands: personal allowance, basic/higher/additional rates, PA taper above £100k
- National Insurance: Class 1 (employed), Class 4 (self-employed), Class 2
- Dividend tax: UK-specific allowance and rates
- Capital gains tax: UK annual exemption, residential vs non-residential rates

## Student Loans (`debt.py`)
- Plan 2 and Plan 3 — UK Student Loans Company specific
- Write-off periods (30 years), repayment thresholds, interest rates
- Break-even salary calculations based on SLC thresholds

## Property (`mortgage.py`)
- Stamp Duty Land Tax (SDLT) — England/NI specific; Scotland has LBTT, Wales has LTT
- Shared Ownership model: Homes England scheme rules
- LTV rate tiers: UK mortgage market structure
- Income multiples: FCA MCOB rules

## Pensions (`investments.py`, `cashflow.py`)
- Annual allowance (£60k), tapered AA for high earners
- 25% tax-free lump sum (PCLS)
- Pension withdrawal tax (emergency tax, cumulative)
- State pension: qualifying years, triple lock, deferral rules
- Auto-enrolment minimum contributions

## Savings (`goals.py`, `investments.py`)
- ISA: £20k annual allowance, tax-free growth
- LISA: £4k limit, 25% bonus, £450k property cap, age restrictions
- No equivalent of US 401(k)/IRA/Roth structures

## Insurance (`insurance.py`)
- Life cover multiples based on UK industry norms (ABI guidance)
- Income protection: 60% benefit cap (UK market standard)
- State benefit assumptions (UK welfare system)

## Estate (`estate.py`)
- Inheritance Tax: nil-rate band, RNRB, spousal exemption
- UK probate process assumptions
- Will and LPA costs (OPG registration fees)

## Childcare (`life_events.py`)
- Tax-Free Childcare: UK government scheme (20% top-up, £2k max/child)
- 30 hours free childcare for 3-4 year olds
- Child cost model based on UK cost-of-living data

## Expenses (`cashflow.py`)
- Spending benchmarks: ONS Family Spending Survey (UK averages)
- Council tax (implicit in housing costs)

## General
- All currency: GBP only
- Tax year: April 6 - April 5
- All rates, thresholds, and limits sourced from HMRC/GOV.UK
