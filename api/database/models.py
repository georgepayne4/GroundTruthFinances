"""api/database/models.py — SQLAlchemy ORM models (v5.3-02).

Schema:
  users      — API consumers (email-keyed)
  profiles   — Stored financial profiles per user
  reports    — Full JSON reports generated from profiles
  assumptions — Versioned assumption sets (tax year keyed)
  runs       — Lightweight metric snapshots (migrated from v5.2-05 SQLite)
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    """Shared base for all ORM models."""


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    api_key_hash = Column(String(128), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    profiles = relationship("Profile", back_populates="user", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    yaml_content = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    user = relationship("User", back_populates="profiles")
    reports = relationship("Report", back_populates="profile", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_user_profile_name"),
    )


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, autoincrement=True)
    profile_id = Column(Integer, ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    json_content = Column(Text, nullable=False)
    overall_score = Column(Float, nullable=True)
    grade = Column(String(4), nullable=True)
    generated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    profile = relationship("Profile", back_populates="reports")

    __table_args__ = (
        Index("ix_reports_generated_at", "generated_at"),
    )


class Assumption(Base):
    __tablename__ = "assumptions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    tax_year = Column(String(16), nullable=False, unique=True)
    yaml_content = Column(Text, nullable=False)
    effective_from = Column(String(10), nullable=True)
    effective_to = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)


class Run(Base):
    """Lightweight metric snapshot — migrated from v5.2-05 SQLite history.

    Standalone table (no FK to profiles/reports) so it can serve both
    API and CLI-migrated data. The full_report_json column is retained
    for back-fill capability.
    """
    __tablename__ = "runs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(String(64), nullable=False)
    profile_name = Column(String(255), nullable=True, index=True)
    profile_path = Column(String(512), nullable=True)
    overall_score = Column(Float, nullable=True)
    grade = Column(String(4), nullable=True)
    surplus_monthly = Column(Float, nullable=True)
    net_worth = Column(Float, nullable=True)
    debt_total = Column(Float, nullable=True)
    savings_rate_pct = Column(Float, nullable=True)
    pension_replacement_pct = Column(Float, nullable=True)
    emergency_fund_months = Column(Float, nullable=True)
    goals_on_track = Column(Integer, nullable=True)
    goals_at_risk = Column(Integer, nullable=True)
    goals_unreachable = Column(Integer, nullable=True)
    high_interest_debt_count = Column(Integer, nullable=True)
    mortgage_readiness = Column(String(32), nullable=True)
    full_report_json = Column(Text, nullable=True)
