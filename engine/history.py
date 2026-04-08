"""
history.py — Historical Run Database (v5.2-05)

Optional SQLite-backed run history. Records key metrics from each
completed engine run, lets you list past runs, and produces structured
diffs between any two runs.

Design notes:
- Stdlib `sqlite3` only. No SQLAlchemy / Alembic until v5.3.
- Schema versioned via a `meta` table; future migrations bump the version.
- The full report JSON is stored alongside extracted metrics so we can
  back-fill new diff fields without re-running the engine.
- Fully optional: callers can skip recording, the engine works without
  the database, and a missing/corrupt DB is reported via ImportHistoryError
  rather than crashing the run.
"""

from __future__ import annotations

import contextlib
import json
import logging
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from engine.exceptions import GroundTruthError

logger = logging.getLogger(__name__)


SCHEMA_VERSION = 1


class HistoryError(GroundTruthError):
    """Raised when the history database cannot be opened or queried."""


# ---------------------------------------------------------------------------
# Schema management
# ---------------------------------------------------------------------------

_RUNS_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    profile_name TEXT,
    profile_path TEXT,
    overall_score REAL,
    grade TEXT,
    surplus_monthly REAL,
    net_worth REAL,
    debt_total REAL,
    savings_rate_pct REAL,
    pension_replacement_pct REAL,
    emergency_fund_months REAL,
    goals_on_track INTEGER,
    goals_at_risk INTEGER,
    goals_unreachable INTEGER,
    high_interest_debt_count INTEGER,
    mortgage_readiness TEXT,
    full_report_json TEXT
);
"""

_META_TABLE_DDL = """
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create tables if missing and stamp the schema version."""
    cur = conn.cursor()
    cur.execute(_META_TABLE_DDL)
    cur.execute(_RUNS_TABLE_DDL)
    cur.execute(
        "INSERT OR IGNORE INTO meta (key, value) VALUES (?, ?)",
        ("schema_version", str(SCHEMA_VERSION)),
    )
    conn.commit()


@contextmanager
def _connect(db_path: str | Path) -> Iterator[sqlite3.Connection]:
    """Open the SQLite DB, ensure the schema is current, yield the connection."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        _ensure_schema(conn)
        yield conn
    except sqlite3.Error as e:
        raise HistoryError(f"SQLite error on {db_path}: {e}") from e
    finally:
        with contextlib.suppress(Exception):
            conn.close()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def record_run(
    report: dict[str, Any],
    db_path: str | Path,
    profile: dict[str, Any] | None = None,
    profile_path: str | Path | None = None,
) -> int:
    """Persist a completed report to the history DB. Returns the new row id.

    Idempotent on the report dict — calling twice creates two rows
    (history is append-only by design). The profile dict is optional but
    enables net-worth and emergency-fund-months tracking that the report
    alone doesn't expose.
    """
    metrics = _extract_metrics(report, profile)
    payload_json = json.dumps(report, default=str)

    with _connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO runs (
                timestamp, profile_name, profile_path,
                overall_score, grade, surplus_monthly, net_worth, debt_total,
                savings_rate_pct, pension_replacement_pct, emergency_fund_months,
                goals_on_track, goals_at_risk, goals_unreachable,
                high_interest_debt_count, mortgage_readiness,
                full_report_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                metrics["timestamp"],
                metrics["profile_name"],
                str(profile_path) if profile_path else None,
                metrics["overall_score"],
                metrics["grade"],
                metrics["surplus_monthly"],
                metrics["net_worth"],
                metrics["debt_total"],
                metrics["savings_rate_pct"],
                metrics["pension_replacement_pct"],
                metrics["emergency_fund_months"],
                metrics["goals_on_track"],
                metrics["goals_at_risk"],
                metrics["goals_unreachable"],
                metrics["high_interest_debt_count"],
                metrics["mortgage_readiness"],
                payload_json,
            ),
        )
        conn.commit()
        run_id = cur.lastrowid
    logger.info(
        "Recorded run %d for profile %s (score %.0f)",
        run_id, metrics["profile_name"], metrics["overall_score"] or 0,
    )
    return run_id


def list_runs(
    db_path: str | Path,
    limit: int = 10,
    profile_name: str | None = None,
) -> list[dict[str, Any]]:
    """Return the most recent runs as a list of dicts (newest first)."""
    with _connect(db_path) as conn:
        cur = conn.cursor()
        if profile_name:
            cur.execute(
                """
                SELECT id, timestamp, profile_name, overall_score, grade,
                       surplus_monthly, net_worth, debt_total,
                       savings_rate_pct, pension_replacement_pct,
                       emergency_fund_months, goals_on_track, goals_at_risk
                FROM runs
                WHERE profile_name = ?
                ORDER BY id DESC
                LIMIT ?
                """,
                (profile_name, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, timestamp, profile_name, overall_score, grade,
                       surplus_monthly, net_worth, debt_total,
                       savings_rate_pct, pension_replacement_pct,
                       emergency_fund_months, goals_on_track, goals_at_risk
                FROM runs
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            )
        return [dict(row) for row in cur.fetchall()]


def diff_runs(
    db_path: str | Path,
    run_id_a: int,
    run_id_b: int,
) -> dict[str, Any]:
    """Compare two runs (a = older, b = newer). Returns a structured diff.

    Numeric fields produce {old, new, delta, delta_pct}. Categorical fields
    (grade, mortgage_readiness) produce {old, new, changed: bool}.
    """
    with _connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM runs WHERE id IN (?, ?)", (run_id_a, run_id_b))
        rows = {row["id"]: dict(row) for row in cur.fetchall()}

    missing = [rid for rid in (run_id_a, run_id_b) if rid not in rows]
    if missing:
        raise HistoryError(f"Run id(s) not found: {missing}")

    a, b = rows[run_id_a], rows[run_id_b]

    numeric_fields = (
        "overall_score", "surplus_monthly", "net_worth", "debt_total",
        "savings_rate_pct", "pension_replacement_pct", "emergency_fund_months",
        "goals_on_track", "goals_at_risk", "goals_unreachable",
        "high_interest_debt_count",
    )
    categorical_fields = ("grade", "mortgage_readiness", "profile_name")

    numeric: dict[str, dict[str, Any]] = {}
    for f in numeric_fields:
        numeric[f] = _numeric_diff(a.get(f), b.get(f))

    categorical: dict[str, dict[str, Any]] = {}
    for f in categorical_fields:
        old, new = a.get(f), b.get(f)
        categorical[f] = {"old": old, "new": new, "changed": old != new}

    return {
        "from": {"id": a["id"], "timestamp": a["timestamp"]},
        "to": {"id": b["id"], "timestamp": b["timestamp"]},
        "numeric": numeric,
        "categorical": categorical,
        "summary": _diff_summary(numeric, categorical),
    }


def latest_two_runs(db_path: str | Path, profile_name: str | None = None) -> tuple[int, int] | None:
    """Return (older_id, newer_id) of the two most recent runs, or None."""
    runs = list_runs(db_path, limit=2, profile_name=profile_name)
    if len(runs) < 2:
        return None
    return runs[1]["id"], runs[0]["id"]


# ---------------------------------------------------------------------------
# Metric extraction
# ---------------------------------------------------------------------------

def _extract_metrics(
    report: dict[str, Any],
    profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Pull the key fields out of a full report dict (and optional profile)."""
    meta = report.get("meta", {})
    scoring = report.get("scoring", {})
    cashflow = report.get("cashflow", {})
    debt = report.get("debt", {})
    goals = report.get("goals", {})
    investments = report.get("investments", {})
    mortgage = report.get("mortgage", {})

    surplus = cashflow.get("surplus", {}).get("monthly")
    savings_rate = cashflow.get("savings_rate", {}).get("basic_pct")

    debt_summary = debt.get("summary", {})
    debt_total = debt_summary.get("total_balance")
    high_interest_count = debt_summary.get("high_interest_debt_count", 0)

    goal_summary = goals.get("summary", {})
    goals_on_track = goal_summary.get("on_track", 0)
    goals_at_risk = goal_summary.get("at_risk", 0)
    goals_unreachable = goal_summary.get("unreachable", 0)

    pension = investments.get("pension_analysis", {})
    pension_repl = pension.get("income_replacement_ratio_pct")

    # Net worth and emergency fund months come from the profile, not the report
    net_worth: float | None = None
    ef_months: float | None = None
    if profile:
        net_worth = profile.get("_net_worth")
        sav = profile.get("savings", {}) or {}
        exp = profile.get("expenses", {}) or {}
        monthly_exp = exp.get("_total_monthly", 0) if isinstance(exp, dict) else 0
        ef = sav.get("emergency_fund", 0) if isinstance(sav, dict) else 0
        if monthly_exp > 0:
            ef_months = round(ef / monthly_exp, 1)

    return {
        "timestamp": meta.get("generated_at") or datetime.now(timezone.utc).isoformat(),
        "profile_name": meta.get("profile_name"),
        "overall_score": scoring.get("overall_score"),
        "grade": scoring.get("grade"),
        "surplus_monthly": surplus,
        "net_worth": net_worth,
        "debt_total": debt_total,
        "savings_rate_pct": savings_rate,
        "pension_replacement_pct": pension_repl,
        "emergency_fund_months": ef_months,
        "goals_on_track": goals_on_track,
        "goals_at_risk": goals_at_risk,
        "goals_unreachable": goals_unreachable,
        "high_interest_debt_count": high_interest_count,
        "mortgage_readiness": mortgage.get("readiness"),
    }


def _numeric_diff(old: Any, new: Any) -> dict[str, Any]:
    """Diff a single numeric field with delta and percentage change."""
    if old is None or new is None:
        return {"old": old, "new": new, "delta": None, "delta_pct": None}
    delta = new - old
    delta_pct = (delta / old * 100) if old not in (0, 0.0) else None
    return {
        "old": round(old, 2) if isinstance(old, float) else old,
        "new": round(new, 2) if isinstance(new, float) else new,
        "delta": round(delta, 2),
        "delta_pct": round(delta_pct, 1) if delta_pct is not None else None,
    }


def _diff_summary(
    numeric: dict[str, dict[str, Any]],
    categorical: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Headline summary of the most material changes."""
    score = numeric.get("overall_score", {})
    surplus = numeric.get("surplus_monthly", {})
    net_worth = numeric.get("net_worth", {})
    debt = numeric.get("debt_total", {})

    direction = "unchanged"
    if score.get("delta") is not None:
        if score["delta"] > 0:
            direction = "improved"
        elif score["delta"] < 0:
            direction = "declined"

    return {
        "direction": direction,
        "score_delta": score.get("delta"),
        "surplus_delta": surplus.get("delta"),
        "net_worth_delta": net_worth.get("delta"),
        "debt_delta": debt.get("delta"),
        "grade_changed": categorical.get("grade", {}).get("changed", False),
    }
