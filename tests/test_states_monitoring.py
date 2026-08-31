"""DOM-004 state machines and MON-000 temporal invariant tests."""
import pytest

from atlas.monitoring import (aggregate_record_freshness, apply_check,
                              target_freshness)
from atlas.states import TransitionError, transition

AT = "2026-08-31T12:00:00Z"


def test_illegal_transitions_fail():
    with pytest.raises(TransitionError):   # no direct draft -> published
        transition("revision", "draft", "published")
    with pytest.raises(TransitionError):   # passed runs are immutable
        transition("verification", "passed", "failed")
    with pytest.raises(TransitionError):
        transition("job", "completed", "ready")
    with pytest.raises(TransitionError):   # candidate never becomes 'published'
        transition("candidate_disposition", "unresolved", "published")
    assert transition("revision", "draft", "in_review") == "in_review"
    assert transition("revision", "in_review", "draft") == "draft"
    assert transition("candidate_disposition", "excluded", "unresolved") \
        == "unresolved"  # boundary-change replay


def _target(**over):
    t = {"schema_version": "atlas-monitor-target/v1",
         "target_id": "mtg_abcdef123456", "source_id": "ftc_enforcement",
         "kind": "listing_page", "last_attempted_check_at": None,
         "last_successful_check_at": None,
         "next_check_due_at": "2026-09-14T00:00:00Z", "retry_due_at": None,
         "consecutive_failures": 0, "degraded_after_failures": 3}
    t.update(over)
    return t


def test_failed_check_never_advances_success():
    t = _target(last_successful_check_at="2026-08-01T00:00:00Z")
    t2 = apply_check(t, outcome="failure", attempted_at=AT,
                     next_due="2026-09-14T00:00:00Z",
                     retry_due="2026-08-31T18:00:00Z")
    assert t2["last_successful_check_at"] == "2026-08-01T00:00:00Z"
    assert t2["last_attempted_check_at"] == AT
    assert t2["consecutive_failures"] == 1
    assert t["consecutive_failures"] == 0  # original untouched
    t3 = apply_check(t2, outcome="success_unchanged", attempted_at=AT,
                     next_due="2026-09-14T00:00:00Z")
    assert t3["last_successful_check_at"] == AT
    assert t3["consecutive_failures"] == 0


def test_freshness_states_and_aggregation():
    ok = _target(last_successful_check_at=AT)
    assert target_freshness(ok, as_of=AT, grace="2026-09-21T00:00:00Z") == "current"
    overdue = _target(last_successful_check_at="2026-08-01T00:00:00Z",
                      next_check_due_at="2026-08-15T00:00:00Z")
    assert target_freshness(overdue, as_of=AT,
                            grace="2026-09-15T00:00:00Z") == "overdue"
    assert target_freshness(overdue, as_of="2026-09-16T00:00:00Z",
                            grace="2026-09-15T00:00:00Z") == "stale"
    degraded = _target(last_successful_check_at=AT, consecutive_failures=3)
    assert target_freshness(degraded, as_of=AT, grace=AT) == "monitoring_degraded"
    # one source succeeding does not erase another's failure
    agg = aggregate_record_freshness(
        [ok, dict(degraded, target_id="mtg_bbbbbbbbbbbb")], as_of=AT,
        grace_by_target={})
    assert agg["state"] == "monitoring_degraded"
    assert agg["worst_targets"] == ["mtg_bbbbbbbbbbbb"]
    assert aggregate_record_freshness([], as_of=AT, grace_by_target={})[
        "state"] == "unmonitored"
