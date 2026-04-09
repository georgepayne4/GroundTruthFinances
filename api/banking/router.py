"""api/banking/router.py — Open Banking API endpoints (v6.0-02).

Endpoints for connecting bank accounts via TrueLayer, syncing transactions,
viewing expenses, and verifying income.
"""

from __future__ import annotations

import contextlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.banking import crud as banking_crud
from api.banking.encryption import encrypt_token
from api.banking.expenses import summarise_expenses
from api.banking.income import verify_income
from api.banking.sync import sync_connection, sync_user_connections
from api.banking.truelayer import build_auth_url, exchange_code
from api.database.models import User
from api.database.session import get_db
from api.dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/banking", tags=["banking"])


# ---------------------------------------------------------------------------
# OAuth consent flow
# ---------------------------------------------------------------------------

@router.get("/connect", summary="Initiate Open Banking consent")
async def connect_bank(
    user: User = Depends(get_current_user),
) -> dict[str, str]:
    """Generate a TrueLayer authorization URL for the user to grant bank access.

    The frontend should redirect the user to the returned auth_url.
    """
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required for banking")
    state = f"user_{user.id}"
    auth_url = build_auth_url(state=state)
    return {"auth_url": auth_url, "state": state}


@router.get("/callback", summary="OAuth callback from TrueLayer")
async def oauth_callback(
    code: str = Query(..., description="Authorization code from TrueLayer"),
    state: str = Query("", description="State parameter for CSRF protection"),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Handle the OAuth callback after user grants consent.

    Exchanges the authorization code for tokens and stores them encrypted.
    """
    # Extract user_id from state
    user_id = None
    if state.startswith("user_"):
        with contextlib.suppress(ValueError, IndexError):
            user_id = int(state.split("_", 1)[1])

    if user_id is None:
        raise HTTPException(status_code=400, detail="Invalid state parameter")

    try:
        tokens = await exchange_code(code)
    except Exception as exc:
        logger.error("Token exchange failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to exchange authorization code") from exc

    expires_at = datetime.now(timezone.utc) + timedelta(seconds=tokens.expires_in)
    connection = banking_crud.create_connection(
        db,
        user_id=user_id,
        provider="truelayer",
        access_token_enc=encrypt_token(tokens.access_token),
        refresh_token_enc=encrypt_token(tokens.refresh_token),
        token_expires_at=expires_at,
    )

    # Trigger initial sync
    result = await sync_connection(db, connection)

    return {
        "connection_id": connection.id,
        "status": "connected",
        "accounts_synced": result.accounts_synced,
        "transactions_added": result.transactions_added,
        "errors": result.errors,
    }


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

@router.get("/connections", summary="List bank connections")
async def list_connections(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return all bank connections for the authenticated user."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    connections = banking_crud.list_connections(db, user.id)
    return {
        "connections": [
            {
                "id": c.id,
                "provider": c.provider,
                "institution_name": c.institution_name,
                "status": c.status,
                "consent_granted_at": c.consent_granted_at.isoformat() if c.consent_granted_at else None,
                "last_synced_at": c.last_synced_at.isoformat() if c.last_synced_at else None,
                "account_count": len(c.accounts),
            }
            for c in connections
        ],
        "count": len(connections),
    }


@router.delete("/connections/{connection_id}", summary="Disconnect a bank")
async def disconnect_bank(
    connection_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """Revoke a bank connection and delete all associated data."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    conn = banking_crud.get_connection(db, connection_id)
    if conn is None or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Connection not found")
    banking_crud.delete_connection(db, connection_id)
    return {"status": "disconnected", "connection_id": str(connection_id)}


# ---------------------------------------------------------------------------
# Accounts and sync
# ---------------------------------------------------------------------------

@router.get("/accounts", summary="List connected bank accounts")
async def list_accounts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return all bank accounts across active connections."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    accounts = banking_crud.list_user_accounts(db, user.id)
    return {"accounts": accounts, "count": len(accounts)}


@router.post("/sync", summary="Sync all bank connections")
async def sync_all(
    days: int = Query(90, ge=1, le=365, description="Days of transaction history to sync"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Trigger a sync of all active bank connections for the user."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    results = await sync_user_connections(db, user.id, days_back=days)
    return {
        "results": [
            {
                "connection_id": r.connection_id,
                "accounts_synced": r.accounts_synced,
                "transactions_added": r.transactions_added,
                "errors": r.errors,
            }
            for r in results
        ],
        "total_accounts": sum(r.accounts_synced for r in results),
        "total_transactions_added": sum(r.transactions_added for r in results),
    }


@router.post("/accounts/{account_id}/sync", summary="Sync a specific account")
async def sync_account(
    account_id: int,
    days: int = Query(90, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Sync transactions for a specific bank account."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    account = banking_crud.get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    conn = banking_crud.get_connection(db, account.connection_id)
    if conn is None or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Account not found")

    result = await sync_connection(db, conn, days_back=days)
    return {
        "connection_id": result.connection_id,
        "accounts_synced": result.accounts_synced,
        "transactions_added": result.transactions_added,
        "errors": result.errors,
    }


# ---------------------------------------------------------------------------
# Transactions
# ---------------------------------------------------------------------------

@router.get("/transactions", summary="List transactions across all accounts")
async def list_transactions(
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return recent transactions across all connected bank accounts."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    txns = banking_crud.list_user_transactions(db, user.id, limit=limit)
    return {"transactions": txns, "count": len(txns)}


@router.get("/accounts/{account_id}/transactions", summary="List account transactions")
async def list_account_transactions(
    account_id: int,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return transactions for a specific bank account."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    account = banking_crud.get_account(db, account_id)
    if account is None:
        raise HTTPException(status_code=404, detail="Account not found")

    conn = banking_crud.get_connection(db, account.connection_id)
    if conn is None or conn.user_id != user.id:
        raise HTTPException(status_code=404, detail="Account not found")

    txns = banking_crud.list_transactions(db, account_id, limit=limit, offset=offset)
    return {"transactions": txns, "count": len(txns)}


# ---------------------------------------------------------------------------
# Expenses and income
# ---------------------------------------------------------------------------

@router.get("/expenses", summary="Auto-categorised expense summary")
async def get_expenses(
    days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return auto-categorised expense breakdown from real bank data."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    summary = summarise_expenses(db, user.id, days=days)
    return {
        "total_spending": summary.total_spending,
        "monthly_average": summary.monthly_average,
        "period_days": summary.period_days,
        "transaction_count": summary.transaction_count,
        "categories": [
            {
                "category": c.category,
                "total": c.total,
                "count": c.count,
                "average": c.average,
                "percentage": c.percentage,
            }
            for c in summary.categories
        ],
    }


@router.get("/income", summary="Income verification")
async def get_income(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Verify income from bank transaction patterns."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    result = verify_income(db, user.id)
    return {
        "total_monthly_income": result.total_monthly_income,
        "analysis_period_days": result.analysis_period_days,
        "transaction_count": result.transaction_count,
        "streams": [
            {
                "description": s.description,
                "average_amount": s.average_amount,
                "frequency": s.frequency,
                "occurrences": s.occurrences,
                "last_received": s.last_received,
                "confidence": s.confidence,
            }
            for s in result.streams
        ],
    }
