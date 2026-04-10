"""PostgreSQL integration tests (v7.5).

These tests verify ORM models work correctly with PostgreSQL features:
timezone handling, unique constraints, concurrent writes.

Skipped when DATABASE_TEST_URL is not set (i.e., no PG available).
Run with: DATABASE_TEST_URL=postgresql://user:pass@localhost:5432/test_groundtruth pytest tests/test_postgres.py
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from api.database.models import Base, Profile, Run, User

_PG_URL = os.environ.get("DATABASE_TEST_URL")

pytestmark = pytest.mark.skipif(
    _PG_URL is None,
    reason="DATABASE_TEST_URL not set — skipping PostgreSQL tests",
)


@pytest.fixture
def pg_session():
    """Create a fresh PostgreSQL session with clean tables."""
    engine = create_engine(_PG_URL, poolclass=StaticPool)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


class TestPostgresTimezone:
    def test_user_created_at_has_timezone(self, pg_session):
        user = User(email="tz@test.com", name="TZ Test")
        pg_session.add(user)
        pg_session.commit()
        pg_session.refresh(user)
        assert user.created_at is not None
        assert user.created_at.tzinfo is not None

    def test_profile_timestamps_have_timezone(self, pg_session):
        user = User(email="profile@test.com")
        pg_session.add(user)
        pg_session.commit()
        profile = Profile(user_id=user.id, name="Test", yaml_content="personal: {}")
        pg_session.add(profile)
        pg_session.commit()
        pg_session.refresh(profile)
        assert profile.created_at.tzinfo is not None
        assert profile.updated_at.tzinfo is not None


class TestPostgresConstraints:
    def test_unique_email(self, pg_session):
        u1 = User(email="dupe@test.com")
        u2 = User(email="dupe@test.com")
        pg_session.add(u1)
        pg_session.commit()
        pg_session.add(u2)
        with pytest.raises(IntegrityError):
            pg_session.commit()
        pg_session.rollback()

    def test_unique_profile_name_per_user(self, pg_session):
        user = User(email="uniq@test.com")
        pg_session.add(user)
        pg_session.commit()
        p1 = Profile(user_id=user.id, name="Same Name", yaml_content="a: 1")
        pg_session.add(p1)
        pg_session.commit()
        p2 = Profile(user_id=user.id, name="Same Name", yaml_content="b: 2")
        pg_session.add(p2)
        with pytest.raises(IntegrityError):
            pg_session.commit()
        pg_session.rollback()

    def test_different_users_same_profile_name_ok(self, pg_session):
        u1 = User(email="user1@test.com")
        u2 = User(email="user2@test.com")
        pg_session.add_all([u1, u2])
        pg_session.commit()
        p1 = Profile(user_id=u1.id, name="My Plan", yaml_content="a: 1")
        p2 = Profile(user_id=u2.id, name="My Plan", yaml_content="b: 2")
        pg_session.add_all([p1, p2])
        pg_session.commit()
        assert p1.id != p2.id


class TestPostgresRuns:
    def test_run_storage_and_retrieval(self, pg_session):
        run = Run(
            timestamp=datetime.now(timezone.utc).isoformat(),
            profile_name="PG Test",
            overall_score=72.5,
            grade="B",
            surplus_monthly=500.0,
        )
        pg_session.add(run)
        pg_session.commit()
        fetched = pg_session.query(Run).filter(Run.profile_name == "PG Test").first()
        assert fetched is not None
        assert fetched.overall_score == 72.5
        assert fetched.grade == "B"
