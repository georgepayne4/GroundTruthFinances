# Goals

A goal is any target: emergency fund, house deposit, kid's university, retirement, sabbatical. GroundTruth allocates your surplus across goals by priority and tells you whether each is reachable.

## Goal feasibility

Each goal is scored:

- **On track** — allocated surplus meets required monthly
- **At risk** — shortfall exists but manageable with adjustment
- **Unreachable** — gap too large to close with current surplus and timeline
- **Blocked** — higher-priority goals consume all available surplus first

## The surplus allocation engine

Goals are funded in **priority order** (1 = highest). Each goal gets its required monthly allocation before lower-priority goals receive anything. This is intentional — GroundTruth won't paper over reality by telling you all goals are half-funded. You either fund the critical goals or you don't.

If your total required monthly exceeds your available surplus, lower-priority goals will be flagged blocked or unreachable until the constraint eases.

## Inflation adjustment

Every goal target is projected in today's pounds. A £30,000 wedding in five years is shown as a higher nominal target to preserve real purchasing power, using the inflation assumption from `config/assumptions.yaml`.

## LISA bonus

If a goal is tagged `house_deposit` or `retirement` and you have LISA contributions, GroundTruth adds the 25% government bonus to your projected accumulation. This is the most powerful compounding mechanism in the UK savings system — the dashboard surfaces it explicitly.

## What would it take?

For at-risk or unreachable goals, GroundTruth computes three ways to close the gap:

- **Increase income** — how much more monthly you'd need to earn
- **Reduce expenses** — how much less monthly you'd need to spend
- **Combined** — a proportional split of both

These aren't recommendations — they're mathematical feasibility options. Use them to negotiate with yourself or a partner about what's realistic.

## Blocked goals

A blocked goal has no allocation because higher-priority goals consumed the surplus. The dashboard tells you **what** is blocking **what**. The fix is either:

1. Increase surplus (earn more, spend less)
2. Reprioritise goals (move the blocked goal up, or demote a higher one)
3. Extend the blocked goal's deadline

## What goals do not show

- **Per-goal risk alignment** — whether the investment vehicle funding the goal matches its time horizon. See [Investments](investments.md) for risk profiling.
- **Tax-efficient sequencing** — which account type to use for each goal. See [Investments](investments.md).
