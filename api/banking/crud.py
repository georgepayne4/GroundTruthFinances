"""api/banking/crud.py — Database operations for Open Banking (v6.0-02).

Pure persistence functions for bank connections, accounts, and transactions.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from api.database.models import BankAccount, BankConnection, BankTransaction

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

def create_connection(
    db: Session,
    user_id: int,
    provider: str,
    access_token_enc: str,
    refresh_token_enc: str,
    token_expires_at: datetime | None = None,
    institution_name: str | None = None,
) -> BankConnection:
    """Create a new bank connection after OAuth consent."""
    conn = BankConnection(
        user_id=user_id,
        provider=provider,
        institution_name=institution_name,
        access_token_enc=access_token_enc,
        refresh_token_enc=refresh_token_enc,
        token_expires_at=token_expires_at,
        status="active",
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    logger.info("Created bank connection %d for user %d via %s", conn.id, user_id, provider)
    return conn


def get_connection(db: Session, connection_id: int) -> BankConnection | None:
    return db.query(BankConnection).filter(BankConnection.id == connection_id).first()


def list_connections(db: Session, user_id: int) -> list[BankConnection]:
    return (
        db.query(BankConnection)
        .filter(BankConnection.user_id == user_id)
        .order_by(BankConnection.consent_granted_at.desc())
        .all()
    )


def update_tokens(
    db: Session,
    connection_id: int,
    access_token_enc: str,
    refresh_token_enc: str,
    token_expires_at: datetime | None = None,
) -> BankConnection | None:
    """Update stored tokens after a refresh."""
    conn = get_connection(db, connection_id)
    if conn is None:
        return None
    conn.access_token_enc = access_token_enc
    conn.refresh_token_enc = refresh_token_enc
    conn.token_expires_at = token_expires_at
    db.commit()
    db.refresh(conn)
    return conn


def update_connection_status(db: Session, connection_id: int, status: str) -> BankConnection | None:
    conn = get_connection(db, connection_id)
    if conn is None:
        return None
    conn.status = status
    db.commit()
    db.refresh(conn)
    return conn


def mark_synced(db: Session, connection_id: int) -> None:
    """Update last_synced_at on the connection."""
    conn = get_connection(db, connection_id)
    if conn:
        conn.last_synced_at = datetime.now(timezone.utc)
        db.commit()


def delete_connection(db: Session, connection_id: int) -> bool:
    """Revoke and delete a bank connection (cascades to accounts and transactions)."""
    conn = get_connection(db, connection_id)
    if conn is None:
        return False
    db.delete(conn)
    db.commit()
    logger.info("Deleted bank connection %d", connection_id)
    return True


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

def upsert_account(
    db: Session,
    connection_id: int,
    external_account_id: str,
    display_name: str | None = None,
    account_type: str = "current",
    currency: str = "GBP",
    balance: float | None = None,
) -> BankAccount:
    """Insert or update a bank account from provider data."""
    existing = (
        db.query(BankAccount)
        .filter(
            BankAccount.connection_id == connection_id,
            BankAccount.external_account_id == external_account_id,
        )
        .first()
    )
    if existing:
        existing.display_name = display_name
        existing.account_type = account_type
        existing.currency = currency
        existing.balance = balance
        existing.last_synced_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(existing)
        return existing

    account = BankAccount(
        connection_id=connection_id,
        external_account_id=external_account_id,
        display_name=display_name,
        account_type=account_type,
        currency=currency,
        balance=balance,
        last_synced_at=datetime.now(timezone.utc),
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return account


def list_accounts(db: Session, connection_id: int) -> list[BankAccount]:
    return (
        db.query(BankAccount)
        .filter(BankAccount.connection_id == connection_id)
        .all()
    )


def list_user_accounts(db: Session, user_id: int) -> list[dict[str, Any]]:
    """Return all bank accounts for a user across all connections."""
    rows = (
        db.query(BankAccount, BankConnection)
        .join(BankConnection, BankAccount.connection_id == BankConnection.id)
        .filter(BankConnection.user_id == user_id, BankConnection.status == "active")
        .all()
    )
    return [
        {
            "id": acct.id,
            "connection_id": acct.connection_id,
            "external_account_id": acct.external_account_id,
            "display_name": acct.display_name,
            "account_type": acct.account_type,
            "currency": acct.currency,
            "balance": acct.balance,
            "institution": conn.institution_name,
            "last_synced_at": acct.last_synced_at.isoformat() if acct.last_synced_at else None,
        }
        for acct, conn in rows
    ]


def get_account(db: Session, account_id: int) -> BankAccount | None:
    return db.query(BankAccount).filter(BankAccount.id == account_id).first()


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

def upsert_transactions(
    db: Session,
    account_id: int,
    transactions: list[dict[str, Any]],
) -> int:
    """Bulk upsert transactions. Returns count of new transactions inserted."""
    existing_ids = set(
        row[0]
        for row in db.query(BankTransaction.external_transaction_id)
        .filter(BankTransaction.account_id == account_id)
        .all()
    )
    new_count = 0
    for t in transactions:
        ext_id = t["external_transaction_id"]
        if ext_id in existing_ids:
            continue
        txn = BankTransaction(
            account_id=account_id,
            external_transaction_id=ext_id,
            timestamp=t["timestamp"],
            amount=t["amount"],
            currency=t.get("currency", "GBP"),
            description=t.get("description"),
            transaction_type=t.get("transaction_type"),
            category=t.get("category"),
            merchant_name=t.get("merchant_name"),
        )
        db.add(txn)
        new_count += 1
        existing_ids.add(ext_id)

    if new_count:
        db.commit()
    return new_count


def list_transactions(
    db: Session,
    account_id: int,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """Return transactions for an account, newest first."""
    rows = (
        db.query(BankTransaction)
        .filter(BankTransaction.account_id == account_id)
        .order_by(BankTransaction.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "external_transaction_id": t.external_transaction_id,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "amount": t.amount,
            "currency": t.currency,
            "description": t.description,
            "transaction_type": t.transaction_type,
            "category": t.category,
            "merchant_name": t.merchant_name,
        }
        for t in rows
    ]


def list_user_transactions(
    db: Session,
    user_id: int,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return all transactions across a user's connected accounts."""
    rows = (
        db.query(BankTransaction)
        .join(BankAccount, BankTransaction.account_id == BankAccount.id)
        .join(BankConnection, BankAccount.connection_id == BankConnection.id)
        .filter(BankConnection.user_id == user_id, BankConnection.status == "active")
        .order_by(BankTransaction.timestamp.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "account_id": t.account_id,
            "external_transaction_id": t.external_transaction_id,
            "timestamp": t.timestamp.isoformat() if t.timestamp else None,
            "amount": t.amount,
            "currency": t.currency,
            "description": t.description,
            "category": t.category,
            "merchant_name": t.merchant_name,
        }
        for t in rows
    ]
