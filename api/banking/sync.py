"""api/banking/sync.py — Account and transaction sync logic (v6.0-02).

Orchestrates fetching data from TrueLayer, decrypting tokens, refreshing
if expired, and persisting accounts/transactions to the database.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.banking import crud as banking_crud
from api.banking.encryption import decrypt_token, encrypt_token
from api.banking.truelayer import (
    fetch_accounts,
    fetch_transactions,
    refresh_tokens,
)
from api.database.models import BankAccount, BankConnection

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    """Summary of a sync operation."""
    connection_id: int
    accounts_synced: int
    transactions_added: int
    errors: list[str]


async def _ensure_valid_token(db: Session, connection: BankConnection) -> str:
    """Return a valid access token, refreshing if expired."""
    now = datetime.now(timezone.utc)

    if connection.token_expires_at and connection.token_expires_at > now + timedelta(minutes=5):
        return decrypt_token(connection.access_token_enc)

    logger.info("Token expired for connection %d, refreshing", connection.id)
    refresh_tok = decrypt_token(connection.refresh_token_enc)
    new_tokens = await refresh_tokens(refresh_tok)

    banking_crud.update_tokens(
        db,
        connection.id,
        access_token_enc=encrypt_token(new_tokens.access_token),
        refresh_token_enc=encrypt_token(new_tokens.refresh_token),
        token_expires_at=now + timedelta(seconds=new_tokens.expires_in),
    )
    return new_tokens.access_token


async def sync_connection(
    db: Session,
    connection: BankConnection,
    days_back: int = 90,
) -> SyncResult:
    """Sync all accounts and recent transactions for a bank connection."""
    errors: list[str] = []
    accounts_synced = 0
    transactions_added = 0

    try:
        access_token = await _ensure_valid_token(db, connection)
    except Exception as exc:
        banking_crud.update_connection_status(db, connection.id, "expired")
        return SyncResult(connection.id, 0, 0, [f"Token refresh failed: {exc}"])

    try:
        tl_accounts = await fetch_accounts(access_token)
    except Exception as exc:
        errors.append(f"Failed to fetch accounts: {exc}")
        return SyncResult(connection.id, 0, 0, errors)

    from_date = (datetime.now(timezone.utc) - timedelta(days=days_back)).date()

    for tl_acct in tl_accounts:
        try:
            banking_crud.upsert_account(
                db,
                connection_id=connection.id,
                external_account_id=tl_acct.account_id,
                display_name=tl_acct.display_name,
                account_type=tl_acct.account_type,
                currency=tl_acct.currency,
                balance=tl_acct.balance,
            )
            accounts_synced += 1
        except Exception as exc:
            errors.append(f"Account {tl_acct.account_id}: {exc}")
            continue

        # Fetch transactions
        try:
            tl_txns = await fetch_transactions(access_token, tl_acct.account_id, from_date=from_date)
            db_account = (
                db.query(BankAccount)
                .filter_by(connection_id=connection.id, external_account_id=tl_acct.account_id)
                .first()
            )
            if db_account:
                txn_dicts = [
                    {
                        "external_transaction_id": t.transaction_id,
                        "timestamp": datetime.fromisoformat(t.timestamp) if isinstance(t.timestamp, str) else t.timestamp,
                        "amount": t.amount,
                        "currency": t.currency,
                        "description": t.description,
                        "transaction_type": t.transaction_type,
                        "category": t.category,
                        "merchant_name": t.merchant_name,
                    }
                    for t in tl_txns
                ]
                added = banking_crud.upsert_transactions(db, db_account.id, txn_dicts)
                transactions_added += added
        except Exception as exc:
            errors.append(f"Transactions for {tl_acct.account_id}: {exc}")

    banking_crud.mark_synced(db, connection.id)
    logger.info(
        "Sync complete for connection %d: %d accounts, %d new transactions",
        connection.id, accounts_synced, transactions_added,
    )
    return SyncResult(connection.id, accounts_synced, transactions_added, errors)


async def sync_user_connections(db: Session, user_id: int, days_back: int = 90) -> list[SyncResult]:
    """Sync all active bank connections for a user."""
    connections = banking_crud.list_connections(db, user_id)
    results = []
    for conn in connections:
        if conn.status != "active":
            continue
        result = await sync_connection(db, conn, days_back)
        results.append(result)
    return results
