"""api/notifications/triggers.py — Notification trigger evaluation (v6.0-05).

Compares current and previous analysis results to detect events that
warrant user notification. Each trigger is a pure function that returns
a list of alerts.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """A notification to deliver to the user."""
    trigger: str
    severity: str  # "info", "warning", "critical"
    title: str
    message: str
    data: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Score change trigger
# ---------------------------------------------------------------------------

def check_score_change(
    current_report: dict[str, Any],
    previous_report: dict[str, Any] | None,
    threshold: float = 5.0,
) -> list[Alert]:
    """Alert if the overall score changed by more than threshold points."""
    if previous_report is None:
        return []

    current_score = current_report.get("scoring", {}).get("overall_score")
    previous_score = previous_report.get("scoring", {}).get("overall_score")

    if current_score is None or previous_score is None:
        return []

    delta = current_score - previous_score
    if abs(delta) < threshold:
        return []

    direction = "improved" if delta > 0 else "deteriorated"
    severity = "info" if delta > 0 else "warning"

    return [Alert(
        trigger="score_change",
        severity=severity,
        title=f"Score {direction} by {abs(delta):.1f} points",
        message=(
            f"Your financial health score has {direction} from "
            f"{previous_score:.1f} to {current_score:.1f} ({delta:+.1f} points)."
        ),
        data={"previous_score": previous_score, "current_score": current_score, "delta": delta},
    )]


# ---------------------------------------------------------------------------
# Goal deadline trigger
# ---------------------------------------------------------------------------

def check_goal_deadlines(
    report: dict[str, Any],
    warning_months: int = 6,
) -> list[Alert]:
    """Alert for goals approaching deadline with funding gaps."""
    alerts = []
    goals = report.get("goals", {}).get("goals", [])
    today = date.today()

    for goal in goals:
        target_date_str = goal.get("target_date")
        if not target_date_str:
            continue

        try:
            target_date = date.fromisoformat(target_date_str) if isinstance(target_date_str, str) else target_date_str
        except (ValueError, TypeError):
            continue

        months_remaining = (target_date.year - today.year) * 12 + (target_date.month - today.month)
        if months_remaining > warning_months or months_remaining < 0:
            continue

        status = goal.get("status", "")
        if status in ("on_track", "achieved"):
            continue

        gap = goal.get("funding_gap", goal.get("shortfall", 0))
        name = goal.get("name", "Unknown goal")

        alerts.append(Alert(
            trigger="goal_deadline",
            severity="warning" if months_remaining > 3 else "critical",
            title=f"Goal '{name}' deadline in {months_remaining} months",
            message=(
                f"Your goal '{name}' is due in {months_remaining} months "
                f"with a funding gap of £{gap:,.0f}. Consider increasing contributions."
            ),
            data={"goal_name": name, "months_remaining": months_remaining, "gap": gap},
        ))

    return alerts


# ---------------------------------------------------------------------------
# Tax year change trigger
# ---------------------------------------------------------------------------

def check_tax_year_change(
    current_date: date | None = None,
) -> list[Alert]:
    """Alert when a new UK tax year is approaching or has just started.

    UK tax year runs 6 April to 5 April. Alert in March and early April.
    """
    today = current_date or date.today()
    month, day = today.month, today.day

    # March: tax year ending soon
    if month == 3 and day >= 1:
        return [Alert(
            trigger="tax_year_change",
            severity="info",
            title="UK tax year ending soon",
            message=(
                f"The current tax year ends on 5 April {today.year}. "
                "Review your ISA contributions, pension allowances, and CGT utilisation."
            ),
            data={"tax_year_end": f"{today.year}-04-05"},
        )]

    # Early April: new tax year
    if month == 4 and day >= 6 and day <= 30:
        return [Alert(
            trigger="tax_year_change",
            severity="info",
            title="New UK tax year started",
            message=(
                f"Tax year {today.year}/{today.year + 1} has begun. "
                "Assumptions may need updating for new allowances and thresholds."
            ),
            data={"new_tax_year": f"{today.year}/{today.year + 1}"},
        )]

    return []


# ---------------------------------------------------------------------------
# Review schedule trigger
# ---------------------------------------------------------------------------

def check_review_schedule(
    last_run_timestamp: str | None,
    review_interval_days: int = 30,
) -> list[Alert]:
    """Alert when a periodic financial review is due."""
    if not last_run_timestamp:
        return [Alert(
            trigger="review_due",
            severity="info",
            title="Financial review recommended",
            message="No previous analysis found. Run a full analysis to establish your baseline.",
        )]

    try:
        last_run = datetime.fromisoformat(last_run_timestamp)
    except (ValueError, TypeError):
        return []

    days_since = (datetime.now(last_run.tzinfo) - last_run).days
    if days_since < review_interval_days:
        return []

    return [Alert(
        trigger="review_due",
        severity="info" if days_since < review_interval_days * 2 else "warning",
        title=f"Financial review overdue ({days_since} days)",
        message=(
            f"Your last analysis was {days_since} days ago. "
            "Run a fresh analysis to keep your financial picture current."
        ),
        data={"days_since_last_run": days_since, "last_run": last_run_timestamp},
    )]


# ---------------------------------------------------------------------------
# Expense spike trigger (uses bank data from v6.0-02)
# ---------------------------------------------------------------------------

def check_expense_spikes(
    current_expenses: dict[str, Any] | None,
    previous_expenses: dict[str, Any] | None,
    spike_threshold_pct: float = 50.0,
) -> list[Alert]:
    """Alert when spending in a category spikes compared to previous period."""
    if not current_expenses or not previous_expenses:
        return []

    alerts = []
    current_cats = {c["category"]: c for c in current_expenses.get("categories", [])}
    previous_cats = {c["category"]: c for c in previous_expenses.get("categories", [])}

    for cat, current in current_cats.items():
        prev = previous_cats.get(cat)
        if not prev or prev["total"] == 0:
            continue

        pct_change = ((current["total"] - prev["total"]) / prev["total"]) * 100
        if pct_change < spike_threshold_pct:
            continue

        alerts.append(Alert(
            trigger="expense_spike",
            severity="warning",
            title=f"Spending spike in '{cat}': +{pct_change:.0f}%",
            message=(
                f"Your '{cat}' spending increased from £{prev['total']:,.2f} to "
                f"£{current['total']:,.2f} ({pct_change:+.0f}% change)."
            ),
            data={"category": cat, "previous": prev["total"], "current": current["total"], "pct_change": pct_change},
        ))

    return alerts


# ---------------------------------------------------------------------------
# Aggregate evaluator
# ---------------------------------------------------------------------------

def evaluate_all_triggers(
    current_report: dict[str, Any],
    previous_report: dict[str, Any] | None = None,
    last_run_timestamp: str | None = None,
    current_expenses: dict[str, Any] | None = None,
    previous_expenses: dict[str, Any] | None = None,
    score_threshold: float = 5.0,
    review_interval_days: int = 30,
) -> list[Alert]:
    """Run all notification triggers and return combined alerts."""
    alerts: list[Alert] = []
    alerts.extend(check_score_change(current_report, previous_report, score_threshold))
    alerts.extend(check_goal_deadlines(current_report))
    alerts.extend(check_tax_year_change())
    alerts.extend(check_review_schedule(last_run_timestamp, review_interval_days))
    alerts.extend(check_expense_spikes(current_expenses, previous_expenses))

    # Sort by severity: critical > warning > info
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    alerts.sort(key=lambda a: severity_order.get(a.severity, 3))

    return alerts
