"""Tests for the assumption auto-update pipeline (v5.3-03)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from engine.assumption_updater import (
    FetchError,
    SanityCheckError,
    _get_nested,
    _set_nested,
    apply_updates,
    check_sanity,
    fetch_boe_base_rate,
    fetch_ons_cpi,
    run_update,
)

# ---------------------------------------------------------------------------
# Helper: minimal assumptions dict
# ---------------------------------------------------------------------------

def _base_assumptions() -> dict:
    return {
        "tax_year": "2025/26",
        "tax": {
            "personal_allowance": 12570,
            "basic_rate": 0.20,
            "basic_threshold": 50270,
            "higher_rate": 0.40,
            "higher_threshold": 125140,
            "additional_rate": 0.45,
            "national_insurance_rate": 0.08,
            "employer_national_insurance_rate": 0.15,
        },
        "inflation": {"general": 0.03},
        "mortgage_products": {
            "tracker": {"rate": 0.042, "margin_above_base": 0.01},
        },
        "pension_annual_allowance": {"standard": 60000},
        "isa": {"annual_limit": 20000},
        "lisa": {"annual_limit": 4000},
        "capital_gains_tax": {"annual_exemption": 3000},
        "inheritance_tax": {"nil_rate_band": 325000},
        "state_pension": {"full_annual_amount": 11502},
    }


# ---------------------------------------------------------------------------
# Nested dict helpers
# ---------------------------------------------------------------------------

class TestNestedHelpers:
    def test_get_nested(self):
        d = {"a": {"b": {"c": 42}}}
        assert _get_nested(d, "a.b.c") == 42

    def test_get_nested_missing(self):
        d = {"a": {"b": 1}}
        assert _get_nested(d, "a.x.y") is None

    def test_get_nested_top_level(self):
        d = {"key": "value"}
        assert _get_nested(d, "key") == "value"

    def test_set_nested(self):
        d = {"a": {"b": 1}}
        _set_nested(d, "a.b", 2)
        assert d["a"]["b"] == 2

    def test_set_nested_creates_intermediate(self):
        d = {}
        _set_nested(d, "a.b.c", 99)
        assert d["a"]["b"]["c"] == 99


# ---------------------------------------------------------------------------
# Sanity checks
# ---------------------------------------------------------------------------

class TestSanityChecks:
    def test_passes_valid_value(self):
        check_sanity("tax.personal_allowance", 12570)

    def test_fails_out_of_range(self):
        with pytest.raises(SanityCheckError):
            check_sanity("tax.personal_allowance", 999999)

    def test_fails_negative(self):
        with pytest.raises(SanityCheckError):
            check_sanity("tax.personal_allowance", -1)

    def test_unknown_key_passes(self):
        # Keys without defined bounds should not raise
        check_sanity("some.unknown.key", 9999)

    def test_inflation_bounds(self):
        check_sanity("inflation.general", 0.02)
        with pytest.raises(SanityCheckError):
            check_sanity("inflation.general", 0.50)


# ---------------------------------------------------------------------------
# Apply updates
# ---------------------------------------------------------------------------

class TestApplyUpdates:
    def test_applies_valid_change(self):
        assumptions = _base_assumptions()
        changes = apply_updates(assumptions, {"inflation.general": 0.025}, source="test")
        assert len(changes) == 1
        assert changes[0].old_value == 0.03
        assert changes[0].new_value == 0.025
        assert assumptions["inflation"]["general"] == 0.025

    def test_skips_unchanged_value(self):
        assumptions = _base_assumptions()
        changes = apply_updates(assumptions, {"inflation.general": 0.03}, source="test")
        assert len(changes) == 0

    def test_skips_insane_value(self):
        assumptions = _base_assumptions()
        changes = apply_updates(assumptions, {"tax.personal_allowance": -500}, source="test")
        assert len(changes) == 0
        assert assumptions["tax"]["personal_allowance"] == 12570  # unchanged

    def test_multiple_updates(self):
        assumptions = _base_assumptions()
        changes = apply_updates(assumptions, {
            "inflation.general": 0.02,
            "tax.personal_allowance": 13000,
        }, source="test")
        assert len(changes) == 2

    def test_change_records_source(self):
        assumptions = _base_assumptions()
        changes = apply_updates(assumptions, {"inflation.general": 0.04}, source="ONS CPI")
        assert changes[0].source == "ONS CPI"


# ---------------------------------------------------------------------------
# BoE fetcher (mocked HTTP)
# ---------------------------------------------------------------------------

class TestBoeFetcher:
    @patch("engine.assumption_updater.httpx.get")
    def test_parses_csv_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = "Date, IUDBEDR\n01 Jan 2025, 4.50\n01 Feb 2025, 4.50\n01 Mar 2025, 4.25\n"
        mock_get.return_value = mock_resp

        result = fetch_boe_base_rate()
        assert result["boe_base_rate"] == 0.0425
        assert "Bank of England" in result["source"]

    @patch("engine.assumption_updater.httpx.get")
    def test_handles_decimal_rate(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = "Date, IUDBEDR\n01 Jan 2025, 0.0425\n"
        mock_get.return_value = mock_resp

        result = fetch_boe_base_rate()
        assert result["boe_base_rate"] == 0.0425

    @patch("engine.assumption_updater.httpx.get")
    def test_raises_on_http_error(self, mock_get):
        import httpx
        mock_get.side_effect = httpx.HTTPError("Connection failed")

        with pytest.raises(FetchError, match="BoE"):
            fetch_boe_base_rate()

    @patch("engine.assumption_updater.httpx.get")
    def test_raises_on_empty_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.text = "Header\n"
        mock_get.return_value = mock_resp

        with pytest.raises(FetchError, match="no data"):
            fetch_boe_base_rate()


# ---------------------------------------------------------------------------
# ONS CPI fetcher (mocked HTTP)
# ---------------------------------------------------------------------------

class TestOnsCpiFetcher:
    @patch("engine.assumption_updater.httpx.get")
    def test_parses_json_response(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "months": [
                {"year": "2025", "month": "January", "value": "3.0"},
                {"year": "2025", "month": "February", "value": "2.8"},
            ]
        }
        mock_get.return_value = mock_resp

        result = fetch_ons_cpi()
        assert abs(result["inflation_general"] - 0.028) < 1e-9
        assert "ONS" in result["source"]

    @patch("engine.assumption_updater.httpx.get")
    def test_raises_on_empty_months(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {"months": []}
        mock_get.return_value = mock_resp

        with pytest.raises(FetchError, match="no monthly"):
            fetch_ons_cpi()

    @patch("engine.assumption_updater.httpx.get")
    def test_raises_on_http_error(self, mock_get):
        import httpx
        mock_get.side_effect = httpx.HTTPError("Timeout")

        with pytest.raises(FetchError, match="ONS"):
            fetch_ons_cpi()


# ---------------------------------------------------------------------------
# Full update pipeline (mocked fetchers)
# ---------------------------------------------------------------------------

class TestRunUpdate:
    @patch("engine.assumption_updater.fetch_ons_cpi")
    @patch("engine.assumption_updater.fetch_boe_base_rate")
    def test_applies_both_sources(self, mock_boe, mock_ons):
        mock_boe.return_value = {"boe_base_rate": 0.0425, "source": "BoE"}
        mock_ons.return_value = {"inflation_general": 0.028, "source": "ONS"}

        assumptions = _base_assumptions()
        result = run_update(assumptions)

        assert len(result.errors) == 0
        assert len(result.changes) >= 1
        # Tracker rate should be updated: 0.0425 + 0.01 margin = 0.0525
        assert assumptions["mortgage_products"]["tracker"]["rate"] == 0.0525

    @patch("engine.assumption_updater.fetch_ons_cpi")
    @patch("engine.assumption_updater.fetch_boe_base_rate")
    def test_partial_failure_still_applies_other(self, mock_boe, mock_ons):
        mock_boe.side_effect = FetchError("BoE down")
        mock_ons.return_value = {"inflation_general": 0.025, "source": "ONS"}

        assumptions = _base_assumptions()
        result = run_update(assumptions)

        assert len(result.errors) == 1
        assert "BoE" in result.errors[0]
        # CPI should still have been applied
        assert assumptions["inflation"]["general"] == 0.025

    @patch("engine.assumption_updater.fetch_ons_cpi")
    @patch("engine.assumption_updater.fetch_boe_base_rate")
    def test_both_fail_returns_no_changes(self, mock_boe, mock_ons):
        mock_boe.side_effect = FetchError("BoE down")
        mock_ons.side_effect = FetchError("ONS down")

        assumptions = _base_assumptions()
        result = run_update(assumptions)

        assert len(result.errors) == 2
        assert len(result.changes) == 0

    @patch("engine.assumption_updater.fetch_ons_cpi")
    @patch("engine.assumption_updater.fetch_boe_base_rate")
    def test_sets_last_auto_update(self, mock_boe, mock_ons):
        mock_boe.return_value = {"boe_base_rate": 0.05, "source": "BoE"}
        mock_ons.return_value = {"inflation_general": 0.03, "source": "ONS"}

        assumptions = _base_assumptions()
        result = run_update(assumptions)

        if result.changes:
            assert "last_auto_update" in assumptions

    @patch("engine.assumption_updater.fetch_ons_cpi")
    @patch("engine.assumption_updater.fetch_boe_base_rate")
    def test_no_change_if_values_same(self, mock_boe, mock_ons):
        mock_boe.return_value = {"boe_base_rate": 0.032, "source": "BoE"}
        mock_ons.return_value = {"inflation_general": 0.03, "source": "ONS"}

        assumptions = _base_assumptions()
        # Pre-set tracker to what it would be: 0.032 + 0.01 = 0.042
        result = run_update(assumptions)

        # inflation.general=0.03 is same, tracker rate=0.042 is same
        assert len(result.changes) == 0
