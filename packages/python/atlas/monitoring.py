"""Monitoring target/check primitives and freshness aggregation (MON-000).

Temporal invariant (SPEC 2.4): a failed check NEVER advances
last_successful_check_at; success is per-target; one source succeeding
does not erase another's failure. Record-level freshness is the worst
applicable target state and the earliest due time, under a versioned
aggregation rule.
"""
from .schemas import validate

AGGREGATION_RULE_VERSION = "1.0.0"
_SEVERITY = {"current": 0, "due": 1, "overdue": 2, "stale": 3,
             "monitoring_degraded": 3, "unmonitored": 2}


def apply_check(target: dict, *, outcome: str, attempted_at: str,
                next_due: str, retry_due: str | None = None) -> dict:
    """Returns a NEW target state dict; never mutates in place."""
    validate("monitor-target.schema.json", target)
    if outcome not in ("success_unchanged", "success_changed", "failure"):
        raise ValueError(f"unknown outcome {outcome!r}")
    new = dict(target)
    new["last_attempted_check_at"] = attempted_at
    if outcome == "failure":
        new["consecutive_failures"] = target.get("consecutive_failures", 0) + 1
        new["retry_due_at"] = retry_due
        # last_successful_check_at DELIBERATELY untouched
    else:
        new["consecutive_failures"] = 0
        new["last_successful_check_at"] = attempted_at
        new["next_check_due_at"] = next_due
        new["retry_due_at"] = None
    validate("monitor-target.schema.json", new)
    return new


def target_freshness(target: dict, *, as_of: str, grace: str) -> str:
    """Pure: all times are supplied ISO strings, compared lexically
    (valid for UTC ISO-8601)."""
    last_ok = target.get("last_successful_check_at")
    if last_ok is None:
        return "unmonitored"
    if target.get("consecutive_failures", 0) >= target.get(
            "degraded_after_failures", 3):
        return "monitoring_degraded"
    due = target["next_check_due_at"]
    if as_of <= due:
        return "current"
    return "stale" if as_of > grace else "overdue"


def aggregate_record_freshness(targets: list[dict], *, as_of: str,
                               grace_by_target: dict[str, str]) -> dict:
    if not targets:
        return {"state": "unmonitored", "worst_targets": [],
                "aggregation_rule_version": AGGREGATION_RULE_VERSION}
    states = {}
    for t in targets:
        states[t["target_id"]] = target_freshness(
            t, as_of=as_of, grace=grace_by_target.get(t["target_id"], as_of))
    worst = max(states.values(), key=lambda s: _SEVERITY[s])
    return {"state": worst,
            "worst_targets": sorted(k for k, v in states.items() if v == worst),
            "aggregation_rule_version": AGGREGATION_RULE_VERSION,
            "as_of": as_of}
