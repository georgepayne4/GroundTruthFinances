"""engine/providers.py — Account data provider abstraction (v5.3-06).

Defines a common interface for fetching account and transaction data from
different sources: local CSV files (v5.2-01), Open Banking APIs (future),
or manual entry.

The abstraction isolates the engine from data-source specifics. New providers
implement the AccountProvider ABC and plug into the analysis pipeline.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from engine.import_csv import (
    Transaction,
    aggregate_to_expenses,
    categorise_transactions,
    import_bank_csv,
    load_category_rules,
    parse_csv,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class Account:
    """A normalised bank account representation."""
    account_id: str
    name: str
    institution: str
    account_type: str  # "current", "savings", "credit_card"
    currency: str = "GBP"
    balance: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TransactionPage:
    """A page of transactions from a provider with optional pagination."""
    transactions: list[Transaction]
    total_count: int
    has_more: bool = False
    cursor: str | None = None


# ---------------------------------------------------------------------------
# Abstract provider
# ---------------------------------------------------------------------------

class AccountProvider(ABC):
    """Abstract base for account data providers.

    Subclasses must implement get_accounts() and get_transactions().
    Optional hooks: connect(), disconnect(), refresh().
    """

    @abstractmethod
    def get_accounts(self) -> list[Account]:
        """Return all accessible accounts."""

    @abstractmethod
    def get_transactions(
        self,
        account_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> TransactionPage:
        """Return transactions for an account, optionally filtered by date range."""

    def connect(self) -> None:
        """Establish connection to the data source (no-op by default)."""

    def disconnect(self) -> None:
        """Release resources (no-op by default)."""

    def refresh(self, account_id: str) -> None:
        """Force-refresh data for an account (no-op by default)."""

    def get_categorised_expenses(
        self,
        account_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
        rules_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Fetch transactions, categorise, and aggregate into an expenses block.

        Default implementation uses the import_csv categorisation engine.
        Providers may override for source-native categorisation (e.g., Monzo categories).
        """
        page = self.get_transactions(account_id, from_date, to_date)
        rules = load_category_rules(rules_path)
        categorise_transactions(page.transactions, rules)
        expenses = aggregate_to_expenses(page.transactions)
        return {
            "expenses": expenses,
            "transaction_count": page.total_count,
            "source": self.__class__.__name__,
        }


# ---------------------------------------------------------------------------
# CSV provider (wraps v5.2-01 parser)
# ---------------------------------------------------------------------------

class CsvAccountProvider(AccountProvider):
    """Reads account data from locally downloaded bank CSV files.

    Each CSV file is treated as one account. The bank is auto-detected
    from the CSV header format.
    """

    def __init__(self, csv_paths: list[str | Path]) -> None:
        self._paths = [Path(p) for p in csv_paths]
        self._parsed: dict[str, list[Transaction]] = {}

    def get_accounts(self) -> list[Account]:
        accounts = []
        for path in self._paths:
            txns = self._load(path)
            bank = txns[0].bank if txns else "unknown"
            accounts.append(Account(
                account_id=str(path),
                name=path.stem,
                institution=bank,
                account_type="current",
            ))
        return accounts

    def get_transactions(
        self,
        account_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> TransactionPage:
        txns = self._load(Path(account_id))
        if from_date:
            txns = [t for t in txns if t.txn_date >= from_date]
        if to_date:
            txns = [t for t in txns if t.txn_date <= to_date]
        return TransactionPage(
            transactions=txns,
            total_count=len(txns),
        )

    def get_full_import(self, account_id: str, rules_path: str | Path | None = None) -> dict[str, Any]:
        """Run the full import_bank_csv pipeline on a CSV file."""
        return import_bank_csv(account_id, rules_path)

    def _load(self, path: Path) -> list[Transaction]:
        key = str(path)
        if key not in self._parsed:
            self._parsed[key] = parse_csv(path)
            logger.info("CsvAccountProvider loaded %d transactions from %s", len(self._parsed[key]), path.name)
        return self._parsed[key]


# ---------------------------------------------------------------------------
# Open Banking provider (stub for v6.0-02)
# ---------------------------------------------------------------------------

class OpenBankingProvider(AccountProvider):
    """Stub for TrueLayer/Plaid Open Banking integration.

    Not yet implemented — this provider defines the integration surface
    for v6.0-02. Calling any method raises NotImplementedError with a
    message pointing to the roadmap.

    Expected flow (v6.0-02):
    1. User initiates OAuth consent via TrueLayer/Plaid Link
    2. Provider stores access token (encrypted) per user
    3. get_accounts() calls provider API for linked accounts
    4. get_transactions() fetches from provider with date filtering
    5. refresh() triggers a data sync for stale accounts
    """

    def __init__(self, provider: str = "truelayer", access_token: str | None = None) -> None:
        self._provider = provider
        self._access_token = access_token

    def get_accounts(self) -> list[Account]:
        raise NotImplementedError(
            f"Open Banking ({self._provider}) not yet implemented. "
            "See roadmap v6.0-02 for the planned integration."
        )

    def get_transactions(
        self,
        account_id: str,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> TransactionPage:
        raise NotImplementedError(
            f"Open Banking ({self._provider}) not yet implemented. "
            "See roadmap v6.0-02 for the planned integration."
        )

    def connect(self) -> None:
        raise NotImplementedError(
            f"Open Banking ({self._provider}) requires OAuth consent flow. "
            "See roadmap v6.0-02."
        )

    def refresh(self, account_id: str) -> None:
        raise NotImplementedError(
            f"Open Banking ({self._provider}) not yet implemented. "
            "See roadmap v6.0-02."
        )
