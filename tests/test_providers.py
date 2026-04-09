"""Tests for the account provider abstraction (v5.3-06)."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

from engine.providers import (
    Account,
    AccountProvider,
    CsvAccountProvider,
    OpenBankingProvider,
    TransactionPage,
)

# ---------------------------------------------------------------------------
# Test fixtures
# ---------------------------------------------------------------------------

def _write_monzo_csv(tmp_path: Path) -> Path:
    """Create a minimal Monzo-format CSV for testing."""
    csv_path = tmp_path / "monzo_test.csv"
    csv_path.write_text(
        "Date,Name,Amount,Category,Type\n"
        "01/03/2026,Tesco,-45.50,Groceries,card payment\n"
        "02/03/2026,Salary,2500.00,Income,bank transfer\n"
        "03/03/2026,Netflix,-15.99,Entertainment,direct debit\n"
        "15/03/2026,Rent,-950.00,Bills,standing order\n"
        "20/03/2026,Coffee Shop,-4.20,Eating out,card payment\n",
        encoding="utf-8",
    )
    return csv_path


# ---------------------------------------------------------------------------
# ABC contract tests
# ---------------------------------------------------------------------------

class TestAccountProviderABC:
    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            AccountProvider()

    def test_subclass_must_implement_get_accounts(self):
        class Incomplete(AccountProvider):
            def get_transactions(self, account_id, from_date=None, to_date=None):
                return TransactionPage(transactions=[], total_count=0)

        with pytest.raises(TypeError):
            Incomplete()

    def test_subclass_must_implement_get_transactions(self):
        class Incomplete(AccountProvider):
            def get_accounts(self):
                return []

        with pytest.raises(TypeError):
            Incomplete()


# ---------------------------------------------------------------------------
# Account / TransactionPage dataclass tests
# ---------------------------------------------------------------------------

class TestDataModels:
    def test_account_defaults(self):
        a = Account(account_id="1", name="Test", institution="Monzo", account_type="current")
        assert a.currency == "GBP"
        assert a.balance is None
        assert a.metadata == {}

    def test_transaction_page_defaults(self):
        page = TransactionPage(transactions=[], total_count=0)
        assert page.has_more is False
        assert page.cursor is None


# ---------------------------------------------------------------------------
# CsvAccountProvider tests
# ---------------------------------------------------------------------------

class TestCsvAccountProvider:
    def test_get_accounts(self, tmp_path):
        csv_path = _write_monzo_csv(tmp_path)
        provider = CsvAccountProvider([csv_path])
        accounts = provider.get_accounts()
        assert len(accounts) == 1
        assert accounts[0].institution == "monzo"
        assert accounts[0].account_type == "current"
        assert accounts[0].name == "monzo_test"

    def test_get_transactions_all(self, tmp_path):
        csv_path = _write_monzo_csv(tmp_path)
        provider = CsvAccountProvider([csv_path])
        page = provider.get_transactions(str(csv_path))
        assert page.total_count == 5
        assert len(page.transactions) == 5
        assert page.has_more is False

    def test_get_transactions_date_filter(self, tmp_path):
        csv_path = _write_monzo_csv(tmp_path)
        provider = CsvAccountProvider([csv_path])
        page = provider.get_transactions(
            str(csv_path),
            from_date=date(2026, 3, 2),
            to_date=date(2026, 3, 15),
        )
        assert page.total_count == 3

    def test_get_transactions_from_date_only(self, tmp_path):
        csv_path = _write_monzo_csv(tmp_path)
        provider = CsvAccountProvider([csv_path])
        page = provider.get_transactions(str(csv_path), from_date=date(2026, 3, 15))
        assert page.total_count == 2

    def test_get_transactions_to_date_only(self, tmp_path):
        csv_path = _write_monzo_csv(tmp_path)
        provider = CsvAccountProvider([csv_path])
        page = provider.get_transactions(str(csv_path), to_date=date(2026, 3, 2))
        assert page.total_count == 2

    def test_multiple_csv_files(self, tmp_path):
        csv1 = _write_monzo_csv(tmp_path)
        csv2 = tmp_path / "monzo_test2.csv"
        csv2.write_text(
            "Date,Name,Amount,Category,Type\n"
            "05/03/2026,Amazon,-29.99,Shopping,card payment\n",
            encoding="utf-8",
        )
        provider = CsvAccountProvider([csv1, csv2])
        accounts = provider.get_accounts()
        assert len(accounts) == 2

    def test_caches_parsed_csv(self, tmp_path):
        csv_path = _write_monzo_csv(tmp_path)
        provider = CsvAccountProvider([csv_path])
        # Call twice — should use cached data
        provider.get_transactions(str(csv_path))
        provider.get_transactions(str(csv_path))
        assert str(csv_path) in provider._parsed

    def test_get_categorised_expenses(self, tmp_path):
        csv_path = _write_monzo_csv(tmp_path)
        provider = CsvAccountProvider([csv_path])
        result = provider.get_categorised_expenses(str(csv_path))
        assert "expenses" in result
        assert result["transaction_count"] == 5
        assert result["source"] == "CsvAccountProvider"

    def test_get_full_import(self, tmp_path):
        csv_path = _write_monzo_csv(tmp_path)
        provider = CsvAccountProvider([csv_path])
        result = provider.get_full_import(str(csv_path))
        assert "expenses" in result
        assert "summary" in result
        assert result["summary"]["transactions_parsed"] == 5

    def test_connect_disconnect_noop(self, tmp_path):
        csv_path = _write_monzo_csv(tmp_path)
        provider = CsvAccountProvider([csv_path])
        provider.connect()
        provider.disconnect()


# ---------------------------------------------------------------------------
# OpenBankingProvider stub tests
# ---------------------------------------------------------------------------

class TestOpenBankingProvider:
    def test_get_accounts_raises(self):
        provider = OpenBankingProvider()
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            provider.get_accounts()

    def test_get_transactions_raises(self):
        provider = OpenBankingProvider()
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            provider.get_transactions("acc_123")

    def test_connect_raises(self):
        provider = OpenBankingProvider()
        with pytest.raises(NotImplementedError, match="OAuth consent"):
            provider.connect()

    def test_refresh_raises(self):
        provider = OpenBankingProvider()
        with pytest.raises(NotImplementedError, match="not yet implemented"):
            provider.refresh("acc_123")

    def test_default_provider_is_truelayer(self):
        provider = OpenBankingProvider()
        assert provider._provider == "truelayer"

    def test_custom_provider_name(self):
        provider = OpenBankingProvider(provider="plaid")
        assert provider._provider == "plaid"
        with pytest.raises(NotImplementedError, match="plaid"):
            provider.get_accounts()
