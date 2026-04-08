"""Tests for engine/history.py — SQLite-backed run history (v5.2-05)."""

from __future__ import annotations

import sqlite3

import pytest

from engine.history import (
    SCHEMA_VERSION,
    HistoryError,
    diff_runs,
    latest_two_runs,
    list_runs,
    record_run,
)


def _make_report(
    *,
    score: float = 70.0,
    grade: str = "B",
    surplus: float = 800.0,
    debt_total: float = 5000.0,
    profile_name: str = "Test User",
    high_interest_count: int = 1,
    on_track: int = 2,
    at_risk: int = 1,
    unreachable: int = 0,
    pension_repl: float = 55.0,
    savings_rate: float = 18.0,
    mortgage_readiness: str = "Almost ready",
) -> dict:
    """Build a minimal report dict that satisfies _extract_metrics."""
    return {
        "meta": {
            "profile_name": profile_name,
            "generated_at": "2026-04-01T12:00:00+00:00",
        },
        "scoring": {"overall_score": score, "grade": grade},
        "cashflow": {
            "surplus": {"monthly": surplus},
            "savings_rate": {"basic_pct": savings_rate},
        },
        "debt": {
            "summary": {
                "total_balance": debt_total,
                "high_interest_debt_count": high_interest_count,
            },
        },
        "goals": {
            "summary": {
                "on_track": on_track,
                "at_risk": at_risk,
                "unreachable": unreachable,
            },
        },
        "investments": {
            "pension_analysis": {"income_replacement_ratio_pct": pension_repl},
        },
        "mortgage": {"readiness": mortgage_readiness},
    }


def _make_profile(emergency_fund: float = 6000.0, monthly_expenses: float = 2000.0) -> dict:
    return {
        "_net_worth": 25000,
        "savings": {"emergency_fund": emergency_fund},
        "expenses": {"_total_monthly": monthly_expenses},
    }


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "history.db"


# ---------------------------------------------------------------------------
# Schema and connection
# ---------------------------------------------------------------------------

class TestSchema:
    def test_schema_created_on_first_use(self, db_path):
        record_run(_make_report(), db_path, profile=_make_profile())
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = {row[0] for row in cur.fetchall()}
        assert "runs" in tables
        assert "meta" in tables

    def test_schema_version_stamped(self, db_path):
        record_run(_make_report(), db_path)
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT value FROM meta WHERE key='schema_version'")
            row = cur.fetchone()
        assert row is not None
        assert int(row[0]) == SCHEMA_VERSION

    def test_creates_parent_directory(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "history.db"
        record_run(_make_report(), nested)
        assert nested.exists()

    def test_corrupt_db_raises_history_error(self, db_path):
        db_path.write_text("not a sqlite database")
        with pytest.raises(HistoryError):
            list_runs(db_path)


# ---------------------------------------------------------------------------
# record_run
# ---------------------------------------------------------------------------

class TestRecordRun:
    def test_returns_row_id(self, db_path):
        run_id = record_run(_make_report(), db_path)
        assert isinstance(run_id, int)
        assert run_id == 1

    def test_two_records_get_distinct_ids(self, db_path):
        a = record_run(_make_report(score=70), db_path)
        b = record_run(_make_report(score=75), db_path)
        assert b == a + 1

    def test_records_without_profile(self, db_path):
        run_id = record_run(_make_report(), db_path)
        runs = list_runs(db_path)
        row = next(r for r in runs if r["id"] == run_id)
        assert row["overall_score"] == 70.0
        assert row["net_worth"] is None
        assert row["emergency_fund_months"] is None

    def test_records_with_profile_extracts_extras(self, db_path):
        record_run(
            _make_report(),
            db_path,
            profile=_make_profile(emergency_fund=6000, monthly_expenses=2000),
        )
        row = list_runs(db_path)[0]
        assert row["net_worth"] == 25000
        assert row["emergency_fund_months"] == 3.0

    def test_records_profile_path(self, db_path):
        record_run(_make_report(), db_path, profile_path="/some/path/profile.yaml")
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT profile_path FROM runs LIMIT 1")
            row = cur.fetchone()
        assert row[0] == "/some/path/profile.yaml"

    def test_full_report_json_round_trips(self, db_path):
        import json
        record_run(_make_report(score=88.5), db_path)
        with sqlite3.connect(db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT full_report_json FROM runs LIMIT 1")
            row = cur.fetchone()
        decoded = json.loads(row[0])
        assert decoded["scoring"]["overall_score"] == 88.5

    def test_idempotent_recording_creates_two_rows(self, db_path):
        report = _make_report()
        record_run(report, db_path)
        record_run(report, db_path)
        runs = list_runs(db_path)
        assert len(runs) == 2

    def test_zero_monthly_expenses_skips_ef_months(self, db_path):
        record_run(
            _make_report(),
            db_path,
            profile=_make_profile(emergency_fund=6000, monthly_expenses=0),
        )
        row = list_runs(db_path)[0]
        assert row["emergency_fund_months"] is None


# ---------------------------------------------------------------------------
# list_runs
# ---------------------------------------------------------------------------

class TestListRuns:
    def test_empty_db_returns_empty_list(self, db_path):
        # Touch the DB so the schema exists, then read.
        record_run(_make_report(), db_path)
        with sqlite3.connect(db_path) as conn:
            conn.execute("DELETE FROM runs")
            conn.commit()
        assert list_runs(db_path) == []

    def test_newest_first_ordering(self, db_path):
        record_run(_make_report(score=60), db_path)
        record_run(_make_report(score=70), db_path)
        record_run(_make_report(score=80), db_path)
        runs = list_runs(db_path)
        assert [r["overall_score"] for r in runs] == [80, 70, 60]

    def test_limit_caps_results(self, db_path):
        for s in range(5):
            record_run(_make_report(score=float(s)), db_path)
        assert len(list_runs(db_path, limit=2)) == 2

    def test_filter_by_profile_name(self, db_path):
        record_run(_make_report(profile_name="Alice"), db_path)
        record_run(_make_report(profile_name="Bob"), db_path)
        record_run(_make_report(profile_name="Alice"), db_path)
        alice_runs = list_runs(db_path, profile_name="Alice")
        assert len(alice_runs) == 2
        assert all(r["profile_name"] == "Alice" for r in alice_runs)


# ---------------------------------------------------------------------------
# diff_runs
# ---------------------------------------------------------------------------

class TestDiffRuns:
    def test_numeric_delta_and_pct(self, db_path):
        a = record_run(_make_report(score=60, surplus=500), db_path)
        b = record_run(_make_report(score=75, surplus=750), db_path)
        diff = diff_runs(db_path, a, b)
        assert diff["numeric"]["overall_score"]["delta"] == 15
        assert diff["numeric"]["overall_score"]["delta_pct"] == 25.0
        assert diff["numeric"]["surplus_monthly"]["delta"] == 250

    def test_categorical_changed_flag(self, db_path):
        a = record_run(_make_report(grade="C"), db_path)
        b = record_run(_make_report(grade="B"), db_path)
        diff = diff_runs(db_path, a, b)
        assert diff["categorical"]["grade"]["changed"] is True
        assert diff["categorical"]["grade"]["old"] == "C"
        assert diff["categorical"]["grade"]["new"] == "B"

    def test_unchanged_categorical(self, db_path):
        a = record_run(_make_report(mortgage_readiness="Ready"), db_path)
        b = record_run(_make_report(mortgage_readiness="Ready"), db_path)
        diff = diff_runs(db_path, a, b)
        assert diff["categorical"]["mortgage_readiness"]["changed"] is False

    def test_summary_direction_improved(self, db_path):
        a = record_run(_make_report(score=60), db_path)
        b = record_run(_make_report(score=75), db_path)
        diff = diff_runs(db_path, a, b)
        assert diff["summary"]["direction"] == "improved"
        assert diff["summary"]["score_delta"] == 15

    def test_summary_direction_declined(self, db_path):
        a = record_run(_make_report(score=80), db_path)
        b = record_run(_make_report(score=70), db_path)
        diff = diff_runs(db_path, a, b)
        assert diff["summary"]["direction"] == "declined"

    def test_summary_direction_unchanged(self, db_path):
        a = record_run(_make_report(score=70), db_path)
        b = record_run(_make_report(score=70), db_path)
        diff = diff_runs(db_path, a, b)
        assert diff["summary"]["direction"] == "unchanged"

    def test_missing_run_raises(self, db_path):
        a = record_run(_make_report(), db_path)
        with pytest.raises(HistoryError, match="not found"):
            diff_runs(db_path, a, 9999)

    def test_none_old_value_handled(self, db_path):
        a = record_run(_make_report(), db_path)  # no profile -> net_worth is None
        b = record_run(_make_report(), db_path, profile=_make_profile())
        diff = diff_runs(db_path, a, b)
        nw = diff["numeric"]["net_worth"]
        assert nw["old"] is None
        assert nw["delta"] is None

    def test_zero_old_value_no_pct_division(self, db_path):
        a = record_run(_make_report(debt_total=0), db_path)
        b = record_run(_make_report(debt_total=1000), db_path)
        diff = diff_runs(db_path, a, b)
        assert diff["numeric"]["debt_total"]["delta"] == 1000
        assert diff["numeric"]["debt_total"]["delta_pct"] is None


# ---------------------------------------------------------------------------
# latest_two_runs
# ---------------------------------------------------------------------------

class TestLatestTwoRuns:
    def test_returns_none_when_zero_runs(self, db_path):
        record_run(_make_report(), db_path)
        with sqlite3.connect(db_path) as conn:
            conn.execute("DELETE FROM runs")
            conn.commit()
        assert latest_two_runs(db_path) is None

    def test_returns_none_when_only_one_run(self, db_path):
        record_run(_make_report(), db_path)
        assert latest_two_runs(db_path) is None

    def test_returns_older_then_newer(self, db_path):
        a = record_run(_make_report(score=60), db_path)
        b = record_run(_make_report(score=70), db_path)
        c = record_run(_make_report(score=80), db_path)
        pair = latest_two_runs(db_path)
        assert pair == (b, c)
        assert a not in pair

    def test_filters_by_profile(self, db_path):
        record_run(_make_report(profile_name="Alice"), db_path)
        record_run(_make_report(profile_name="Bob"), db_path)
        bob2 = record_run(_make_report(profile_name="Bob"), db_path)
        record_run(_make_report(profile_name="Alice"), db_path)
        pair = latest_two_runs(db_path, profile_name="Bob")
        assert pair is not None
        assert pair[1] == bob2
