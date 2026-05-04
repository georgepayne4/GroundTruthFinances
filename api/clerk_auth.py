"""api/clerk_auth.py — Clerk JWT verification for the GroundTruth API (v9.3).

Verifies Clerk session tokens using JWKS (RS256). Caches public keys in memory
and re-fetches on unknown kid (key rotation). Uses httpx for HTTP calls.

Hobby-tier Clerk JWTs contain sub (user ID) but no email claim.
On first login, we call the Clerk Backend API to fetch the user's email.
"""

from __future__ import annotations

import base64
import logging
import os

import httpx
import jwt

logger = logging.getLogger(__name__)

_CLERK_SECRET_KEY = os.environ.get("CLERK_SECRET_KEY", "")
# Backend prefers the un-prefixed name in root `.env`; falls back to the
# Vite-prefixed name (used by the frontend in `web/.env.local`) for setups
# where only one is provisioned.
_CLERK_PUBLISHABLE_KEY = (
    os.environ.get("CLERK_PUBLISHABLE_KEY", "")
    or os.environ.get("VITE_CLERK_PUBLISHABLE_KEY", "")
)

# Derive the Clerk Frontend API domain from the publishable key.
# pk_test_<base64-encoded-domain> -> decode to get e.g. "above-parakeet-10.clerk.accounts.dev$"
_CLERK_FRONTEND_API = ""


def _derive_frontend_api() -> str:
    global _CLERK_FRONTEND_API
    if _CLERK_FRONTEND_API:
        return _CLERK_FRONTEND_API
    pk = (
        _CLERK_PUBLISHABLE_KEY
        or os.environ.get("CLERK_PUBLISHABLE_KEY", "")
        or os.environ.get("VITE_CLERK_PUBLISHABLE_KEY", "")
    )
    if not pk:
        return ""
    # Strip pk_test_ or pk_live_ prefix
    encoded = pk.split("_", 2)[-1] if pk.count("_") >= 2 else ""
    if not encoded:
        return ""
    # Base64 decode (add padding)
    padded = encoded + "=" * (-len(encoded) % 4)
    try:
        domain = base64.b64decode(padded).decode("utf-8").rstrip("$")
        _CLERK_FRONTEND_API = domain
        return domain
    except Exception:
        logger.warning("Failed to decode Clerk publishable key")
        return ""


# JWKS cache: kid -> PyJWK
_jwks_cache: dict[str, jwt.PyJWK] = {}


def _fetch_jwks() -> None:
    """Fetch JWKS from Clerk and populate the cache."""
    domain = _derive_frontend_api()
    if not domain:
        return
    url = f"https://{domain}/.well-known/jwks.json"
    try:
        resp = httpx.get(url, timeout=10)
        resp.raise_for_status()
        jwks_data = resp.json()
        _jwks_cache.clear()
        for key_data in jwks_data.get("keys", []):
            kid = key_data.get("kid")
            if kid:
                _jwks_cache[kid] = jwt.PyJWK(key_data)
        logger.info("Fetched %d JWKS keys from Clerk", len(_jwks_cache))
    except Exception as e:
        logger.warning("Failed to fetch Clerk JWKS: %s", e)


def _get_signing_key(kid: str) -> jwt.PyJWK | None:
    """Get a signing key by kid, re-fetching JWKS if not cached."""
    if kid not in _jwks_cache:
        _fetch_jwks()
    return _jwks_cache.get(kid)


def verify_clerk_token(token: str) -> dict:
    """Verify a Clerk session JWT and return decoded claims.

    Raises ValueError on invalid/expired/unverifiable tokens.
    """
    if not _derive_frontend_api():
        raise ValueError("Clerk not configured")

    try:
        # Decode header to get kid without verification
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not kid:
            raise ValueError("No kid in JWT header")

        signing_key = _get_signing_key(kid)
        if not signing_key:
            raise ValueError(f"Unknown signing key: {kid}")

        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            options={"verify_aud": False},
        )
        return claims
    except jwt.ExpiredSignatureError as exc:
        raise ValueError("Token expired") from exc
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}") from exc


def get_clerk_user_email(clerk_user_id: str) -> str | None:
    """Fetch a Clerk user's primary email via the Backend API.

    Returns None if the API call fails or no email is found.
    """
    if not _CLERK_SECRET_KEY:
        return None
    try:
        resp = httpx.get(
            f"https://api.clerk.com/v1/users/{clerk_user_id}",
            headers={"Authorization": f"Bearer {_CLERK_SECRET_KEY}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        emails = data.get("email_addresses", [])
        primary_id = data.get("primary_email_address_id")
        for email in emails:
            if email.get("id") == primary_id:
                return email.get("email_address")
        if emails:
            return emails[0].get("email_address")
        return None
    except Exception as e:
        logger.warning("Failed to fetch Clerk user email: %s", e)
        return None
