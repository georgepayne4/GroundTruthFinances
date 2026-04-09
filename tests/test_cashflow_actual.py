"""Tests for Planned vs Actual Cashflow (v6.0-07)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.cashflow_actual import CashflowComparison, analyse_drift
from api.database.models import (
    BankAccount,
    BankConnection,
    BankTransaction,
    Base,
    User,
)


@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = factory()
    yield session
    session.close()
    engine.dispose()


@pytest.fixture
def user(db: Session) -> User:
    u = User(email="drift@example.com", name="Drift User")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def connection(db: Session, user: User) -> BankConnection:
    conn = BankConnection(
        user_id=user.id, provider="truelayer", institution_name="Test Bank",
        access_token_enc="enc", refresh_token_enc="enc", status="active",
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


@pytest.fixture
def account(db: Session, connection: BankConnection) -> BankAccount:
    acct = BankAccount(
        connection_id=connection.id, external_account_id="drift_acc",
        display_name="Current", account_type="current", balance=2000.0,
    )
    db.add(acct)
    db.commit()
    db.refresh(acct)
    return acct


def _add_txns(db: Session, account_id: int, txns: list[dict]) -> None:
    for t in txns:
        db.add(BankTransaction(
            account_id=account_id,
            external_transaction_id=t["ext_id"],
            timestamp=t["timestamp"],
            amount=t["amount"],
            category=t.get("category", "PURCHASE"),
        ))
    db.commit()


@pytest.fixture
def sample_profile_with_expenses() -> dict:
    return {
        "expenses": {
            "essential": {
                "food_groceries": 300,
                "bills": 200,
                "transport": 150,
            },
            "discretionary": {
                "dining_out": 100,
                "entertainment": 50,
            },
        }
    }


class TestAnalyseDrift:
    def test_no_bank_data(self, db, user, sample_profile_with_expenses):
        result = analyse_drift(sample_profile_with_expenses, db, user.id)
        assert isinstance(result, CashflowComparison)
        assert result.total_actual_monthly == 0
        assert result.total_planned_monthly == 800

    def test_with_bank_data(self, db, user, connection, account, sample_profile_with_expenses):
        now = datetime.now(timezone.utc)
        txns = [
            {"ext_id": f"g_{i}", "timestamp": now - timedelta(days=i * 3), "amount": -35.0, "category": "groceries"}
            for i in range(10)
        ] + [
            {"ext_id": f"d_{i}", "timestamp": now - timedelta(days=i * 7), "amount": -25.0, "category": "dining"}
            for i in range(4)
        ]
        _add_txns(db, account.id, txns)

        result = analyse_drift(sample_profile_with_expenses, db, user.id, months=1)
        assert result.total_actual_monthly > 0
        assert len(result.category_drifts) > 0

    def test_drift_detection(self, db, user, connection, account, sample_profile_with_expenses):
        now = datetime.now(timezone.utc)
        # Spend way more on groceries than planned (£50/day for 20 days = £1000 in ~20 days)
        txns = [
            {"ext_id": f"over_{i}", "timestamp": now - timedelta(days=i), "amount": -50.0, "category": "groceries"}
            for i in range(20)
        ]
        _add_txns(db, account.id, txns)

        result = analyse_drift(sample_profile_with_expenses, db, user.id, months=1)
        groceries_drift = next((d for d in result.category_drifts if d.category == "food_groceries"), None)
        assert groceries_drift is not None
        assert groceries_drift.actual_monthly > groceries_drift.planned_monthly

    def test_suggested_updates(self, db, user, connection, account, sample_profile_with_expenses):
        now = datetime.now(timezone.utc)
        # Spend significantly more than planned (£40/day for 25 days = £1000)
        txns = [
            {"ext_id": f"sug_{i}", "timestamp": now - timedelta(days=i), "amount": -40.0, "category": "groceries"}
            for i in range(25)
        ]
        _add_txns(db, account.id, txns)

        result = analyse_drift(sample_profile_with_expenses, db, user.id, months=1, drift_threshold_pct=20.0)
        # Should suggest updating food_groceries
        food_suggestion = [s for s in result.suggested_updates if s["category"] == "food_groceries"]
        assert len(food_suggestion) >= 1

    def test_monthly_breakdown(self, db, user, connection, account, sample_profile_with_expenses):
        now = datetime.now(timezone.utc)
        txns = [
            {"ext_id": f"mb_{i}", "timestamp": now - timedelta(days=i * 5), "amount": -50.0, "category": "bills"}
            for i in range(6)
        ]
        _add_txns(db, account.id, txns)

        result = analyse_drift(sample_profile_with_expenses, db, user.id, months=2)
        assert len(result.monthly_breakdown) >= 1

    def test_empty_profile_expenses(self, db, user):
        result = analyse_drift({}, db, user.id)
        assert result.total_planned_monthly == 0
