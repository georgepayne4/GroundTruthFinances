"""api/notifications/router.py — Notification API endpoints (v6.0-05).

Endpoints for listing notifications, managing preferences, and
triggering alert evaluation after an analysis run.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.database.models import User
from api.database.session import get_db
from api.dependencies import get_current_user
from api.notifications import crud as notif_crud
from api.notifications.channels import InAppChannel
from api.notifications.triggers import evaluate_all_triggers

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class PreferenceUpdate(BaseModel):
    score_threshold: float | None = None
    review_interval_days: int | None = None
    email_enabled: bool | None = None
    in_app_enabled: bool | None = None
    webhook_url: str | None = None


class EvaluateRequest(BaseModel):
    """Trigger notification evaluation with current and previous reports."""
    current_report: dict[str, Any]
    previous_report: dict[str, Any] | None = None
    last_run_timestamp: str | None = None
    current_expenses: dict[str, Any] | None = None
    previous_expenses: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Notification endpoints
# ---------------------------------------------------------------------------

@router.get("", summary="List notifications")
async def list_notifications(
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Return notifications for the authenticated user."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    notifs = notif_crud.list_notifications(db, user.id, unread_only=unread_only, limit=limit)
    unread_count = sum(1 for n in notifs if not n["read"])
    return {"notifications": notifs, "count": len(notifs), "unread_count": unread_count}


@router.post("/{notification_id}/read", summary="Mark notification as read")
async def mark_notification_read(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not notif_crud.mark_read(db, notification_id, user.id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "read"}


@router.post("/read-all", summary="Mark all notifications as read")
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    count = notif_crud.mark_all_read(db, user.id)
    return {"marked_read": count}


@router.delete("/{notification_id}", summary="Delete a notification")
async def delete_notification(
    notification_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not notif_crud.delete_notification(db, notification_id, user.id):
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Preferences
# ---------------------------------------------------------------------------

@router.get("/preferences", summary="Get notification preferences")
async def get_preferences(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return notif_crud.get_preferences(db, user.id)


@router.put("/preferences", summary="Update notification preferences")
async def update_preferences(
    request: PreferenceUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    updates = {k: v for k, v in request.model_dump().items() if v is not None}
    return notif_crud.update_preferences(db, user.id, updates)


# ---------------------------------------------------------------------------
# Trigger evaluation
# ---------------------------------------------------------------------------

@router.post("/evaluate", summary="Evaluate notification triggers")
async def evaluate_triggers(
    request: EvaluateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Run all notification triggers and deliver alerts via configured channels."""
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    prefs = notif_crud.get_preferences(db, user.id)

    alerts = evaluate_all_triggers(
        current_report=request.current_report,
        previous_report=request.previous_report,
        last_run_timestamp=request.last_run_timestamp,
        current_expenses=request.current_expenses,
        previous_expenses=request.previous_expenses,
        score_threshold=prefs["score_threshold"],
        review_interval_days=prefs["review_interval_days"],
    )

    delivered = 0
    if prefs["in_app_enabled"] and alerts:
        channel = InAppChannel()
        delivered += channel.deliver(user.id, alerts, db=db)

    return {
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
        "alert_count": len(alerts),
        "delivered": delivered,
    }
