"""Workload calibration (REV-005).

Derives weekly capacity from measured handling data and enforces the SPEC
§0.2 guardrails (SPEC §9 REV-005). Rules:

- weekly capacity comes from measured arrivals/mix/handling with 60-90 minutes
  reserved for releases/incidents/operational review;
- the initial §0.2 caps stay in force until three real packs justify an
  operator-approved revision;
- when demand exceeds capacity, low-value discovery and migration pause
  *before* any evidence gate is changed;
- operator-unavailability mode freezes decisions and releases while
  monitoring continues and degraded/stale states stay visible;
- single-operator delayed re-review is intra-rater reliability, never
  described as inter-reviewer agreement.

Pure and deterministic; no network, credentials or model calls (A0). These
are operational metrics, not a persisted domain object.
"""

# SPEC §0.2 initial caps.
INITIAL_CAPS = {"review_minutes": 240, "decision_cards": 25,
                "record_reviews": 12, "complex_decisions": 3}
RESERVE_MIN, RESERVE_MAX = 60, 90
MIN_PACKS_FOR_REVISION = 3


class CalibrationError(ValueError):
    pass


def percentile(values: list[float], p: float) -> float:
    """Deterministic nearest-rank-ish linear-interpolation percentile."""
    if not values:
        raise CalibrationError("no values")
    if not 0 <= p <= 100:
        raise CalibrationError("percentile out of range")
    s = sorted(values)
    if len(s) == 1:
        return float(s[0])
    rank = (p / 100) * (len(s) - 1)
    lo = int(rank)
    hi = min(lo + 1, len(s) - 1)
    frac = rank - lo
    return float(s[lo] + (s[hi] - s[lo]) * frac)


def median(values: list[float]) -> float:
    return percentile(values, 50)


class Calibration:
    """Records per-card-type handling data and derives stats."""

    def __init__(self):
        self._by_type: dict[str, list[dict]] = {}

    def record(self, card_type: str, handling_minutes: float, *,
               edited: bool = False, deferred: bool = False) -> None:
        self._by_type.setdefault(card_type, []).append(
            {"minutes": float(handling_minutes), "edited": edited, "deferred": deferred})

    def stats_by_card_type(self) -> dict:
        out = {}
        for ct, rows in self._by_type.items():
            mins = [r["minutes"] for r in rows]
            n = len(rows)
            out[ct] = {
                "n": n,
                "median_minutes": median(mins),
                "p95_minutes": percentile(mins, 95),
                "edit_rate": sum(r["edited"] for r in rows) / n,
                "deferral_rate": sum(r["deferred"] for r in rows) / n,
            }
        return out


def available_review_minutes(reserve_minutes: int = 75) -> int:
    """Weekly review minutes after reserving 60-90 min for releases/incidents."""
    if not RESERVE_MIN <= reserve_minutes <= RESERVE_MAX:
        raise CalibrationError(f"reserve must be {RESERVE_MIN}-{RESERVE_MAX} minutes")
    return INITIAL_CAPS["review_minutes"] - reserve_minutes


def enforced_caps(packs_completed: int, operator_approved_revision: dict | None = None) -> dict:
    """The §0.2 initial caps stay in force until three real packs AND an
    operator-approved revision justify a change."""
    if packs_completed < MIN_PACKS_FOR_REVISION or operator_approved_revision is None:
        return dict(INITIAL_CAPS)
    return dict(operator_approved_revision)


def throttle_discovery(*, trailing_3wk_arrivals: float, review_capacity: float,
                       pending_weeks_of_capacity: float, oldest_ordinary_days: float,
                       oldest_status_correction_hours: float,
                       deferral_rate_two_packs: float) -> bool:
    """SPEC §0.2 rule 7 discovery-throttle triggers (any one fires)."""
    return (trailing_3wk_arrivals > 0.80 * review_capacity
            or pending_weeks_of_capacity > 2
            or oldest_ordinary_days > 21
            or oldest_status_correction_hours > 48
            or deferral_rate_two_packs > 0.20)


def demand_response(demand_minutes: float, capacity_minutes: float) -> dict:
    """When demand exceeds capacity, pause low-value discovery/migration BEFORE
    any evidence gate is changed."""
    over = demand_minutes > capacity_minutes
    return {
        "over_capacity": over,
        "actions": ["pause_low_value_discovery", "pause_migration"] if over else [],
        "change_evidence_gates": False,
    }


def operator_unavailable_mode() -> dict:
    """Freeze decisions and releases; keep monitoring; keep degraded/stale
    states visible."""
    return {
        "decisions": "frozen",
        "releases": "frozen",
        "monitoring": "active",
        "degraded_states_visible": True,
    }


def resample_label(same_operator: bool) -> str:
    """Single-operator delayed re-review is intra-rater reliability, never
    inter-reviewer agreement."""
    return "intra_rater_reliability" if same_operator else "inter_reviewer_agreement"


def validate_report_labeling(entries: list[dict]) -> None:
    """Reject any report that describes single-operator delayed re-review as
    inter-reviewer agreement."""
    for e in entries:
        if e.get("same_operator") and e.get("label") != "intra_rater_reliability":
            raise CalibrationError(
                "single-operator delayed re-review must not be described as "
                "inter-reviewer agreement")
