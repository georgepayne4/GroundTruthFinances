"""
report.py — Report Assembly and Output

Collects results from all analysis modules, assembles them into a
consistent JSON schema, and writes the final report to disk.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def assemble_report(
    profile: dict,
    validation_flags: list[dict],
    cashflow: dict,
    debt_analysis: dict,
    goal_analysis: dict,
    investment_analysis: dict,
    mortgage_analysis: dict,
    life_events: dict,
    scoring: dict,
    insights: dict,
) -> dict[str, Any]:
    """
    Assemble all analysis results into the final report structure.
    """
    personal = profile.get("personal", {})

    report = {
        "meta": {
            "report_type": "GroundTruth Financial Health Report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "engine_version": "1.0.0",
            "profile_name": personal.get("name", "Unknown"),
            "profile_age": personal.get("age"),
        },
        "validation": {
            "flags": validation_flags,
            "error_count": sum(1 for f in validation_flags if f.get("severity") == "error"),
            "warning_count": sum(1 for f in validation_flags if f.get("severity") == "warning"),
            "info_count": sum(1 for f in validation_flags if f.get("severity") == "info"),
        },
        "scoring": scoring,
        "cashflow": cashflow,
        "debt": debt_analysis,
        "goals": goal_analysis,
        "investments": investment_analysis,
        "mortgage": mortgage_analysis,
        "life_events": life_events,
        "advisor_insights": insights,
    }

    return report


def save_report(report: dict, output_path: str | Path) -> Path:
    """Write the report to a JSON file and return the path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=2, ensure_ascii=False, default=str)

    return output_path
