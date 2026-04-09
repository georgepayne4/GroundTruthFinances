"""
import_csv.py — UK Bank Statement CSV Parser (v5.2-01)

Parses transaction exports from major UK banks into a standardised
schema, auto-categorises spending using keyword matching, and aggregates
into a profile-compatible expenses block.

Supported banks:
- Monzo
- Starling
- Barclays
- HSBC
- Nationwide
- Lloyds
- NatWest

Format detection is by header fingerprinting — the first row of the CSV
is matched against known signatures. If no match, raises ImportCsvError.

No API keys, no cloud calls. Operates on locally downloaded files only.
"""

from __future__ import annotations

import csv
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from engine.exceptions import GroundTruthError

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ImportCsvError(GroundTruthError):
    """Raised when a CSV cannot be parsed or its format is unrecognised."""


# ---------------------------------------------------------------------------
# Transaction model
# ---------------------------------------------------------------------------

@dataclass
class Transaction:
    """A single normalised bank transaction.

    amount: signed — negative for outflows (debits), positive for inflows.
    confidence: 0.0–1.0 score for the auto-categorisation. None if uncategorised.
    payment_method: normalised type — "direct_debit", "standing_order",
        "card", "transfer", or None if the CSV format doesn't expose it.
    """
    txn_date: date
    description: str
    amount: float
    bank: str
    category: str | None = None
    sub_category: str | None = None
    confidence: float | None = None
    payment_method: str | None = None
    raw: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Bank format definitions
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BankFormat:
    """Describes how to parse one bank's CSV format."""
    name: str
    required_headers: tuple[str, ...]   # all of these must appear (case-insensitive)
    date_field: str
    description_field: str
    date_formats: tuple[str, ...]
    # Either a single signed amount field or separate debit/credit fields:
    amount_field: str | None = None
    debit_field: str | None = None
    credit_field: str | None = None
    # v5.2-07: optional payment type column (DD, SO, card, etc.)
    type_field: str | None = None
    type_mapping: dict[str, str] | None = None  # raw value → normalised method


BANK_FORMATS: tuple[BankFormat, ...] = (
    BankFormat(
        name="monzo",
        required_headers=("Date", "Name", "Amount", "Category"),
        date_field="Date",
        description_field="Name",
        amount_field="Amount",
        date_formats=("%d/%m/%Y", "%Y-%m-%d"),
        type_field="Type",
        type_mapping={
            "direct debit": "direct_debit",
            "standing order": "standing_order",
            "card payment": "card",
            "faster payment": "transfer",
            "bank transfer": "transfer",
        },
    ),
    BankFormat(
        name="starling",
        required_headers=("Date", "Counter Party", "Amount (GBP)"),
        date_field="Date",
        description_field="Counter Party",
        amount_field="Amount (GBP)",
        date_formats=("%d/%m/%Y", "%Y-%m-%d"),
    ),
    BankFormat(
        name="barclays",
        required_headers=("Date", "Memo", "Amount"),
        date_field="Date",
        description_field="Memo",
        amount_field="Amount",
        date_formats=("%d/%m/%Y",),
    ),
    BankFormat(
        name="hsbc",
        required_headers=("Date", "Description", "Value"),
        date_field="Date",
        description_field="Description",
        amount_field="Value",
        date_formats=("%d/%m/%Y", "%d %b %Y"),
    ),
    BankFormat(
        name="nationwide",
        required_headers=("Date", "Description", "Paid out", "Paid in"),
        date_field="Date",
        description_field="Description",
        debit_field="Paid out",
        credit_field="Paid in",
        date_formats=("%d %b %Y", "%d/%m/%Y"),
    ),
    BankFormat(
        name="lloyds",
        required_headers=(
            "Transaction Date", "Transaction Description",
            "Debit Amount", "Credit Amount",
        ),
        date_field="Transaction Date",
        description_field="Transaction Description",
        debit_field="Debit Amount",
        credit_field="Credit Amount",
        date_formats=("%d/%m/%Y",),
        type_field="Transaction Type",
        type_mapping={
            "dd": "direct_debit",
            "so": "standing_order",
            "deb": "card",
            "fpi": "transfer",
            "bgc": "transfer",
        },
    ),
    BankFormat(
        name="natwest",
        required_headers=("Date", "Type", "Description", "Value"),
        date_field="Date",
        description_field="Description",
        amount_field="Value",
        date_formats=("%d/%m/%Y",),
        type_field="Type",
        type_mapping={
            "d/d": "direct_debit",
            "dd": "direct_debit",
            "s/o": "standing_order",
            "so": "standing_order",
            "pos": "card",
            "vis": "card",
            "bac": "transfer",
            "chq": "transfer",
        },
    ),
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_csv(path: str | Path) -> list[Transaction]:
    """Parse a bank CSV file into a list of normalised transactions.

    Detects the bank format by header fingerprinting.
    Raises ImportCsvError if the format is unrecognised or rows fail to parse.
    """
    path = Path(path)
    if not path.exists():
        raise ImportCsvError(f"CSV file not found: {path}")

    try:
        with open(path, encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh)
            headers = reader.fieldnames or []
            fmt = _detect_format(headers)
            if fmt is None:
                raise ImportCsvError(
                    f"Unrecognised CSV format. Headers: {headers}. "
                    f"Supported banks: {[f.name for f in BANK_FORMATS]}",
                )
            transactions = [_parse_row(row, fmt) for row in reader]
    except UnicodeDecodeError as e:
        raise ImportCsvError(f"Could not decode CSV (try UTF-8): {e}") from e

    logger.info("Parsed %d transactions from %s (format: %s)", len(transactions), path.name, fmt.name)
    return transactions


def categorise_transactions(
    transactions: list[Transaction], rules: dict[str, dict[str, list[str]]],
) -> list[Transaction]:
    """Assign category and sub_category to each outflow transaction.

    rules format: {category: {sub_category: [keyword1, keyword2, ...]}}
    Keywords are matched at word boundaries (prefix-anchored) so that
    "sainsbury" matches "SAINSBURYS GROCERIES" but "tfl" does not match
    inside "Netflix". First matching rule wins. Inflows are left
    uncategorised.

    Sets a confidence score on each matched transaction:
      1.0  — exact word match (description equals or starts with the keyword)
      0.8  — keyword found at a word boundary in a longer string
      0.5  — fallback for short keywords (<=3 chars) where false positives are likelier
    """
    # Pre-compile prefix-anchored word-boundary regexes for each keyword
    flat_rules: list[tuple[re.Pattern[str], str, str, str]] = []
    for category, sub_map in rules.items():
        for sub_key, keywords in sub_map.items():
            for kw in keywords:
                pattern = re.compile(rf"\b{re.escape(kw)}", re.IGNORECASE)
                flat_rules.append((pattern, category, sub_key, kw))

    matched = 0
    for txn in transactions:
        if txn.amount >= 0:
            continue  # only categorise outflows
        for pattern, category, sub_key, kw in flat_rules:
            if pattern.search(txn.description):
                txn.category = category
                txn.sub_category = sub_key
                txn.confidence = _score_match(txn.description, kw)
                matched += 1
                break

    logger.info("Categorised %d/%d outflow transactions", matched, sum(1 for t in transactions if t.amount < 0))
    return transactions


def detect_income_transactions(
    transactions: list[Transaction], min_amount: float = 500.0,
) -> list[Transaction]:
    """Identify likely salary / regular income credits.

    Heuristic: large positive (>= min_amount) credits whose description
    contains a payroll-style keyword (salary, payroll, wages, employer).
    Returns a list of matching transactions, sorted by date.
    """
    payroll_re = re.compile(
        r"\b(salary|payroll|wages?|employer|paye|net pay)\b", re.IGNORECASE,
    )
    matches = [
        t for t in transactions
        if t.amount >= min_amount and payroll_re.search(t.description)
    ]
    matches.sort(key=lambda t: t.txn_date)
    logger.info("Detected %d likely income transactions", len(matches))
    return matches


def detect_recurring_transactions(
    transactions: list[Transaction],
    min_occurrences: int = 2,
    amount_tolerance_pct: float = 0.10,
) -> list[dict[str, Any]]:
    """Identify recurring outflows (subscriptions, direct debits, loan payments).

    Groups outflows by a normalised description key and reports any group
    where:
      - it appears at least ``min_occurrences`` times, AND
      - the amounts are within ``amount_tolerance_pct`` of the mean.

    Returns a list of dicts: {description, occurrences, mean_amount,
    monthly_estimate, first_seen, last_seen, category, sub_category}.
    Sorted by monthly_estimate descending.
    """
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for txn in transactions:
        if txn.amount >= 0:
            continue
        key = _normalise_merchant(txn.description)
        if key:
            groups[key].append(txn)

    results: list[dict[str, Any]] = []
    for key, txns in groups.items():
        if len(txns) < min_occurrences:
            continue
        amounts = [abs(t.amount) for t in txns]
        mean = sum(amounts) / len(amounts)
        if mean == 0:
            continue
        # All amounts must be within tolerance of mean
        if any(abs(a - mean) / mean > amount_tolerance_pct for a in amounts):
            continue
        dates = sorted(t.txn_date for t in txns)
        span_days = (dates[-1] - dates[0]).days or 30
        # Cadence: estimate average days between occurrences
        cadence_days = span_days / max(1, len(txns) - 1) if len(txns) > 1 else 30
        monthly_estimate = round(mean * (30 / cadence_days), 2) if cadence_days > 0 else mean
        first_txn = txns[0]
        results.append({
            "description": first_txn.description,
            "merchant_key": key,
            "occurrences": len(txns),
            "mean_amount": round(mean, 2),
            "monthly_estimate": monthly_estimate,
            "cadence_days": round(cadence_days, 1),
            "first_seen": dates[0].isoformat(),
            "last_seen": dates[-1].isoformat(),
            "category": first_txn.category,
            "sub_category": first_txn.sub_category,
        })

    results.sort(key=lambda r: r["monthly_estimate"], reverse=True)
    logger.info("Detected %d recurring transaction groups", len(results))
    return results


_SUBSCRIPTION_KEYWORDS: tuple[str, ...] = (
    "netflix", "spotify", "disney", "amazon prime", "prime video",
    "apple.com", "apple music", "icloud", "youtube", "hulu",
    "google", "google one", "google storage", "microsoft", "office 365",
    "adobe", "creative cloud", "dropbox", "notion", "github",
    "audible", "kindle", "patreon", "substack", "medium",
    "nytimes", "guardian", "ft.com", "telegraph", "the times",
    "now tv", "nowtv", "discovery+", "paramount", "britbox",
    "duolingo", "linkedin", "figma", "1password", "lastpass",
    "expressvpn", "nordvpn", "proton",
)


def detect_subscriptions(
    transactions: list[Transaction],
    recurring_groups: list[dict[str, Any]] | None = None,
    price_drift_pct: float = 0.05,
) -> list[dict[str, Any]]:
    """v5.2-06: Identify recurring outflows that look like subscriptions.

    A subscription is a recurring transaction with:
      - monthly cadence (~25-35 days) or annual cadence (~350-380 days)
      - amount in a plausible subscription range (£1-£500 per charge)
      - merchant name matches a known subscription keyword OR
        sub_category is the dedicated subscriptions bucket

    Detects price drift within a group: if the latest occurrence is
    >price_drift_pct above the earliest, the subscription is flagged
    with previous_amount and current_amount. To capture price changes
    we re-group transactions here with a wider tolerance than the
    base recurring detector allows.

    Returns a list of dicts: {name, merchant_key, monthly_cost,
    charge_amount, frequency, category, sub_category, occurrences,
    first_seen, last_seen, price_changed, previous_amount,
    current_amount, known_merchant}.
    """
    # Re-group with a relaxed tolerance so price-drifted subs are captured.
    relaxed_groups = detect_recurring_transactions(
        transactions,
        min_occurrences=2,
        amount_tolerance_pct=0.50,
    )
    by_key: dict[str, dict[str, Any]] = {g["merchant_key"]: g for g in relaxed_groups}
    if recurring_groups:
        # Prefer the strict-tolerance entry when both exist (more accurate cadence)
        for g in recurring_groups:
            by_key.setdefault(g["merchant_key"], g)

    # Build a quick index of original transactions per merchant key for drift checks
    txn_by_key: dict[str, list[Transaction]] = defaultdict(list)
    for t in transactions:
        if t.amount >= 0:
            continue
        k = _normalise_merchant(t.description)
        if k:
            txn_by_key[k].append(t)

    subs: list[dict[str, Any]] = []
    for key, group in by_key.items():
        cadence = group.get("cadence_days", 0)
        frequency = _classify_cadence(cadence)
        if frequency is None:
            continue
        charge_amount = group.get("mean_amount", 0)
        if not (1.0 <= charge_amount <= 500.0):
            continue

        sub_category = group.get("sub_category") or ""
        is_known = _is_known_subscription_merchant(group.get("description", ""), key)
        is_subs_category = "subscription" in sub_category.lower()
        if not (is_known or is_subs_category):
            continue

        group_txns = sorted(txn_by_key.get(key, []), key=lambda t: t.txn_date)
        price_changed = False
        previous_amount: float | None = None
        current_amount: float = charge_amount
        if len(group_txns) >= 2:
            earliest = abs(group_txns[0].amount)
            latest = abs(group_txns[-1].amount)
            if earliest > 0 and abs(latest - earliest) / earliest >= price_drift_pct:
                price_changed = True
                previous_amount = round(earliest, 2)
                current_amount = round(latest, 2)

        monthly_cost = (
            round(current_amount, 2) if frequency == "monthly"
            else round(current_amount / 12, 2)
        )

        subs.append({
            "name": _clean_subscription_name(group.get("description", key)),
            "merchant_key": key,
            "monthly_cost": monthly_cost,
            "charge_amount": round(current_amount, 2),
            "frequency": frequency,
            "category": group.get("category"),
            "sub_category": group.get("sub_category"),
            "occurrences": group.get("occurrences", len(group_txns)),
            "first_seen": group.get("first_seen"),
            "last_seen": group.get("last_seen"),
            "price_changed": price_changed,
            "previous_amount": previous_amount,
            "current_amount": round(current_amount, 2),
            "known_merchant": is_known,
        })

    subs.sort(key=lambda s: s["monthly_cost"], reverse=True)
    logger.info("Detected %d subscriptions", len(subs))
    return subs


def detect_committed_outflows(
    transactions: list[Transaction],
    min_occurrences: int = 2,
) -> list[dict[str, Any]]:
    """v5.2-07: Identify committed expenses from direct debits and standing orders.

    These are outflows whose payment_method is 'direct_debit' or
    'standing_order'. They represent fixed obligations (utilities, council
    tax, insurance, loan repayments) that are more reliable than card
    spending for estimating true committed monthly costs.

    Returns a list of dicts sorted by monthly amount, with category
    mapping where available: {name, merchant_key, payment_method,
    mean_amount, monthly_amount, occurrences, category, sub_category,
    first_seen, last_seen}.
    """
    committed_methods = {"direct_debit", "standing_order"}
    groups: dict[str, list[Transaction]] = defaultdict(list)
    for txn in transactions:
        if txn.amount >= 0 or txn.payment_method not in committed_methods:
            continue
        key = _normalise_merchant(txn.description)
        if key:
            groups[key].append(txn)

    results: list[dict[str, Any]] = []
    for key, txns in groups.items():
        if len(txns) < min_occurrences:
            continue
        amounts = [abs(t.amount) for t in txns]
        mean = sum(amounts) / len(amounts)
        if mean == 0:
            continue
        dates = sorted(t.txn_date for t in txns)
        first_txn = txns[0]
        results.append({
            "name": _clean_subscription_name(first_txn.description),
            "merchant_key": key,
            "payment_method": first_txn.payment_method,
            "mean_amount": round(mean, 2),
            "monthly_amount": round(mean, 2),
            "occurrences": len(txns),
            "category": first_txn.category,
            "sub_category": first_txn.sub_category,
            "first_seen": dates[0].isoformat(),
            "last_seen": dates[-1].isoformat(),
        })

    results.sort(key=lambda r: r["monthly_amount"], reverse=True)
    logger.info("Detected %d committed outflows (DD/SO)", len(results))
    return results


def aggregate_to_expenses(
    transactions: list[Transaction], months: int | None = None,
) -> dict[str, dict[str, float]]:
    """Aggregate categorised transactions into a profile-compatible expenses block.

    Returns a dict matching the YAML expenses schema:
        {category: {sub_key_monthly: amount, ...}, ...}

    months: number of months the data spans. If None, inferred from txn date range.
    Uncategorised outflows are added to other.miscellaneous_monthly.
    """
    if not transactions:
        return {}

    if months is None:
        months = max(1, _infer_months(transactions))

    totals: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    uncategorised_total = 0.0

    for txn in transactions:
        if txn.amount >= 0:
            continue
        outflow = abs(txn.amount)
        if txn.category and txn.sub_category:
            totals[txn.category][txn.sub_category] += outflow
        else:
            uncategorised_total += outflow

    # Convert sums to monthly averages and round
    expenses: dict[str, dict[str, float]] = {}
    for category, subs in totals.items():
        expenses[category] = {
            sub_key: round(amount / months, 2)
            for sub_key, amount in subs.items()
        }

    if uncategorised_total > 0:
        expenses.setdefault("other", {})
        existing = expenses["other"].get("miscellaneous_monthly", 0)
        expenses["other"]["miscellaneous_monthly"] = round(
            existing + uncategorised_total / months, 2,
        )

    return expenses


def import_bank_csv(
    path: str | Path, rules_path: str | Path | None = None,
) -> dict[str, Any]:
    """End-to-end: parse, categorise, aggregate into a profile expenses block.

    Returns a dict with the generated expenses block, detected income and
    recurring transactions, and a summary of what was parsed (transaction
    count, date range, uncategorised count, average confidence).
    """
    transactions = parse_csv(path)
    rules = load_category_rules(rules_path)
    categorise_transactions(transactions, rules)
    expenses = aggregate_to_expenses(transactions)

    outflows = [t for t in transactions if t.amount < 0]
    uncategorised = [t for t in outflows if not t.category]
    categorised = [t for t in outflows if t.category]
    avg_confidence = (
        round(sum(t.confidence or 0 for t in categorised) / len(categorised), 3)
        if categorised else 0.0
    )

    income = detect_income_transactions(transactions)
    recurring = detect_recurring_transactions(transactions)
    subscriptions = detect_subscriptions(transactions, recurring)
    committed = detect_committed_outflows(transactions)

    return {
        "expenses": expenses,
        "income_transactions": [
            {
                "date": t.txn_date.isoformat(),
                "description": t.description,
                "amount": t.amount,
            }
            for t in income
        ],
        "recurring_transactions": recurring,
        "subscriptions": subscriptions,
        "committed_outflows": committed,
        "summary": {
            "transactions_parsed": len(transactions),
            "outflow_count": len(outflows),
            "inflow_count": len(transactions) - len(outflows),
            "uncategorised_count": len(uncategorised),
            "average_confidence": avg_confidence,
            "income_detected_count": len(income),
            "recurring_detected_count": len(recurring),
            "subscription_count": len(subscriptions),
            "subscription_monthly_total": round(
                sum(s["monthly_cost"] for s in subscriptions), 2,
            ),
            "committed_outflow_count": len(committed),
            "committed_outflow_monthly_total": round(
                sum(c["monthly_amount"] for c in committed), 2,
            ),
            "date_range": _date_range(transactions),
            "months_covered": _infer_months(transactions),
            "bank": transactions[0].bank if transactions else None,
        },
    }


def load_category_rules(path: str | Path | None = None) -> dict[str, dict[str, list[str]]]:
    """Load the category rules YAML. Defaults to config/category_rules.yaml."""
    if path is None:
        path = Path(__file__).resolve().parent.parent / "config" / "category_rules.yaml"
    path = Path(path)
    if not path.exists():
        raise ImportCsvError(f"Category rules file not found: {path}")
    with open(path, encoding="utf-8") as fh:
        rules = yaml.safe_load(fh) or {}
    return rules


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_format(headers: list[str]) -> BankFormat | None:
    """Match a CSV header row against known bank signatures."""
    header_set = {h.strip().lower() for h in headers if h}
    best: BankFormat | None = None
    best_score = 0
    for fmt in BANK_FORMATS:
        required = {h.lower() for h in fmt.required_headers}
        if required.issubset(header_set):
            # Prefer the format that uses the most headers (most specific)
            score = len(required)
            if score > best_score:
                best = fmt
                best_score = score
    return best


def _parse_row(row: dict[str, str], fmt: BankFormat) -> Transaction:
    """Parse a single CSV row into a Transaction using the given format."""
    try:
        txn_date = _parse_date(row.get(fmt.date_field, ""), fmt.date_formats)
        description = (row.get(fmt.description_field) or "").strip()

        if fmt.amount_field:
            amount = _parse_amount(row.get(fmt.amount_field, ""))
        else:
            debit = _parse_amount(row.get(fmt.debit_field or "", "")) if fmt.debit_field else 0.0
            credit = _parse_amount(row.get(fmt.credit_field or "", "")) if fmt.credit_field else 0.0
            amount = credit - debit  # debits become negative outflows
    except (ValueError, KeyError) as e:
        raise ImportCsvError(f"Failed to parse row {row}: {e}") from e

    payment_method = _parse_payment_method(row, fmt)

    return Transaction(
        txn_date=txn_date,
        description=description,
        amount=amount,
        bank=fmt.name,
        payment_method=payment_method,
        raw=dict(row),
    )


def _parse_payment_method(row: dict[str, str], fmt: BankFormat) -> str | None:
    """v5.2-07: extract a normalised payment method from the CSV row.

    Returns one of 'direct_debit', 'standing_order', 'card', 'transfer',
    or None if the format doesn't expose a type column.
    """
    if not fmt.type_field or not fmt.type_mapping:
        return None
    raw_type = (row.get(fmt.type_field) or "").strip().lower()
    return fmt.type_mapping.get(raw_type)


def _parse_date(value: str, formats: tuple[str, ...]) -> date:
    """Parse a date string using the first format that succeeds."""
    value = (value or "").strip()
    if not value:
        raise ValueError("empty date")
    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Could not parse date '{value}' with any of {formats}")


def _parse_amount(value: str) -> float:
    """Parse a money string to float. Empty/blank returns 0.0.

    Handles £ symbols, commas, parentheses for negatives, and trailing CR/DR.
    """
    if value is None:
        return 0.0
    value = str(value).strip()
    if not value:
        return 0.0

    negative = False
    if value.startswith("(") and value.endswith(")"):
        negative = True
        value = value[1:-1]
    if value.endswith(" CR"):
        value = value[:-3]
    elif value.endswith(" DR"):
        negative = True
        value = value[:-3]

    value = value.replace("£", "").replace(",", "").replace(" ", "")
    if not value or value == "-":
        return 0.0

    amount = float(value)
    return -amount if negative else amount


def _score_match(description: str, keyword: str) -> float:
    """Confidence score for a categorisation hit.

    1.0 — description exactly matches the keyword (whitespace-trimmed, lowercase)
    0.9 — description starts with the keyword
    0.8 — keyword length > 3 (specific enough that a word-boundary hit is reliable)
    0.5 — keyword length <= 3 (short, higher false-positive risk)
    """
    desc = description.strip().lower()
    kw = keyword.strip().lower()
    if desc == kw:
        return 1.0
    if desc.startswith(kw):
        return 0.9
    if len(kw) > 3:
        return 0.8
    return 0.5


# Strip card-payment trailers, store IDs, and dates so that
# "TESCO STORES 1234 LONDON 03MAR" and "TESCO STORES 5678 LONDON 17MAR"
# normalise to the same merchant key.
_MERCHANT_NOISE = re.compile(
    r"\b(\d{2,}|ref|payment|purchase|card|visa|mastercard|gbp|"
    r"jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b",
    re.IGNORECASE,
)


def _classify_cadence(cadence_days: float) -> str | None:
    """Map an average inter-transaction gap to a recurrence frequency.

    Returns 'monthly', 'annual', or None if the gap doesn't match a
    plausible subscription cadence.
    """
    if 25 <= cadence_days <= 35:
        return "monthly"
    if 350 <= cadence_days <= 380:
        return "annual"
    return None


def _is_known_subscription_merchant(description: str, merchant_key: str) -> bool:
    """Return True if the description or normalised key matches a known sub provider."""
    haystack = f"{description} {merchant_key}".lower()
    return any(kw in haystack for kw in _SUBSCRIPTION_KEYWORDS)


def _clean_subscription_name(description: str) -> str:
    """Title-case a transaction description for display as a subscription name."""
    cleaned = _MERCHANT_NOISE.sub(" ", description)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.title() if cleaned else description


def _normalise_merchant(description: str) -> str:
    """Reduce a transaction description to a stable merchant key.

    Strips digits, payment-method noise, month abbreviations, and excess
    whitespace, then keeps the first three significant tokens.
    """
    cleaned = _MERCHANT_NOISE.sub(" ", description)
    cleaned = re.sub(r"[^a-zA-Z\s]", " ", cleaned)
    tokens = [t for t in cleaned.lower().split() if len(t) >= 2]
    return " ".join(tokens[:3])


def _infer_months(transactions: list[Transaction]) -> int:
    """Estimate how many months the transaction list covers."""
    if not transactions:
        return 1
    dates = [t.txn_date for t in transactions]
    span_days = (max(dates) - min(dates)).days
    return max(1, round(span_days / 30))


def _date_range(transactions: list[Transaction]) -> dict[str, str] | None:
    """Return the {start, end} ISO date range of a transaction list."""
    if not transactions:
        return None
    dates = [t.txn_date for t in transactions]
    return {"start": min(dates).isoformat(), "end": max(dates).isoformat()}
