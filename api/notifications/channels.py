"""api/notifications/channels.py — Delivery channels for notifications (v6.0-05).

Defines an abstract channel interface and concrete implementations:
  - InAppChannel: stores notifications in the database for UI retrieval
  - EmailChannel: sends email via SMTP (stub — requires mail server config)
  - WebhookChannel: POSTs JSON to a user-configured URL

Channel selection is per-user via notification preferences.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx
from sqlalchemy.orm import Session

from api.notifications.triggers import Alert

logger = logging.getLogger(__name__)


class NotificationChannel(ABC):
    """Abstract base for notification delivery."""

    @abstractmethod
    def deliver(self, user_id: int, alerts: list[Alert], db: Session | None = None) -> int:
        """Deliver alerts to the user. Returns count of successfully delivered."""


# ---------------------------------------------------------------------------
# In-app (database) channel
# ---------------------------------------------------------------------------

class InAppChannel(NotificationChannel):
    """Store notifications in the database for retrieval via API."""

    def deliver(self, user_id: int, alerts: list[Alert], db: Session | None = None) -> int:
        if db is None:
            logger.warning("InAppChannel requires a database session")
            return 0

        from api.notifications.crud import create_notifications
        return create_notifications(db, user_id, alerts)


# ---------------------------------------------------------------------------
# Email channel (stub)
# ---------------------------------------------------------------------------

class EmailChannel(NotificationChannel):
    """Send notifications via email.

    Requires SMTP configuration via environment variables:
      GROUNDTRUTH_SMTP_HOST, GROUNDTRUTH_SMTP_PORT,
      GROUNDTRUTH_SMTP_USER, GROUNDTRUTH_SMTP_PASS,
      GROUNDTRUTH_SMTP_FROM
    """

    def deliver(self, user_id: int, alerts: list[Alert], db: Session | None = None) -> int:
        import os
        host = os.environ.get("GROUNDTRUTH_SMTP_HOST")
        if not host:
            logger.debug("Email channel not configured (GROUNDTRUTH_SMTP_HOST not set)")
            return 0

        # Full SMTP implementation deferred until mail server is configured.
        # For now, log the intent. The interface is stable.
        for alert in alerts:
            logger.info("Would email user %d: [%s] %s", user_id, alert.severity, alert.title)
        return len(alerts)


# ---------------------------------------------------------------------------
# Webhook channel
# ---------------------------------------------------------------------------

class WebhookChannel(NotificationChannel):
    """POST alerts as JSON to a user-configured webhook URL."""

    def __init__(self, url: str, secret: str | None = None) -> None:
        self._url = url
        self._secret = secret

    def deliver(self, user_id: int, alerts: list[Alert], db: Session | None = None) -> int:
        payload = {
            "user_id": user_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "alerts": [
                {
                    "trigger": a.trigger,
                    "severity": a.severity,
                    "title": a.title,
                    "message": a.message,
                    "data": a.data,
                }
                for a in alerts
            ],
        }

        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._secret:
            headers["X-Webhook-Secret"] = self._secret

        try:
            resp = httpx.post(self._url, json=payload, headers=headers, timeout=10.0)
            resp.raise_for_status()
            logger.info("Webhook delivered %d alerts to %s (status %d)", len(alerts), self._url, resp.status_code)
            return len(alerts)
        except Exception as exc:
            logger.error("Webhook delivery to %s failed: %s", self._url, exc)
            return 0
