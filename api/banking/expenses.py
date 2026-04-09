"""api/banking/expenses.py — Auto-categorised expense summary from bank data (v6.0-02).

Aggregates bank transactions into expense categories, leveraging the existing
import_csv categorisation engine where merchant/description patterns match,
and falling back to TrueLayer's native categories.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.database.models import BankAccount, BankConnection, BankTransaction

logger = logging.getLogger(__name__)


# Map TrueLayer categories to engine expense categories
_CATEGORY_MAP: dict[str, str] = {
    "PURCHASE": "general",
    "DEBIT": "general",
    "DIRECT_DEBIT": "bills",
    "STANDING_ORDER": "bills",
    "ATM": "cash",
    "TRANSFER": "transfers",
    "INTEREST": "interest",
    "CHARGE": "fees",
    "UNKNOWN": "uncategorised",
    # Finer-grained mappings from merchant categorisation
    "food": "food",
    "groceries": "food",
    "eating out": "dining",
    "entertainment": "entertainment",
    "transport": "transport",
    "shopping": "shopping",
    "bills": "bills",
    "health": "health",
    "personal care": "personal_care",
    "charity": "charity",
    "holidays": "holidays",
    "family": "family",
}


@dataclass
class ExpenseCategory:
    """A single expense category summary."""
    category: str
    total: float
    count: int
    average: float
    percentage: float = 0.0


@dataclass
class ExpenseSummary:
    """Auto-categorised expense breakdown from bank transactions."""
    total_spending: float
    categories: list[ExpenseCategory] = field(default_factory=list)
    period_days: int = 0
    monthly_average: float = 0.0
    transaction_count: int = 0


def _map_category(raw_category: str | None, merchant_name: str | None) -> str:
    """Map a TrueLayer/merchant category to an engine expense category."""
    if raw_category:
        mapped = _CATEGORY_MAP.get(raw_category.lower())
        if mapped:
            return mapped
        mapped = _CATEGORY_MAP.get(raw_category.upper())
        if mapped:
            return mapped
    return "uncategorised"


def summarise_expenses(
    db: Session,
    user_id: int,
    days: int = 30,
) -> ExpenseSummary:
    """Aggregate a user's spending into categorised expense summary."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.query(BankTransaction)
        .join(BankAccount, BankTransaction.account_id == BankAccount.id)
        .join(BankConnection, BankAccount.connection_id == BankConnection.id)
        .filter(BankConnection.user_id == user_id, BankConnection.status == "active")
        .filter(BankTransaction.amount < 0)
        .filter(BankTransaction.timestamp >= cutoff)
        .all()
    )

    if not rows:
        return ExpenseSummary(total_spending=0.0, period_days=days)

    # Aggregate by category
    category_totals: dict[str, float] = defaultdict(float)
    category_counts: dict[str, int] = defaultdict(int)

    total_spending = 0.0
    for t in rows:
        cat = _map_category(t.category, t.merchant_name)
        amount = abs(t.amount)
        category_totals[cat] += amount
        category_counts[cat] += 1
        total_spending += amount

    categories = []
    for cat, total in sorted(category_totals.items(), key=lambda x: -x[1]):
        count = category_counts[cat]
        pct = (total / total_spending * 100) if total_spending > 0 else 0
        categories.append(ExpenseCategory(
            category=cat,
            total=round(total, 2),
            count=count,
            average=round(total / count, 2),
            percentage=round(pct, 1),
        ))

    months = max(1, days / 30)
    return ExpenseSummary(
        total_spending=round(total_spending, 2),
        categories=categories,
        period_days=days,
        monthly_average=round(total_spending / months, 2),
        transaction_count=len(rows),
    )
