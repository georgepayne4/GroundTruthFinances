"""Tests for Open Banking integration (v6.0-02).

Covers encryption, income verification, expense summarisation,
CRUD operations, and the updated OpenBankingProvider.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from api.database.models import (
    BankAccount,
    BankConnection,
    BankTransaction,
    Base,
    User,
)

# ---------------------------------------------------------------------------
# Database fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def user(db: Session) -> User:
    """Create a test user."""
    u = User(email="test@example.com", name="Test User")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def connection(db: Session, user: User) -> BankConnection:
    """Create a test bank connection."""
    conn = BankConnection(
        user_id=user.id,
        provider="truelayer",
        institution_name="Test Bank",
        access_token_enc="encrypted_access",
        refresh_token_enc="encrypted_refresh",
        status="active",
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@pytest.fixture
def account(db: Session, connection: BankConnection) -> BankAccount:
    """Create a test bank account."""
    acct = BankAccount(
        connection_id=connection.id,
        external_account_id="ext_acc_001",
        display_name="Test Current Account",
        account_type="current",
        currency="GBP",
        balance=1500.00,
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)
    return acct


def _add_transactions(db: Session, account_id: int, transactions: list[dict]) -> None:
    """Helper to bulk-add transactions."""
    for t in transactions:
        txn = BankTransaction(
            account_id=account_id,
            external_transaction_id=t["ext_id"],
            timestamp=t["timestamp"],
            amount=t["amount"],
            currency="GBP",
            description=t.get("description", ""),
            transaction_type=t.get("type", "DEBIT"),
            category=t.get("category"),
            merchant_name=t.get("merchant"),
        )
        db.add(txn)
    db.commit()


# ---------------------------------------------------------------------------
# Encryption tests
# ---------------------------------------------------------------------------

class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        from cryptography.fernet import Fernet

        from api.banking.encryption import decrypt_token, encrypt_token, reset_fernet

        key = Fernet.generate_key().decode()
        reset_fernet()
        with patch.dict(os.environ, {"GROUNDTRUTH_TOKEN_KEY": key}):
            ciphertext = encrypt_token("my_secret_token")
            assert ciphertext != "my_secret_token"
            plaintext = decrypt_token(ciphertext)
            assert plaintext == "my_secret_token"
        reset_fernet()

    def test_missing_key_raises(self):
        from api.banking.encryption import encrypt_token, reset_fernet

        reset_fernet()
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("GROUNDTRUTH_TOKEN_KEY", None)
            with pytest.raises(RuntimeError, match="GROUNDTRUTH_TOKEN_KEY"):
                encrypt_token("test")
        reset_fernet()

    def test_wrong_key_raises(self):
        from cryptography.fernet import Fernet

        from api.banking.encryption import decrypt_token, encrypt_token, reset_fernet

        key1 = Fernet.generate_key().decode()
        key2 = Fernet.generate_key().decode()

        reset_fernet()
        with patch.dict(os.environ, {"GROUNDTRUTH_TOKEN_KEY": key1}):
            ciphertext = encrypt_token("secret")

        reset_fernet()
        with patch.dict(os.environ, {"GROUNDTRUTH_TOKEN_KEY": key2}), pytest.raises(RuntimeError, match="Failed to decrypt"):
            decrypt_token(ciphertext)
        reset_fernet()


# ---------------------------------------------------------------------------
# Banking CRUD tests
# ---------------------------------------------------------------------------

class TestBankingCRUD:
    def test_create_connection(self, db, user):
        from api.banking.crud import create_connection
        conn = create_connection(db, user.id, "truelayer", "enc_access", "enc_refresh")
        assert conn.id is not None
        assert conn.user_id == user.id
        assert conn.status == "active"

    def test_list_connections(self, db, user, connection):
        from api.banking.crud import list_connections
        conns = list_connections(db, user.id)
        assert len(conns) == 1
        assert conns[0].institution_name == "Test Bank"

    def test_delete_connection(self, db, connection):
        from api.banking.crud import delete_connection, get_connection
        assert delete_connection(db, connection.id)
        assert get_connection(db, connection.id) is None

    def test_delete_nonexistent_returns_false(self, db):
        from api.banking.crud import delete_connection
        assert not delete_connection(db, 9999)

    def test_upsert_account_creates(self, db, connection):
        from api.banking.crud import upsert_account
        acct = upsert_account(db, connection.id, "ext_new", "New Account", "savings", "GBP", 5000.0)
        assert acct.id is not None
        assert acct.display_name == "New Account"
        assert acct.balance == 5000.0

    def test_upsert_account_updates(self, db, connection, account):
        from api.banking.crud import upsert_account
        updated = upsert_account(db, connection.id, "ext_acc_001", "Updated Name", "current", "GBP", 2000.0)
        assert updated.id == account.id
        assert updated.display_name == "Updated Name"
        assert updated.balance == 2000.0

    def test_list_user_accounts(self, db, user, connection, account):
        from api.banking.crud import list_user_accounts
        accounts = list_user_accounts(db, user.id)
        assert len(accounts) == 1
        assert accounts[0]["display_name"] == "Test Current Account"
        assert accounts[0]["institution"] == "Test Bank"

    def test_upsert_transactions(self, db, account):
        from api.banking.crud import upsert_transactions
        txns = [
            {"external_transaction_id": "txn_1", "timestamp": datetime.now(timezone.utc), "amount": -25.50, "description": "Tesco"},
            {"external_transaction_id": "txn_2", "timestamp": datetime.now(timezone.utc), "amount": -12.00, "description": "Netflix"},
        ]
        count = upsert_transactions(db, account.id, txns)
        assert count == 2

        # Upsert again — should not add duplicates
        count = upsert_transactions(db, account.id, txns)
        assert count == 0

    def test_list_transactions(self, db, account):
        from api.banking.crud import list_transactions, upsert_transactions
        txns = [
            {"external_transaction_id": "txn_a", "timestamp": datetime.now(timezone.utc), "amount": -50.0, "description": "Shop"},
        ]
        upsert_transactions(db, account.id, txns)
        result = list_transactions(db, account.id)
        assert len(result) == 1
        assert result[0]["amount"] == -50.0

    def test_update_connection_status(self, db, connection):
        from api.banking.crud import get_connection, update_connection_status
        update_connection_status(db, connection.id, "expired")
        conn = get_connection(db, connection.id)
        assert conn.status == "expired"

    def test_mark_synced(self, db, connection):
        from api.banking.crud import get_connection, mark_synced
        assert connection.last_synced_at is None
        mark_synced(db, connection.id)
        conn = get_connection(db, connection.id)
        assert conn.last_synced_at is not None


# ---------------------------------------------------------------------------
# Income verification tests
# ---------------------------------------------------------------------------

class TestIncomeVerification:
    def test_no_transactions(self, db, user):
        from api.banking.income import verify_income
        result = verify_income(db, user.id)
        assert result.total_monthly_income == 0.0
        assert result.streams == []

    def test_salary_detection(self, db, user, connection, account):
        from api.banking.income import verify_income

        now = datetime.now(timezone.utc)
        txns = []
        for i in range(3):
            txns.append({
                "ext_id": f"salary_{i}",
                "timestamp": now - timedelta(days=30 * i),
                "amount": 2500.00,
                "description": "SALARY PAYMENT FROM ACME LTD",
                "category": "INCOME",
            })
        # Add some non-income
        txns.append({"ext_id": "coffee", "timestamp": now, "amount": 4.50, "description": "Costa Coffee"})
        _add_transactions(db, account.id, txns)

        result = verify_income(db, user.id)
        assert result.total_monthly_income > 0
        assert any("SALARY" in s.description for s in result.streams)

    def test_irregular_income(self, db, user, connection, account):
        from api.banking.income import verify_income

        now = datetime.now(timezone.utc)
        txns = [
            {"ext_id": "free_1", "timestamp": now - timedelta(days=60), "amount": 800.0, "description": "Freelance Invoice Payment"},
            {"ext_id": "free_2", "timestamp": now - timedelta(days=25), "amount": 1200.0, "description": "Freelance Invoice Payment"},
            {"ext_id": "free_3", "timestamp": now - timedelta(days=5), "amount": 950.0, "description": "Freelance Invoice Payment"},
        ]
        _add_transactions(db, account.id, txns)

        result = verify_income(db, user.id)
        assert len(result.streams) >= 1


# ---------------------------------------------------------------------------
# Expense summary tests
# ---------------------------------------------------------------------------

class TestExpenseSummary:
    def test_no_spending(self, db, user):
        from api.banking.expenses import summarise_expenses
        result = summarise_expenses(db, user.id, days=30)
        assert result.total_spending == 0.0

    def test_categorised_spending(self, db, user, connection, account):
        from api.banking.expenses import summarise_expenses

        now = datetime.now(timezone.utc)
        txns = [
            {"ext_id": "s1", "timestamp": now - timedelta(days=5), "amount": -45.50, "description": "Tesco", "category": "PURCHASE"},
            {"ext_id": "s2", "timestamp": now - timedelta(days=3), "amount": -15.99, "description": "Netflix", "category": "DIRECT_DEBIT"},
            {"ext_id": "s3", "timestamp": now - timedelta(days=1), "amount": -950.00, "description": "Rent", "category": "STANDING_ORDER"},
        ]
        _add_transactions(db, account.id, txns)

        result = summarise_expenses(db, user.id, days=30)
        assert result.total_spending == 1011.49
        assert result.transaction_count == 3
        assert len(result.categories) >= 2

    def test_ignores_credits(self, db, user, connection, account):
        from api.banking.expenses import summarise_expenses

        now = datetime.now(timezone.utc)
        txns = [
            {"ext_id": "credit", "timestamp": now - timedelta(days=2), "amount": 2500.00, "description": "Salary"},
            {"ext_id": "debit", "timestamp": now - timedelta(days=1), "amount": -30.00, "description": "Amazon"},
        ]
        _add_transactions(db, account.id, txns)

        result = summarise_expenses(db, user.id, days=30)
        assert result.total_spending == 30.00

    def test_percentages_sum_to_100(self, db, user, connection, account):
        from api.banking.expenses import summarise_expenses

        now = datetime.now(timezone.utc)
        txns = [
            {"ext_id": "p1", "timestamp": now - timedelta(days=5), "amount": -100.0, "category": "PURCHASE"},
            {"ext_id": "p2", "timestamp": now - timedelta(days=3), "amount": -50.0, "category": "DIRECT_DEBIT"},
            {"ext_id": "p3", "timestamp": now - timedelta(days=1), "amount": -50.0, "category": "ATM"},
        ]
        _add_transactions(db, account.id, txns)

        result = summarise_expenses(db, user.id, days=30)
        total_pct = sum(c.percentage for c in result.categories)
        assert abs(total_pct - 100.0) < 1.0


# ---------------------------------------------------------------------------
# OpenBankingProvider integration tests
# ---------------------------------------------------------------------------

class TestOpenBankingProvider:
    def test_requires_db(self):
        from engine.providers import OpenBankingProvider
        provider = OpenBankingProvider()
        with pytest.raises(RuntimeError, match="requires a database"):
            provider.get_accounts()

    def test_get_accounts_from_db(self, db, user, connection, account):
        from engine.providers import OpenBankingProvider
        provider = OpenBankingProvider(db=db, user_id=user.id)
        accounts = provider.get_accounts()
        assert len(accounts) == 1
        assert accounts[0].name == "Test Current Account"
        assert accounts[0].institution == "Test Bank"
        assert accounts[0].balance == 1500.00

    def test_get_transactions_from_db(self, db, user, connection, account):
        from engine.providers import OpenBankingProvider

        now = datetime.now(timezone.utc)
        _add_transactions(db, account.id, [
            {"ext_id": "t1", "timestamp": now - timedelta(days=10), "amount": -25.0, "description": "Shop"},
            {"ext_id": "t2", "timestamp": now - timedelta(days=5), "amount": -50.0, "description": "Restaurant"},
            {"ext_id": "t3", "timestamp": now - timedelta(days=1), "amount": 2500.0, "description": "Salary"},
        ])

        provider = OpenBankingProvider(db=db, user_id=user.id)
        page = provider.get_transactions(str(account.id))
        assert page.total_count == 3

    def test_get_transactions_date_filter(self, db, user, connection, account):
        from engine.providers import OpenBankingProvider

        now = datetime.now(timezone.utc)
        _add_transactions(db, account.id, [
            {"ext_id": "old", "timestamp": now - timedelta(days=60), "amount": -100.0, "description": "Old"},
            {"ext_id": "recent", "timestamp": now - timedelta(days=5), "amount": -50.0, "description": "Recent"},
        ])

        provider = OpenBankingProvider(db=db, user_id=user.id)
        page = provider.get_transactions(
            str(account.id),
            from_date=(now - timedelta(days=30)).date(),
        )
        assert page.total_count == 1

    def test_default_provider_is_truelayer(self):
        from engine.providers import OpenBankingProvider
        provider = OpenBankingProvider()
        assert provider._provider == "truelayer"


# ---------------------------------------------------------------------------
# TrueLayer client tests (unit — mock HTTP)
# ---------------------------------------------------------------------------

class TestTrueLayerClient:
    def test_build_auth_url(self):
        from api.banking.truelayer import build_auth_url
        with patch.dict(os.environ, {"TRUELAYER_CLIENT_ID": "test_id", "TRUELAYER_SANDBOX": "1"}):
            url = build_auth_url(state="user_1")
            assert "truelayer-sandbox.com" in url
            assert "client_id=test_id" in url
            assert "state=user_1" in url
            assert "scope=" in url

    def test_build_auth_url_production(self):
        from api.banking.truelayer import build_auth_url
        with patch.dict(os.environ, {"TRUELAYER_CLIENT_ID": "prod_id", "TRUELAYER_SANDBOX": "0"}):
            url = build_auth_url()
            assert "auth.truelayer.com" in url
            assert "client_id=prod_id" in url

    def test_missing_client_id_raises(self):
        from api.banking.truelayer import build_auth_url
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("TRUELAYER_CLIENT_ID", None)
            with pytest.raises(RuntimeError, match="TRUELAYER_CLIENT_ID"):
                build_auth_url()


# ---------------------------------------------------------------------------
# Database model tests
# ---------------------------------------------------------------------------

class TestBankingModels:
    def test_connection_cascade_delete(self, db, user, connection, account):
        """Deleting a connection should cascade to accounts and transactions."""
        now = datetime.now(timezone.utc)
        _add_transactions(db, account.id, [
            {"ext_id": "cascade_1", "timestamp": now, "amount": -10.0},
        ])

        db.delete(connection)
        db.commit()

        assert db.query(BankAccount).count() == 0
        assert db.query(BankTransaction).count() == 0

    def test_account_unique_constraint(self, db, connection):
        """Cannot create two accounts with same connection_id + external_account_id."""
        a1 = BankAccount(connection_id=connection.id, external_account_id="dup_test", account_type="current")
        db.add(a1)
        db.commit()

        a2 = BankAccount(connection_id=connection.id, external_account_id="dup_test", account_type="savings")
        db.add(a2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()

    def test_transaction_unique_constraint(self, db, account):
        """Cannot create two transactions with same account_id + external_transaction_id."""
        t1 = BankTransaction(
            account_id=account.id, external_transaction_id="dup_txn",
            timestamp=datetime.now(timezone.utc), amount=-10.0,
        )
        db.add(t1)
        db.commit()

        t2 = BankTransaction(
            account_id=account.id, external_transaction_id="dup_txn",
            timestamp=datetime.now(timezone.utc), amount=-20.0,
        )
        db.add(t2)
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
