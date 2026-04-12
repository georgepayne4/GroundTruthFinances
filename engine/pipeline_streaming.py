"""engine/pipeline_streaming.py — Streaming analysis pipeline (v6.0-03).

A generator-based version of the pipeline that yields progress updates
after each stage completes. Used by the WebSocket endpoint to stream
real-time feedback to the client.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Generator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine.cashflow import analyse_cashflow
from engine.debt import analyse_debt
from engine.estate import analyse_estate
from engine.goals import analyse_goals
from engine.insights import generate_insights
from engine.insurance import assess_insurance
from engine.investments import analyse_investments
from engine.life_events import simulate_life_events
from engine.loader import load_assumptions, normalise_profile
from engine.mortgage import analyse_mortgage
from engine.report import assemble_report
from engine.risk_profiling import assess_risk_profiles
from engine.scenarios import run_scenarios
from engine.scoring import calculate_scores
from engine.sensitivity import run_sensitivity
from engine.validator import validate_profile

logger = logging.getLogger(__name__)


@dataclass
class StageUpdate:
    """Progress update from a pipeline stage."""
    stage: str
    status: str  # "running", "complete", "error"
    duration_ms: float = 0.0
    result: dict[str, Any] | None = None
    error: str | None = None


def run_pipeline_streaming(
    raw_profile: dict[str, Any],
    assumptions_override: dict[str, Any] | None = None,
    assumptions_path: str | Path | None = None,
) -> Generator[StageUpdate, None, None]:
    """Run the full pipeline, yielding progress after each stage.

    The final yield has stage="report" with the complete report in result.
    """
    # --- Normalise profile ---
    yield StageUpdate(stage="normalise", status="running")
    t0 = time.perf_counter()
    profile = normalise_profile(raw_profile)
    yield StageUpdate(stage="normalise", status="complete", duration_ms=_elapsed_ms(t0))

    # --- Load assumptions ---
    yield StageUpdate(stage="assumptions", status="running")
    t0 = time.perf_counter()
    if assumptions_override:
        from engine.schemas import validate_assumptions
        validate_assumptions(assumptions_override)
        assumptions = assumptions_override
    else:
        path = assumptions_path or (Path(__file__).resolve().parent.parent / "config" / "assumptions.yaml")
        assumptions = load_assumptions(path)
    yield StageUpdate(stage="assumptions", status="complete", duration_ms=_elapsed_ms(t0))

    # --- Validation ---
    yield StageUpdate(stage="validation", status="running")
    t0 = time.perf_counter()
    flags = validate_profile(profile, assumptions)
    flag_dicts = [f.to_dict() for f in flags]
    yield StageUpdate(stage="validation", status="complete", duration_ms=_elapsed_ms(t0))

    # --- Core analysis stages ---
    results: dict[str, Any] = {}

    def _run_stage(name: str, func, *args):
        yield StageUpdate(stage=name, status="running")
        t0 = time.perf_counter()
        try:
            result = func(*args)
            results[name] = result
            yield StageUpdate(stage=name, status="complete", duration_ms=_elapsed_ms(t0))
        except Exception as exc:
            logger.error("Stage %s failed: %s", name, exc)
            yield StageUpdate(stage=name, status="error", duration_ms=_elapsed_ms(t0), error=str(exc))
            raise

    # Cashflow
    yield from _run_stage("cashflow", analyse_cashflow, profile, assumptions)

    # Debt
    yield from _run_stage("debt", analyse_debt, profile, assumptions)

    # Goals
    yield from _run_stage("goals", analyse_goals, profile, assumptions, results["cashflow"], results["debt"])

    # Risk profiling
    yield from _run_stage("risk_profiling", assess_risk_profiles, profile, assumptions, results["cashflow"], results["goals"])

    # Investments
    yield from _run_stage("investments", analyse_investments, profile, assumptions, results["cashflow"], results["goals"], results["risk_profiling"])

    # Mortgage
    yield from _run_stage("mortgage", analyse_mortgage, profile, assumptions, results["cashflow"], results["debt"])

    # Insurance
    yield from _run_stage(
        "insurance", assess_insurance,
        profile, assumptions, results["cashflow"], results["mortgage"], results["investments"],
    )

    # Life events
    yield from _run_stage("life_events", simulate_life_events, profile, assumptions, results["cashflow"])

    # Scoring
    yield from _run_stage(
        "scoring", calculate_scores,
        profile, assumptions, results["cashflow"], results["debt"],
        results["goals"], results["investments"], results["mortgage"],
    )

    # Scenarios
    yield from _run_stage(
        "scenarios", run_scenarios,
        profile, assumptions, results["cashflow"], results["debt"],
        results["mortgage"], results["investments"],
    )

    # Estate
    yield from _run_stage(
        "estate", analyse_estate,
        profile, assumptions, results["investments"], results["mortgage"], results["cashflow"],
    )

    # Sensitivity
    yield from _run_stage(
        "sensitivity", run_sensitivity,
        profile, assumptions, results["cashflow"], results["debt"],
        results["investments"], results["mortgage"],
    )

    # Insights
    yield from _run_stage(
        "insights", generate_insights,
        profile, assumptions, results["cashflow"], results["debt"],
        results["goals"], results["investments"], results["mortgage"],
        results["scoring"], results["life_events"],
    )

    # --- Assemble report ---
    yield StageUpdate(stage="report", status="running")
    t0 = time.perf_counter()
    report = assemble_report(
        profile=profile,
        validation_flags=flag_dicts,
        cashflow=results["cashflow"],
        debt_analysis=results["debt"],
        goal_analysis=results["goals"],
        investment_analysis=results["investments"],
        mortgage_analysis=results["mortgage"],
        life_events=results["life_events"],
        scoring=results["scoring"],
        insights=results["insights"],
        insurance=results["insurance"],
        scenarios=results["scenarios"],
        estate=results["estate"],
        sensitivity=results["sensitivity"],
        risk_profiling=results.get("risk_profiling"),
    )
    yield StageUpdate(
        stage="report",
        status="complete",
        duration_ms=_elapsed_ms(t0),
        result=report,
    )


def _elapsed_ms(start: float) -> float:
    return round((time.perf_counter() - start) * 1000, 1)


def _build_stage_list() -> list[str]:
    """Return the ordered list of pipeline stage names."""
    return [
        "normalise", "assumptions", "validation",
        "cashflow", "debt", "goals", "risk_profiling", "investments", "mortgage",
        "insurance", "life_events", "scoring", "scenarios",
        "estate", "sensitivity", "insights", "report",
    ]


def get_stage_names() -> list[str]:
    """Public accessor for stage names (used by WebSocket for total count)."""
    return _build_stage_list()
