# Scenarios

Stress tests. The deterministic projection tells you the central case. This page tells you how fragile that case is.

## Job loss

How long can you survive on liquid savings if income stops?

- **Monthly burn rate** — essential expenses you can't skip
- **Liquid savings** — emergency fund available immediately
- **Months of runway** — savings divided by burn
- **Assessment** — critical (<3 months), concerning (3-6), healthy (6-12), strong (12+)

Three sub-scenarios show total cost and shortfall assuming unemployment for 3, 6, and 12 months. If any show a shortfall, the recommendation is to increase your emergency fund before any other financial goal.

## Interest rate shock

Applicable if you have a mortgage. Shows your monthly payment and affordability at:

- **Base rate** — current fixed rate
- **+1%** — modest shock
- **+2%** — significant shock
- **+3%** — FCA stress test standard

Each scenario shows:

- New monthly payment
- Affordability % (payment / net income)
- Post-mortgage surplus
- Whether you'd be in deficit

If +2% puts you in deficit, you're overleveraged for the current rate environment.

## Market downturn

Applicable if you have investments. Shows portfolio value after:

- **-10% drawdown** — normal correction
- **-20% drawdown** — recession territory
- **-30% drawdown** — severe (2008-level)
- **-40% drawdown** — once-a-generation (2000 dot-com, 2008, 1929)

The recommendation depends on your time horizon. If you're 30 years from retirement, a -40% drawdown is buying opportunity. If you're 2 years out, it's catastrophic — consider de-risking.

## Compound scenarios

The most sophisticated analysis GroundTruth runs. Rather than one-variable stress tests, compound scenarios combine multiple simultaneous shocks:

- **Recession + rate hike** — unemployment risk up, mortgage servicing up, investments down
- **Stagflation** — high inflation, low growth, bond rout
- **Boom** — low rates, high growth, asset inflation
- **Policy shift** — tax changes, pension rule changes

Each branch has:

- **Probability** (summing to 1.0 across branches)
- **Nudge category** — what kind of macro environment this represents
- **Results** — score, grade, surplus, NPV, per-goal feasibility
- **Score delta** vs baseline

The **expected value** row is the probability-weighted average across branches. This is the single most honest number in financial planning — it captures the fact that no future is certain.

## How to read the compound results

- If **score_delta** is consistently negative across all branches, your plan is fragile — small shocks break it.
- If a single branch (e.g., recession) produces a catastrophic delta while others are benign, that's your primary risk. Insure or hedge against that specific scenario.
- **NPV surplus** is the discounted value of your lifetime cashflow surplus under each branch. Compare NPVs — high-variance NPVs mean a lot of your projected wealth depends on the economy cooperating.

## What scenarios do not show

- **Personal black swans** — death, disability, divorce. See the insurance module and review your coverage.
- **Custom shocks** — the branches are defined in `config/assumptions.yaml`. If you want to model a specific scenario (e.g., "what if I lose my job for 2 years AND markets drop 30%?"), use the API with a custom profile.
