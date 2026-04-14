# Scores & Grades

Every major output has a score. This page explains the methodology so you can interpret numbers with confidence.

## The overall score

A weighted average of seven category scores, each 0-100. The weights sum to 100% and are defined in `config/assumptions.yaml` under `scoring.weights`:

| Category | Weight | Headline measure |
|----------|-------:|------------------|
| Cashflow | 20% | Effective savings rate |
| Emergency Fund | 15% | Months of expenses in liquid savings |
| Debt | 15% | Debt-to-income ratio and high-interest exposure |
| Goals | 15% | Feasibility of top-priority goals |
| Investments | 15% | Pension adequacy + portfolio alignment |
| Insurance | 10% | Coverage gaps vs need |
| Retirement | 10% | Income replacement ratio projection |

## Category scoring logic

Each category has its own threshold table. For example, Cashflow:

| Savings rate | Score |
|-------------:|------:|
| 30%+ | 100 |
| 25-29% | 90 |
| 20-24% | 80 |
| 15-19% | 70 |
| 10-14% | 60 |
| 5-9% | 45 |
| 0-4% | 30 |
| Negative | 10 |

Thresholds are chosen to reflect UK population benchmarks, not aspirational. A 20% savings rate scores 80 because it's achievable for most middle-income UK earners; 30%+ scores 100 because it's uncommon and aggressive.

## The grade

| Grade | Score | What it means |
|-------|------:|---------------|
| A+ | 90-100 | Exceptional. Every category healthy. |
| A | 80-89 | Strong. Minor refinements possible. |
| B | 70-79 | Solid. Clear improvement areas but no red flags. |
| C | 60-69 | Adequate. Multiple categories need work. |
| D | 50-59 | At risk. Structural issues present. |
| F | <50 | Critical. Major intervention needed. |

## Why composite scores are dangerous

A single number hides nuance. You can score 75 (B) by excelling in six categories and failing one catastrophically — and the failing category might be the one that ends you (e.g., no emergency fund, or uninsured mortality risk to dependants).

**Always read category scores, not just the composite.** If any category is below 50, treat it as a fire regardless of the overall grade.

## Calibration

Scores are calibrated against UK income deciles using ONS and HMRC distributional data. A median household by income should score roughly 50-60 with typical financial behaviour. Scores above 80 are genuinely uncommon.

If you're scoring A+ and everything looks rosy, sanity-check your inputs. Optimism bias in self-reported financial data is pervasive.

## Not a predictor of future outcomes

A high score means you're well-positioned today. It does not predict wealth in 30 years — that depends on behaviour, discipline, market outcomes, and luck. The score tells you the starting conditions are favourable. The journey is yours.
