"""api/notifications/crud.py — Notification persistence (v6.0-05).

CRUD operations for in-app notifications and user preferences.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from api.database.models import Notification, NotificationPreference
from api.notifications.triggers import Alert

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def create_notifications(db: Session, user_id: int, alerts: list[Alert]) -> int:
    """Persist alerts as in-app notifications. Returns count created."""
    count = 0
    for alert in alerts:
        notif = Notification(
            user_id=user_id,
            trigger=alert.trigger,
            severity=alert.severity,
            title=alert.title,
            message=alert.message,
        )
        db.add(notif)
        count += 1
    if count:
        db.commit()
    return count


def list_notifications(
    db: Session,
    user_id: int,
    unread_only: bool = False,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """Return notifications for a user, newest first."""
    query = db.query(Notification).filter(Notification.user_id == user_id)
    if unread_only:
        query = query.filter(Notification.read_at.is_(None))
    rows = query.order_by(Notification.created_at.desc()).limit(limit).all()
    return [
        {
            "id": n.id,
            "trigger": n.trigger,
            "severity": n.severity,
            "title": n.title,
            "message": n.message,
            "read": n.read_at is not None,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]


def mark_read(db: Session, notification_id: int, user_id: int) -> bool:
    """Mark a notification as read. Returns True if found and updated."""
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if notif is None:
        return False
    notif.read_at = datetime.now(timezone.utc)
    db.commit()
    return True


def mark_all_read(db: Session, user_id: int) -> int:
    """Mark all notifications as read for a user. Returns count updated."""
    count = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.read_at.is_(None))
        .update({"read_at": datetime.now(timezone.utc)})
    )
    db.commit()
    return count


def delete_notification(db: Session, notification_id: int, user_id: int) -> bool:
    notif = (
        db.query(Notification)
        .filter(Notification.id == notification_id, Notification.user_id == user_id)
        .first()
    )
    if notif is None:
        return False
    db.delete(notif)
    db.commit()
    return True


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

def get_preferences(db: Session, user_id: int) -> dict[str, Any]:
    """Return notification preferences for a user, or defaults."""
    pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
    if pref is None:
        return {
            "score_threshold": 5.0,
            "review_interval_days": 30,
            "email_enabled": False,
            "in_app_enabled": True,
            "webhook_url": None,
        }
    return {
        "score_threshold": pref.score_threshold,
        "review_interval_days": pref.review_interval_days,
        "email_enabled": pref.email_enabled,
        "in_app_enabled": pref.in_app_enabled,
        "webhook_url": pref.webhook_url,
    }


def update_preferences(db: Session, user_id: int, updates: dict[str, Any]) -> dict[str, Any]:
    """Update notification preferences. Creates if not exists."""
    pref = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
    if pref is None:
        pref = NotificationPreference(user_id=user_id)
        db.add(pref)

    for key in ("score_threshold", "review_interval_days", "email_enabled", "in_app_enabled", "webhook_url"):
        if key in updates:
            setattr(pref, key, updates[key])

    db.commit()
    db.refresh(pref)
    return get_preferences(db, user_id)
