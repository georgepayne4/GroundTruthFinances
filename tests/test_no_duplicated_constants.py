"""
test_no_duplicated_constants.py — CI guard against config drift

Enforces CLAUDE.md principle #9: "Any value in `assumptions.yaml` must never be
hardcoded in engine code." This prevents the MODEL_PORTFOLIOS / magic-number
drift identified in the Version 11 System Audit (REVIEW.md §2 C2, C3).

Mechanism: for each critical value in assumptions.yaml, scan engine/*.py for a
matching numeric literal. Any match is a duplication unless explicitly
allowlisted (e.g., where the value co-incidentally equals a literal that has
independent semantic meaning — the allowlist entry documents why).

When a new constant is added to assumptions.yaml, add it to CRITICAL_VALUES.
When a legitimate code-side literal coincides with an assumption, add it to
ALLOWLIST with a justification comment.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = PROJECT_ROOT / "engine"

# Values from assumptions.yaml that must NOT appear as literals in engine/*.py.
# Format: (value, source_key_path). Integer and float are distinct.
# Keep this list focused on values the audit flagged as drift-prone.
CRITICAL_VALUES: list[tuple[int | float, str]] = [
    (0.0015, "fee_comparison.low_cost_total_pct"),
    (0.015, "fee_comparison.high_cost_total_pct"),
    (0.02, "investment_analysis_defaults.dividend_yield"),
    (5.0, "investment_analysis_defaults.rebalancing_drift_threshold_pct"),
    (20000, "isa.annual_limit"),
    (30000, "retirement.default_income_target"),
]

# Allowlist: (file_stem, value, reason). A literal here is permitted in that
# specific engine module. Keep the reason short and concrete. Value type (int vs
# float) must match CRITICAL_VALUES — e.g. `5.0` != `5`.
ALLOWLIST: list[tuple[str, int | float, str]] = [
    # 0.02 appears legitimately in tax/NI/mortgage/scoring (rate adjustments,
    # calibration slopes). Only drift-risky in investments.py where it historically
    # meant dividend_yield.
    ("cashflow", 0.02, "tax/NI percentage — not dividend yield"),
    ("mortgage", 0.02, "rate offset basis — not dividend yield"),
    ("tax", 0.02, "NI rate calculation — not dividend yield"),
    ("scoring", 0.02, "score calibration slope — not dividend yield"),
    ("life_events", 0.02, "stress-test rate offset in house-purchase projection — not dividend yield"),
    # 5.0 (float) — scoring/sensitivity/savings-rate thresholds use the same
    # number by coincidence.
    ("scoring", 5.0, "savings rate breakpoint — not drift threshold"),
    ("sensitivity", 5.0, "sensitivity delta — not drift threshold"),
    ("insights", 5.0, "savings-rate headline threshold — not drift threshold"),
    # 20000 / 30000 (int) — assumption_updater defines sanity BOUNDS (min/max
    # ranges) for these keys; coincidence with the actual value is expected and
    # these bounds are NOT the source of truth for the value itself.
    ("assumption_updater", 20000, "sanity bound on ISA/tax thresholds — not the value"),
    ("assumption_updater", 30000, "sanity bound on personal allowance — not the value"),
]


def _flatten_yaml_numbers(data, path: str = "") -> dict[str, float]:
    """Walk nested dict/list structures yielding {dotted.path: numeric_value}."""
    out: dict[str, float] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            out.update(_flatten_yaml_numbers(v, f"{path}.{k}" if path else k))
    elif isinstance(data, list):
        for i, v in enumerate(data):
            out.update(_flatten_yaml_numbers(v, f"{path}[{i}]"))
    elif isinstance(data, (int, float)) and not isinstance(data, bool):
        out[path] = float(data)
    return out


def _is_get_fallback(parents: dict[int, ast.AST], node: ast.Constant) -> bool:
    """True if `node` is the 2nd positional arg to a `.get(key, default)` call."""
    parent = parents.get(id(node))
    if not isinstance(parent, ast.Call):
        return False
    func = parent.func
    if not (isinstance(func, ast.Attribute) and func.attr == "get"):
        return False
    return len(parent.args) >= 2 and parent.args[1] is node


def _is_field_call_kwarg(parents: dict[int, ast.AST], node: ast.Constant) -> bool:
    """True if `node` is a kwarg value inside a Pydantic `Field(...)` call."""
    parent = parents.get(id(node))
    # Literal sits inside a keyword node: Call -> keyword -> Constant
    if not isinstance(parent, ast.keyword):
        return False
    if parent.arg not in {"default", "ge", "le", "gt", "lt"}:
        return False
    grand = parents.get(id(parent))
    if not isinstance(grand, ast.Call):
        return False
    func = grand.func
    name = func.id if isinstance(func, ast.Name) else (
        func.attr if isinstance(func, ast.Attribute) else None
    )
    return name == "Field"


def _is_keyword_default(parents: dict[int, ast.AST], node: ast.Constant) -> bool:
    """True if `node` is a function/method default value (e.g. `def f(x: int = 5)`)."""
    parent = parents.get(id(node))
    return isinstance(parent, ast.arguments)


def _collect_numeric_literals(py_path: Path) -> list[tuple[int | float, int]]:
    """Parse a Python file and return [(value, lineno), ...] for all number literals.

    Values preserve their original type (int vs float) — critical for distinguishing
    year counts (int 5) from percentage thresholds (float 5.0).

    Skips literals that are safe by construction:
      - 2nd positional arg of a `.get(key, default)` call (backward-compat fallback)
      - `default=` / bounds kwargs to Pydantic `Field(...)` (structural schema default)
      - function/method parameter defaults (already safe by type)
    """
    source = py_path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(py_path))
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    hits: list[tuple[int | float, int]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, (int, float))):
            continue
        if isinstance(node.value, bool):
            continue
        if (
            _is_get_fallback(parents, node)
            or _is_field_call_kwarg(parents, node)
            or _is_keyword_default(parents, node)
        ):
            continue
        hits.append((node.value, node.lineno))
    return hits


def _is_allowlisted(stem: str, value: float) -> bool:
    return any(s == stem and abs(v - value) < 1e-9 for s, v, _ in ALLOWLIST)


@pytest.mark.parametrize(
    "value,source_key", CRITICAL_VALUES, ids=[sk for _, sk in CRITICAL_VALUES],
)
def test_critical_assumption_not_duplicated_in_engine(
    value: int | float, source_key: str,
) -> None:
    """No critical assumptions.yaml value may appear as a literal in engine/*.py.

    Type-strict: int 5 and float 5.0 are treated as distinct so that year counts
    (`range(5)`, `years_list=[5, 10]`) are not conflated with percentage
    thresholds stored in YAML as floats (`rebalancing_drift_threshold_pct: 5.0`).
    """
    offenders: list[str] = []
    for py_file in sorted(ENGINE_DIR.glob("*.py")):
        stem = py_file.stem
        if _is_allowlisted(stem, value):
            continue
        hits = _collect_numeric_literals(py_file)
        for literal, lineno in hits:
            if type(literal) is not type(value):
                continue
            if isinstance(value, float) and abs(literal - value) >= 1e-9:
                continue
            if isinstance(value, int) and literal != value:
                continue
            offenders.append(f"{py_file.name}:{lineno} — literal {literal!r}")

    assert not offenders, (
        f"Hardcoded literal {value!r} (should read from assumptions.yaml:{source_key}) "
        f"found in engine code:\n  "
        + "\n  ".join(offenders)
        + "\nEither read from assumptions, or add an entry to ALLOWLIST in this test "
        "explaining why the literal has independent semantic meaning."
    )


def test_model_portfolios_constant_removed() -> None:
    """MODEL_PORTFOLIOS dict was removed from engine/investments.py in v9.4.2."""
    src = (ENGINE_DIR / "investments.py").read_text(encoding="utf-8")
    # The comment mentioning the historical name is allowed; a `MODEL_PORTFOLIOS = {`
    # reassignment is not.
    assert not re.search(r"^MODEL_PORTFOLIOS\s*=", src, re.MULTILINE), (
        "MODEL_PORTFOLIOS dict must not be redefined in investments.py — "
        "risk profile metadata lives in config/assumptions.yaml under `risk_profiles`."
    )


def test_critical_values_exist_in_assumptions(assumptions: dict) -> None:
    """Each critical value declared above must actually exist in assumptions.yaml.

    Guards against CRITICAL_VALUES drift — if an assumption is renamed, this
    test fails loudly rather than the guard silently becoming a no-op.
    """
    flat = _flatten_yaml_numbers(assumptions)
    missing: list[str] = []
    for value, source_key in CRITICAL_VALUES:
        if source_key in flat:
            actual = flat[source_key]
            if abs(actual - value) > 1e-9:
                missing.append(f"{source_key}: expected {value}, got {actual}")
        else:
            # Some source keys like `fee_comparison.low_cost_total_pct` map directly.
            # Try dotted lookup on the raw dict too.
            parts = source_key.split(".")
            cur: object = assumptions
            try:
                for p in parts:
                    cur = cur[p]  # type: ignore[index]
                if abs(float(cur) - value) > 1e-9:  # type: ignore[arg-type]
                    missing.append(f"{source_key}: expected {value}, got {cur!r}")
            except (KeyError, TypeError):
                missing.append(f"{source_key}: not found in assumptions.yaml")

    assert not missing, (
        "Critical values declared in CRITICAL_VALUES do not match assumptions.yaml:\n  "
        + "\n  ".join(missing)
    )
