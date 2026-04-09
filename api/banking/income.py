"""api/banking/income.py — Income verification from bank transactions (v6.0-02).

Detects recurring income (salary, freelance, benefits) by analysing
transaction patterns: amount consistency, timing regularity, and description
matching.
"""

from __future__ import annotations

import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from api.database.models import BankAccount, BankConnection, BankTransaction

logger = logging.getLogger(__name__)


@dataclass
class IncomeStream:
    """A detected recurring income source."""
    description: str
    average_amount: float
    frequency: str  # "monthly", "weekly", "irregular"
    occurrences: int
    last_received: str
    confidence: float  # 0.0 - 1.0


@dataclass
class IncomeVerification:
    """Result of income verification analysis."""
    total_monthly_income: float
    streams: list[IncomeStream] = field(default_factory=list)
    analysis_period_days: int = 0
    transaction_count: int = 0


# Patterns that indicate income credits
_INCOME_PATTERNS = [
    re.compile(r"salary|wages|payroll", re.IGNORECASE),
    re.compile(r"hmrc|tax\s*(?:refund|credit)", re.IGNORECASE),
    re.compile(r"pension|annuity", re.IGNORECASE),
    re.compile(r"dividend", re.IGNORECASE),
    re.compile(r"universal\s*credit|child\s*benefit|housing\s*benefit", re.IGNORECASE),
    re.compile(r"freelance|invoice|consulting", re.IGNORECASE),
    re.compile(r"interest\s*(?:paid|earned)", re.IGNORECASE),
    re.compile(r"rental?\s*income", re.IGNORECASE),
]


def _is_income_candidate(amount: float, description: str | None) -> bool:
    """Return True if the transaction looks like income."""
    if amount <= 0:
        return False
    if description:
        for pattern in _INCOME_PATTERNS:
            if pattern.search(description):
                return True
    # Large regular credits (> £100) are potential income
    return amount >= 100.0


def _group_by_description(transactions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group income transactions by normalised description."""
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in transactions:
        desc = (t.get("description") or "").strip()
        # Normalise: collapse whitespace, lowercase
        key = re.sub(r"\s+", " ", desc).lower()
        if not key:
            key = "unknown"
        groups[key].append(t)
    return groups


def _detect_frequency(dates: list[datetime]) -> tuple[str, float]:
    """Detect payment frequency from a list of dates. Returns (frequency, confidence)."""
    if len(dates) < 2:
        return "irregular", 0.3

    dates_sorted = sorted(dates)
    gaps = [(dates_sorted[i + 1] - dates_sorted[i]).days for i in range(len(dates_sorted) - 1)]
    avg_gap = sum(gaps) / len(gaps)

    if 25 <= avg_gap <= 35:
        # Monthly — check consistency
        variance = sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)
        confidence = max(0.5, min(1.0, 1.0 - (variance / 100)))
        return "monthly", confidence
    elif 5 <= avg_gap <= 9:
        return "weekly", 0.7
    elif 12 <= avg_gap <= 16:
        return "fortnightly", 0.7
    return "irregular", 0.4


def verify_income(db: Session, user_id: int) -> IncomeVerification:
    """Analyse a user's bank transactions to verify income streams."""
    # Fetch all credits from connected accounts
    rows = (
        db.query(BankTransaction)
        .join(BankAccount, BankTransaction.account_id == BankAccount.id)
        .join(BankConnection, BankAccount.connection_id == BankConnection.id)
        .filter(BankConnection.user_id == user_id, BankConnection.status == "active")
        .filter(BankTransaction.amount > 0)
        .order_by(BankTransaction.timestamp.desc())
        .limit(1000)
        .all()
    )

    if not rows:
        return IncomeVerification(total_monthly_income=0.0)

    # Convert to dicts for processing
    credits = [
        {
            "amount": t.amount,
            "description": t.description,
            "timestamp": t.timestamp,
            "merchant_name": t.merchant_name,
        }
        for t in rows
        if _is_income_candidate(t.amount, t.description or t.merchant_name)
    ]

    # Analysis period
    timestamps = [t.timestamp for t in rows if t.timestamp]
    if not timestamps:
        return IncomeVerification(total_monthly_income=0.0, transaction_count=len(rows))

    period_days = max(1, (max(timestamps) - min(timestamps)).days)

    # Group and analyse
    groups = _group_by_description(credits)
    streams: list[IncomeStream] = []

    for desc_key, txns in groups.items():
        amounts = [t["amount"] for t in txns]
        dates = [t["timestamp"] for t in txns if t["timestamp"]]
        avg_amount = sum(amounts) / len(amounts)

        frequency, confidence = _detect_frequency(dates)

        # Boost confidence if description matches known income patterns
        raw_desc = txns[0].get("description", "")
        if any(p.search(raw_desc or "") for p in _INCOME_PATTERNS):
            confidence = min(1.0, confidence + 0.2)

        streams.append(IncomeStream(
            description=raw_desc or desc_key,
            average_amount=round(avg_amount, 2),
            frequency=frequency,
            occurrences=len(txns),
            last_received=max(dates).isoformat() if dates else "",
            confidence=round(confidence, 2),
        ))

    # Sort by confidence then amount
    streams.sort(key=lambda s: (-s.confidence, -s.average_amount))

    # Estimate monthly income from high-confidence monthly streams
    monthly_total = 0.0
    for s in streams:
        if s.confidence < 0.5:
            continue
        if s.frequency == "monthly":
            monthly_total += s.average_amount
        elif s.frequency == "weekly":
            monthly_total += s.average_amount * 4.33
        elif s.frequency == "fortnightly":
            monthly_total += s.average_amount * 2.17
        elif s.frequency == "irregular" and s.occurrences >= 3:
            # Annualise and divide by 12
            months = max(1, period_days / 30)
            monthly_total += (s.average_amount * s.occurrences) / months

    return IncomeVerification(
        total_monthly_income=round(monthly_total, 2),
        streams=streams,
        analysis_period_days=period_days,
        transaction_count=len(rows),
    )
