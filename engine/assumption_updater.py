"""
assumption_updater.py — Assumption Auto-Update Pipeline (v5.3-03)

Fetches current tax year parameters from public data sources, validates
them against expected ranges, and produces a structured update dict that
can be merged into assumptions.yaml or stored in the database.

Data sources:
  - Bank of England Statistical Interactive Database (base rate)
  - ONS CPI inflation series
  - HMRC rates/thresholds (scraped or manual — no public JSON API)

Design:
  - Each fetcher returns a dict of changed keys or raises FetchError.
  - Sanity bounds prevent obviously wrong values from propagating.
  - Caller decides whether to apply updates (write YAML / store in DB).
  - Fetch failures are non-fatal: return partial results + error list.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date
from typing import Any

import httpx
import yaml

from engine.exceptions import GroundTruthError

logger = logging.getLogger(__name__)


class FetchError(GroundTruthError):
    """Raised when a data source cannot be reached or returns bad data."""


class SanityCheckError(GroundTruthError):
    """Raised when a fetched value is outside its expected range."""


# ---------------------------------------------------------------------------
# Sanity bounds — prevents obviously corrupted data from being applied
# ---------------------------------------------------------------------------

@dataclass
class Bound:
    """Inclusive min/max range for a numeric assumption value."""
    key: str
    min_val: float
    max_val: float
    description: str = ""


_SANITY_BOUNDS: list[Bound] = [
    Bound("tax.personal_allowance", 0, 30000, "UK personal allowance"),
    Bound("tax.basic_rate", 0.05, 0.40, "Basic income tax rate"),
    Bound("tax.basic_threshold", 20000, 100000, "Basic rate upper threshold"),
    Bound("tax.higher_rate", 0.20, 0.60, "Higher income tax rate"),
    Bound("tax.higher_threshold", 80000, 200000, "Higher rate upper threshold"),
    Bound("tax.additional_rate", 0.30, 0.65, "Additional income tax rate"),
    Bound("tax.national_insurance_rate", 0.01, 0.20, "Employee NI rate"),
    Bound("tax.employer_national_insurance_rate", 0.05, 0.25, "Employer NI rate"),
    Bound("inflation.general", 0.00, 0.15, "General CPI inflation"),
    Bound("pension_annual_allowance.standard", 10000, 100000, "Pension annual allowance"),
    Bound("isa.annual_limit", 5000, 50000, "ISA annual limit"),
    Bound("lisa.annual_limit", 1000, 10000, "LISA annual limit"),
    Bound("capital_gains_tax.annual_exemption", 0, 20000, "CGT annual exemption"),
    Bound("inheritance_tax.nil_rate_band", 100000, 500000, "IHT nil rate band"),
    Bound("state_pension.full_annual_amount", 5000, 25000, "Full state pension"),
]


# ---------------------------------------------------------------------------
# Update result
# ---------------------------------------------------------------------------

@dataclass
class AssumptionChange:
    """A single changed value."""
    key_path: str
    old_value: Any
    new_value: Any
    source: str


@dataclass
class UpdateResult:
    """Outcome of an update attempt."""
    changes: list[AssumptionChange] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    source_date: str = ""
    tax_year: str = ""


# ---------------------------------------------------------------------------
# Fetchers
# ---------------------------------------------------------------------------

def fetch_boe_base_rate() -> dict[str, Any]:
    """Fetch the current Bank of England base rate.

    Uses the BoE Statistical Interactive Database CSV endpoint.
    """
    url = "https://www.bankofengland.co.uk/boeapps/database/fromshowcolumns.asp"
    params = {
        "Travel": "NIxAZxSUx",
        "FromSeries": "1",
        "ToSeries": "50",
        "DAession": "999",
        "DataPR": "C",
        "SeriesCodes": "IUDBEDR",
        "UsingCodes": "Y",
        "CSVF": "TN",
        "Datefrom": "01/Jan/2024",
        "Dateto": "31/Dec/2026",
    }

    try:
        resp = httpx.get(url, params=params, timeout=15, follow_redirects=True)
        resp.raise_for_status()
    except httpx.HTTPError as e:
        raise FetchError(f"BoE base rate fetch failed: {e}") from e

    # Parse CSV: header line then "DD MMM YYYY, rate" rows
    lines = resp.text.strip().splitlines()
    if len(lines) < 2:
        raise FetchError("BoE response has no data rows")

    last_line = lines[-1].strip()
    parts = last_line.split(",")
    if len(parts) < 2:
        raise FetchError(f"Cannot parse BoE row: {last_line}")

    try:
        rate = float(parts[-1].strip())
    except ValueError as e:
        raise FetchError(f"Cannot parse BoE rate value: {parts[-1]}") from e

    # BoE returns rate as percentage (e.g. 4.50 for 4.5%)
    if rate > 1:
        rate = rate / 100

    logger.info("BoE base rate fetched: %.4f", rate)
    return {"boe_base_rate": rate, "source": "Bank of England IUDBEDR"}


def fetch_ons_cpi() -> dict[str, Any]:
    """Fetch the latest ONS CPI annual rate.

    Uses the ONS time series API (JSON).
    """
    # D7G7 = CPI Annual Rate (all items)
    url = "https://www.ons.gov.uk/economy/inflationandpriceindices/timeseries/d7g7/mm23/data"

    try:
        resp = httpx.get(url, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as e:
        raise FetchError(f"ONS CPI fetch failed: {e}") from e
    except (ValueError, KeyError) as e:
        raise FetchError(f"ONS CPI parse error: {e}") from e

    months = data.get("months", [])
    if not months:
        raise FetchError("ONS CPI response has no monthly data")

    latest = months[-1]
    try:
        cpi_pct = float(latest["value"])
    except (ValueError, KeyError) as e:
        raise FetchError(f"Cannot parse ONS CPI value: {latest}") from e

    cpi_decimal = cpi_pct / 100
    logger.info("ONS CPI annual rate fetched: %.4f (%s %s)", cpi_decimal, latest.get("month", ""), latest.get("year", ""))
    return {
        "inflation_general": cpi_decimal,
        "source": f"ONS D7G7 {latest.get('month', '')} {latest.get('year', '')}",
    }


# ---------------------------------------------------------------------------
# Core update logic
# ---------------------------------------------------------------------------

def _get_nested(d: dict, key_path: str) -> Any:
    """Retrieve a nested dict value by dot-separated key path."""
    keys = key_path.split(".")
    current = d
    for k in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(k)
    return current


def _set_nested(d: dict, key_path: str, value: Any) -> None:
    """Set a nested dict value by dot-separated key path."""
    keys = key_path.split(".")
    current = d
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value


def check_sanity(key_path: str, value: float) -> None:
    """Raise SanityCheckError if value is outside expected bounds."""
    for bound in _SANITY_BOUNDS:
        if bound.key == key_path:
            if not (bound.min_val <= value <= bound.max_val):
                raise SanityCheckError(
                    f"{key_path}={value} outside bounds [{bound.min_val}, {bound.max_val}] "
                    f"({bound.description})"
                )
            return


def apply_updates(
    assumptions: dict[str, Any],
    updates: dict[str, Any],
    source: str = "auto-update",
) -> list[AssumptionChange]:
    """Apply a dict of {key_path: new_value} to assumptions. Returns changes made.

    Skips values that fail sanity checks (logged as warnings).
    """
    changes: list[AssumptionChange] = []

    for key_path, new_value in updates.items():
        old_value = _get_nested(assumptions, key_path)

        if old_value == new_value:
            continue

        try:
            if isinstance(new_value, (int, float)):
                check_sanity(key_path, float(new_value))
        except SanityCheckError as e:
            logger.warning("Sanity check failed, skipping: %s", e)
            continue

        _set_nested(assumptions, key_path, new_value)
        changes.append(AssumptionChange(
            key_path=key_path,
            old_value=old_value,
            new_value=new_value,
            source=source,
        ))
        logger.info("Updated %s: %s -> %s (source: %s)", key_path, old_value, new_value, source)

    return changes


def run_update(assumptions: dict[str, Any]) -> UpdateResult:
    """Run all fetchers and apply updates to the assumptions dict.

    Non-fatal: individual fetch failures are recorded in result.errors
    but don't prevent other fetchers from running.
    """
    result = UpdateResult(source_date=date.today().isoformat())
    pending_updates: dict[str, Any] = {}

    # --- BoE base rate ---
    try:
        boe = fetch_boe_base_rate()
        base_rate = boe["boe_base_rate"]
        # Update tracker mortgage rate (base + margin)
        margin = _get_nested(assumptions, "mortgage_products.tracker.margin_above_base") or 0.01
        pending_updates["mortgage_products.tracker.rate"] = round(base_rate + margin, 4)
    except FetchError as e:
        result.errors.append(str(e))
        logger.warning("BoE fetch failed: %s", e)

    # --- ONS CPI ---
    try:
        ons = fetch_ons_cpi()
        pending_updates["inflation.general"] = round(ons["inflation_general"], 4)
    except FetchError as e:
        result.errors.append(str(e))
        logger.warning("ONS CPI fetch failed: %s", e)

    # --- Apply all pending updates ---
    if pending_updates:
        result.changes = apply_updates(assumptions, pending_updates, source="auto-update")

    # --- Update metadata ---
    if result.changes:
        assumptions["last_auto_update"] = result.source_date

    return result


def save_assumptions_yaml(assumptions: dict[str, Any], path: str | None = None) -> str:
    """Write the assumptions dict back to YAML. Returns the path written to."""
    from pathlib import Path

    if path is None:
        path = str(Path(__file__).resolve().parent.parent / "config" / "assumptions.yaml")

    with open(path, "w", encoding="utf-8") as f:
        f.write("# ==============================================================================\n")
        f.write("# Financial Planning Assumptions (auto-updated)\n")
        f.write(f"# Last auto-update: {date.today().isoformat()}\n")
        f.write("# ==============================================================================\n\n")
        yaml.dump(assumptions, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

    logger.info("Assumptions written to %s", path)
    return path
