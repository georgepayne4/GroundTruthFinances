"""api/database/models.py — SQLAlchemy ORM models (v5.3-04).

Schema:
  users      — API consumers (email-keyed, per-user API key)
  profiles   — Stored financial profiles per user
  reports    — Full JSON reports generated from profiles
  assumptions — Versioned assumption sets (tax year keyed)
  runs       — Lightweight metric snapshots (migrated from v5.2-05 SQLite)
  audit_log  — Who called what endpoint, when (v5.3-04)
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
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
    api_key_hash = Column(String(128), nullable=True, index=True)
    clerk_user_id = Column(String(255), unique=True, nullable=True, index=True)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

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


class BankConnection(Base):
    """An Open Banking consent linking a user to a bank via TrueLayer/Plaid (v6.0-02)."""
    __tablename__ = "bank_connections"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    provider = Column(String(32), nullable=False, default="truelayer")
    institution_name = Column(String(255), nullable=True)
    access_token_enc = Column(Text, nullable=False)
    refresh_token_enc = Column(Text, nullable=False)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    consent_granted_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    status = Column(String(32), nullable=False, default="active")  # active, expired, revoked
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User", backref="bank_connections")
    accounts = relationship("BankAccount", back_populates="connection", cascade="all, delete-orphan")


class BankAccount(Base):
    """A bank account discovered via Open Banking (v6.0-02)."""
    __tablename__ = "bank_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    connection_id = Column(Integer, ForeignKey("bank_connections.id", ondelete="CASCADE"), nullable=False, index=True)
    external_account_id = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    account_type = Column(String(32), nullable=False, default="current")
    currency = Column(String(8), nullable=False, default="GBP")
    balance = Column(Float, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)

    connection = relationship("BankConnection", back_populates="accounts")
    transactions = relationship("BankTransaction", back_populates="account", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("connection_id", "external_account_id", name="uq_connection_ext_account"),
    )


class BankTransaction(Base):
    """A transaction fetched via Open Banking (v6.0-02)."""
    __tablename__ = "bank_transactions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("bank_accounts.id", ondelete="CASCADE"), nullable=False, index=True)
    external_transaction_id = Column(String(255), nullable=False)
    timestamp = Column(DateTime(timezone=True), nullable=False)
    amount = Column(Float, nullable=False)
    currency = Column(String(8), nullable=False, default="GBP")
    description = Column(String(512), nullable=True)
    transaction_type = Column(String(64), nullable=True)
    category = Column(String(64), nullable=True)
    merchant_name = Column(String(255), nullable=True)

    account = relationship("BankAccount", back_populates="transactions")

    __table_args__ = (
        UniqueConstraint("account_id", "external_transaction_id", name="uq_account_ext_txn"),
        Index("ix_bank_txn_timestamp", "timestamp"),
    )


class Notification(Base):
    """In-app notification for a user (v6.0-05)."""
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    trigger = Column(String(64), nullable=False)
    severity = Column(String(16), nullable=False, default="info")
    title = Column(String(512), nullable=False)
    message = Column(Text, nullable=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_notification_user_created", "user_id", "created_at"),
    )


class NotificationPreference(Base):
    """Per-user notification preferences (v6.0-05)."""
    __tablename__ = "notification_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    score_threshold = Column(Float, nullable=False, default=5.0)
    review_interval_days = Column(Integer, nullable=False, default=30)
    email_enabled = Column(Boolean, nullable=False, default=False)
    in_app_enabled = Column(Boolean, nullable=False, default=True)
    webhook_url = Column(String(512), nullable=True)


class AuditLog(Base):
    """Records API calls for compliance and debugging (v5.3-04)."""
    __tablename__ = "audit_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    endpoint = Column(String(255), nullable=False)
    method = Column(String(10), nullable=False)
    status_code = Column(Integer, nullable=True)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    __table_args__ = (
        Index("ix_audit_log_timestamp", "timestamp"),
    )
