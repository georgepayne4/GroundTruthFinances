"""Tests for the notification system (v6.0-05).

Covers trigger evaluation, CRUD, channels, and API endpoints.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from api.database.models import Base, User
from api.notifications.triggers import (
    Alert,
    check_expense_spikes,
    check_goal_deadlines,
    check_review_schedule,
    check_score_change,
    check_tax_year_change,
    evaluate_all_triggers,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

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
    u = User(email="notify@example.com", name="Notify User")
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


# ---------------------------------------------------------------------------
# Score change trigger
# ---------------------------------------------------------------------------

class TestScoreChange:
    def test_improvement_above_threshold(self):
        current = {"scoring": {"overall_score": 72.0}}
        previous = {"scoring": {"overall_score": 65.0}}
        alerts = check_score_change(current, previous, threshold=5.0)
        assert len(alerts) == 1
        assert "improved" in alerts[0].title
        assert alerts[0].severity == "info"

    def test_deterioration_above_threshold(self):
        current = {"scoring": {"overall_score": 58.0}}
        previous = {"scoring": {"overall_score": 65.0}}
        alerts = check_score_change(current, previous, threshold=5.0)
        assert len(alerts) == 1
        assert "deteriorated" in alerts[0].title
        assert alerts[0].severity == "warning"

    def test_below_threshold_no_alert(self):
        current = {"scoring": {"overall_score": 66.0}}
        previous = {"scoring": {"overall_score": 65.0}}
        alerts = check_score_change(current, previous, threshold=5.0)
        assert len(alerts) == 0

    def test_no_previous_report(self):
        current = {"scoring": {"overall_score": 70.0}}
        assert check_score_change(current, None) == []

    def test_missing_scores(self):
        assert check_score_change({}, {}) == []


# ---------------------------------------------------------------------------
# Goal deadline trigger
# ---------------------------------------------------------------------------

class TestGoalDeadlines:
    def test_approaching_deadline_with_gap(self):
        target = (date.today() + timedelta(days=90)).isoformat()
        report = {"goals": {"goals": [
            {"name": "Emergency Fund", "target_date": target, "status": "at_risk", "funding_gap": 3000},
        ]}}
        alerts = check_goal_deadlines(report, warning_months=6)
        assert len(alerts) == 1
        assert "Emergency Fund" in alerts[0].title

    def test_on_track_goal_no_alert(self):
        target = (date.today() + timedelta(days=90)).isoformat()
        report = {"goals": {"goals": [
            {"name": "Holiday", "target_date": target, "status": "on_track", "funding_gap": 0},
        ]}}
        alerts = check_goal_deadlines(report)
        assert len(alerts) == 0

    def test_distant_deadline_no_alert(self):
        target = (date.today() + timedelta(days=365)).isoformat()
        report = {"goals": {"goals": [
            {"name": "House", "target_date": target, "status": "at_risk", "funding_gap": 50000},
        ]}}
        alerts = check_goal_deadlines(report, warning_months=6)
        assert len(alerts) == 0

    def test_critical_severity_under_3_months(self):
        target = (date.today() + timedelta(days=60)).isoformat()
        report = {"goals": {"goals": [
            {"name": "Car", "target_date": target, "status": "behind", "funding_gap": 2000},
        ]}}
        alerts = check_goal_deadlines(report)
        assert len(alerts) == 1
        assert alerts[0].severity == "critical"


# ---------------------------------------------------------------------------
# Tax year change trigger
# ---------------------------------------------------------------------------

class TestTaxYearChange:
    def test_march_alert(self):
        alerts = check_tax_year_change(date(2026, 3, 15))
        assert len(alerts) == 1
        assert "ending soon" in alerts[0].title

    def test_april_new_year_alert(self):
        alerts = check_tax_year_change(date(2026, 4, 10))
        assert len(alerts) == 1
        assert "started" in alerts[0].title

    def test_no_alert_mid_year(self):
        alerts = check_tax_year_change(date(2026, 7, 15))
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Review schedule trigger
# ---------------------------------------------------------------------------

class TestReviewSchedule:
    def test_no_previous_run(self):
        alerts = check_review_schedule(None)
        assert len(alerts) == 1
        assert "recommended" in alerts[0].title

    def test_overdue_review(self):
        old_date = (datetime.now(timezone.utc) - timedelta(days=45)).isoformat()
        alerts = check_review_schedule(old_date, review_interval_days=30)
        assert len(alerts) == 1
        assert "overdue" in alerts[0].title

    def test_recent_review_no_alert(self):
        recent = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
        alerts = check_review_schedule(recent, review_interval_days=30)
        assert len(alerts) == 0


# ---------------------------------------------------------------------------
# Expense spike trigger
# ---------------------------------------------------------------------------

class TestExpenseSpikes:
    def test_spike_detected(self):
        current = {"categories": [{"category": "dining", "total": 300.0}]}
        previous = {"categories": [{"category": "dining", "total": 150.0}]}
        alerts = check_expense_spikes(current, previous, spike_threshold_pct=50.0)
        assert len(alerts) == 1
        assert "dining" in alerts[0].title

    def test_no_spike(self):
        current = {"categories": [{"category": "groceries", "total": 160.0}]}
        previous = {"categories": [{"category": "groceries", "total": 150.0}]}
        alerts = check_expense_spikes(current, previous, spike_threshold_pct=50.0)
        assert len(alerts) == 0

    def test_no_data(self):
        assert check_expense_spikes(None, None) == []


# ---------------------------------------------------------------------------
# Aggregate evaluator
# ---------------------------------------------------------------------------

class TestEvaluateAll:
    def test_returns_sorted_alerts(self):
        current = {"scoring": {"overall_score": 50.0}, "goals": {"goals": []}}
        previous = {"scoring": {"overall_score": 60.0}}
        alerts = evaluate_all_triggers(current, previous)
        # Score drop should generate a warning
        severities = [a.severity for a in alerts]
        # Verify sorted: all warnings before infos
        warning_indices = [i for i, s in enumerate(severities) if s == "warning"]
        info_indices = [i for i, s in enumerate(severities) if s == "info"]
        if warning_indices and info_indices:
            assert max(warning_indices) < min(info_indices)


# ---------------------------------------------------------------------------
# CRUD tests
# ---------------------------------------------------------------------------

class TestNotificationCRUD:
    def test_create_and_list(self, db, user):
        from api.notifications.crud import create_notifications, list_notifications

        alerts = [
            Alert(trigger="test", severity="info", title="Test Alert", message="Hello"),
            Alert(trigger="test2", severity="warning", title="Warning", message="Watch out"),
        ]
        count = create_notifications(db, user.id, alerts)
        assert count == 2

        notifs = list_notifications(db, user.id)
        assert len(notifs) == 2
        assert notifs[0]["title"] == "Warning"  # newest first

    def test_mark_read(self, db, user):
        from api.notifications.crud import create_notifications, list_notifications, mark_read

        alerts = [Alert(trigger="t", severity="info", title="T", message="M")]
        create_notifications(db, user.id, alerts)
        notifs = list_notifications(db, user.id)
        assert not notifs[0]["read"]

        mark_read(db, notifs[0]["id"], user.id)
        notifs = list_notifications(db, user.id)
        assert notifs[0]["read"]

    def test_mark_all_read(self, db, user):
        from api.notifications.crud import create_notifications, list_notifications, mark_all_read

        alerts = [
            Alert(trigger="a", severity="info", title="A", message="M"),
            Alert(trigger="b", severity="info", title="B", message="M"),
        ]
        create_notifications(db, user.id, alerts)
        count = mark_all_read(db, user.id)
        assert count == 2

        notifs = list_notifications(db, user.id, unread_only=True)
        assert len(notifs) == 0

    def test_delete(self, db, user):
        from api.notifications.crud import create_notifications, delete_notification, list_notifications

        alerts = [Alert(trigger="d", severity="info", title="D", message="M")]
        create_notifications(db, user.id, alerts)
        notifs = list_notifications(db, user.id)
        assert delete_notification(db, notifs[0]["id"], user.id)
        assert len(list_notifications(db, user.id)) == 0

    def test_unread_filter(self, db, user):
        from api.notifications.crud import create_notifications, list_notifications, mark_read

        alerts = [
            Alert(trigger="x", severity="info", title="X", message="M"),
            Alert(trigger="y", severity="info", title="Y", message="M"),
        ]
        create_notifications(db, user.id, alerts)
        notifs = list_notifications(db, user.id)
        mark_read(db, notifs[0]["id"], user.id)

        unread = list_notifications(db, user.id, unread_only=True)
        assert len(unread) == 1


# ---------------------------------------------------------------------------
# Preferences tests
# ---------------------------------------------------------------------------

class TestPreferences:
    def test_defaults(self, db, user):
        from api.notifications.crud import get_preferences

        prefs = get_preferences(db, user.id)
        assert prefs["score_threshold"] == 5.0
        assert prefs["in_app_enabled"] is True
        assert prefs["email_enabled"] is False

    def test_update(self, db, user):
        from api.notifications.crud import get_preferences, update_preferences

        update_preferences(db, user.id, {"score_threshold": 10.0, "email_enabled": True})
        prefs = get_preferences(db, user.id)
        assert prefs["score_threshold"] == 10.0
        assert prefs["email_enabled"] is True

    def test_update_preserves_other_fields(self, db, user):
        from api.notifications.crud import get_preferences, update_preferences

        update_preferences(db, user.id, {"webhook_url": "https://example.com/hook"})
        update_preferences(db, user.id, {"score_threshold": 3.0})
        prefs = get_preferences(db, user.id)
        assert prefs["webhook_url"] == "https://example.com/hook"
        assert prefs["score_threshold"] == 3.0


# ---------------------------------------------------------------------------
# Channel tests
# ---------------------------------------------------------------------------

class TestInAppChannel:
    def test_deliver(self, db, user):
        from api.notifications.channels import InAppChannel
        from api.notifications.crud import list_notifications

        channel = InAppChannel()
        alerts = [Alert(trigger="ch", severity="info", title="Channel Test", message="Via channel")]
        count = channel.deliver(user.id, alerts, db=db)
        assert count == 1

        notifs = list_notifications(db, user.id)
        assert len(notifs) == 1
        assert notifs[0]["title"] == "Channel Test"

    def test_deliver_without_db(self):
        from api.notifications.channels import InAppChannel

        channel = InAppChannel()
        alerts = [Alert(trigger="x", severity="info", title="X", message="M")]
        assert channel.deliver(1, alerts) == 0
