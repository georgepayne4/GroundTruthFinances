"""api/banking/truelayer.py — TrueLayer Data API client (v6.0-02).

Handles OAuth2 consent flow and data retrieval for UK Open Banking.
Supports both sandbox and production environments.

Required env vars:
  TRUELAYER_CLIENT_ID
  TRUELAYER_CLIENT_SECRET
  TRUELAYER_REDIRECT_URI  (e.g. http://localhost:8000/api/v1/banking/callback)
  TRUELAYER_SANDBOX       (set to "1" or "true" for sandbox mode, default: true)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Environment config
# ---------------------------------------------------------------------------

_SANDBOX_AUTH_URL = "https://auth.truelayer-sandbox.com"
_PROD_AUTH_URL = "https://auth.truelayer.com"
_SANDBOX_API_URL = "https://api.truelayer-sandbox.com"
_PROD_API_URL = "https://api.truelayer.com"


def _is_sandbox() -> bool:
    return os.environ.get("TRUELAYER_SANDBOX", "1").lower() in ("1", "true", "yes")


def _auth_base() -> str:
    return _SANDBOX_AUTH_URL if _is_sandbox() else _PROD_AUTH_URL


def _api_base() -> str:
    return _SANDBOX_API_URL if _is_sandbox() else _PROD_API_URL


def _client_id() -> str:
    val = os.environ.get("TRUELAYER_CLIENT_ID", "")
    if not val:
        raise RuntimeError("TRUELAYER_CLIENT_ID environment variable is not set")
    return val


def _client_secret() -> str:
    val = os.environ.get("TRUELAYER_CLIENT_SECRET", "")
    if not val:
        raise RuntimeError("TRUELAYER_CLIENT_SECRET environment variable is not set")
    return val


def _redirect_uri() -> str:
    return os.environ.get(
        "TRUELAYER_REDIRECT_URI",
        "http://localhost:8000/api/v1/banking/callback",
    )


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class TrueLayerTokens:
    """OAuth2 token pair from TrueLayer."""
    access_token: str
    refresh_token: str
    expires_in: int  # seconds


@dataclass
class TrueLayerAccount:
    """Normalised account from TrueLayer Data API."""
    account_id: str
    display_name: str
    provider_name: str
    account_type: str
    currency: str
    balance: float | None = None


@dataclass
class TrueLayerTransaction:
    """Normalised transaction from TrueLayer Data API."""
    transaction_id: str
    timestamp: str
    amount: float
    currency: str
    description: str
    transaction_type: str
    category: str
    merchant_name: str | None = None
    running_balance: float | None = None


# ---------------------------------------------------------------------------
# OAuth2 flow
# ---------------------------------------------------------------------------

def build_auth_url(state: str | None = None) -> str:
    """Generate the TrueLayer authorization URL for user consent.

    The user is redirected here to grant read-only bank access.
    """
    params = {
        "response_type": "code",
        "client_id": _client_id(),
        "scope": "info accounts balance transactions",
        "redirect_uri": _redirect_uri(),
        "providers": "uk-ob-all uk-oauth-all",
    }
    if state:
        params["state"] = state
    return f"{_auth_base()}/?{urlencode(params)}"


async def exchange_code(code: str) -> TrueLayerTokens:
    """Exchange an authorization code for access + refresh tokens."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_auth_base()}/connect/token",
            data={
                "grant_type": "authorization_code",
                "client_id": _client_id(),
                "client_secret": _client_secret(),
                "redirect_uri": _redirect_uri(),
                "code": code,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return TrueLayerTokens(
        access_token=data["access_token"],
        refresh_token=data["refresh_token"],
        expires_in=data.get("expires_in", 3600),
    )


async def refresh_tokens(refresh_token: str) -> TrueLayerTokens:
    """Refresh an expired access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{_auth_base()}/connect/token",
            data={
                "grant_type": "refresh_token",
                "client_id": _client_id(),
                "client_secret": _client_secret(),
                "refresh_token": refresh_token,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    return TrueLayerTokens(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token", refresh_token),
        expires_in=data.get("expires_in", 3600),
    )


# ---------------------------------------------------------------------------
# Data API
# ---------------------------------------------------------------------------

def _auth_headers(access_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {access_token}"}


async def fetch_accounts(access_token: str) -> list[TrueLayerAccount]:
    """Fetch all accounts from TrueLayer Data API."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_api_base()}/data/v1/accounts",
            headers=_auth_headers(access_token),
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])

    accounts = []
    for r in results:
        # Fetch balance for each account
        balance = None
        try:
            bal_resp = await _fetch_balance(client, access_token, r["account_id"])
            balance = bal_resp
        except Exception:
            logger.debug("Could not fetch balance for %s", r["account_id"])

        accounts.append(TrueLayerAccount(
            account_id=r["account_id"],
            display_name=r.get("display_name", r.get("account_id", "")),
            provider_name=r.get("provider", {}).get("display_name", "Unknown"),
            account_type=_map_account_type(r.get("account_type", "TRANSACTION")),
            currency=r.get("currency", "GBP"),
            balance=balance,
        ))
    return accounts


async def _fetch_balance(client: httpx.AsyncClient, access_token: str, account_id: str) -> float | None:
    """Fetch current balance for a single account."""
    resp = await client.get(
        f"{_api_base()}/data/v1/accounts/{account_id}/balance",
        headers=_auth_headers(access_token),
    )
    resp.raise_for_status()
    results = resp.json().get("results", [])
    if results:
        return results[0].get("current", None)
    return None


async def fetch_transactions(
    access_token: str,
    account_id: str,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[TrueLayerTransaction]:
    """Fetch transactions for an account from TrueLayer Data API."""
    params: dict[str, str] = {}
    if from_date:
        params["from"] = from_date.isoformat()
    if to_date:
        params["to"] = to_date.isoformat()

    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{_api_base()}/data/v1/accounts/{account_id}/transactions",
            headers=_auth_headers(access_token),
            params=params,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])

    return [
        TrueLayerTransaction(
            transaction_id=t.get("transaction_id", ""),
            timestamp=t.get("timestamp", ""),
            amount=t.get("amount", 0.0),
            currency=t.get("currency", "GBP"),
            description=t.get("description", ""),
            transaction_type=t.get("transaction_type", ""),
            category=t.get("transaction_category", "UNKNOWN"),
            merchant_name=t.get("merchant_name"),
            running_balance=t.get("running_balance", {}).get("amount") if isinstance(t.get("running_balance"), dict) else None,
        )
        for t in results
    ]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ACCOUNT_TYPE_MAP: dict[str, str] = {
    "TRANSACTION": "current",
    "SAVINGS": "savings",
    "CREDIT_CARD": "credit_card",
    "LOAN": "loan",
    "MORTGAGE": "mortgage",
}


def _map_account_type(truelayer_type: str) -> str:
    return _ACCOUNT_TYPE_MAP.get(truelayer_type.upper(), "current")
