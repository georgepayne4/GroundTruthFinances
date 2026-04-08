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
    """
    txn_date: date
    description: str
    amount: float
    bank: str
    category: str | None = None
    sub_category: str | None = None
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


BANK_FORMATS: tuple[BankFormat, ...] = (
    BankFormat(
        name="monzo",
        required_headers=("Date", "Name", "Amount", "Category"),
        date_field="Date",
        description_field="Name",
        amount_field="Amount",
        date_formats=("%d/%m/%Y", "%Y-%m-%d"),
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
    ),
    BankFormat(
        name="natwest",
        required_headers=("Date", "Type", "Description", "Value"),
        date_field="Date",
        description_field="Description",
        amount_field="Value",
        date_formats=("%d/%m/%Y",),
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
    """
    # Pre-compile prefix-anchored word-boundary regexes for each keyword
    flat_rules: list[tuple[re.Pattern[str], str, str]] = []
    for category, sub_map in rules.items():
        for sub_key, keywords in sub_map.items():
            for kw in keywords:
                pattern = re.compile(rf"\b{re.escape(kw)}", re.IGNORECASE)
                flat_rules.append((pattern, category, sub_key))

    matched = 0
    for txn in transactions:
        if txn.amount >= 0:
            continue  # only categorise outflows
        for pattern, category, sub_key in flat_rules:
            if pattern.search(txn.description):
                txn.category = category
                txn.sub_category = sub_key
                matched += 1
                break

    logger.info("Categorised %d/%d outflow transactions", matched, sum(1 for t in transactions if t.amount < 0))
    return transactions


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

    Returns a dict with the generated expenses block plus a summary of what
    was parsed (transaction count, date range, uncategorised count).
    """
    transactions = parse_csv(path)
    rules = load_category_rules(rules_path)
    categorise_transactions(transactions, rules)
    expenses = aggregate_to_expenses(transactions)

    outflows = [t for t in transactions if t.amount < 0]
    uncategorised = [t for t in outflows if not t.category]

    return {
        "expenses": expenses,
        "summary": {
            "transactions_parsed": len(transactions),
            "outflow_count": len(outflows),
            "inflow_count": len(transactions) - len(outflows),
            "uncategorised_count": len(uncategorised),
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

    return Transaction(
        txn_date=txn_date,
        description=description,
        amount=amount,
        bank=fmt.name,
        raw=dict(row),
    )


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
