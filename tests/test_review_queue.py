"""REV-001 — review queue model and priorities.

Covers SPEC §9 acceptance:
- arrival/exit/age/handling-time/reason-codes measurable by queue;
- backpressure pauses low-priority discovery/migration while preserving
  P0/P1;
- every item has an expiry + restrictive default; no answer -> restrictive
  state, never acceptance/publication;
- P0 emergency / P1 same-day / ordinary weekly paths.
Deterministic; no network, credentials or model calls.
"""
import pytest

from atlas import review_queue as rq
from atlas.schemas import validate


def test_make_task_validates_with_expiry_and_restrictive_default():
    t = rq.make_task("new_candidates", "P2", "Include this FTC matter?",
                     "2026-09-02T09:00:00Z")
    validate("review-task.schema.json", t)
    assert t["restrictive_default"] in rq.RESTRICTIVE_DEFAULTS
    assert t["expiry"] > t["created_at"]  # ISO strings, same tz/width


def test_restrictive_default_cannot_be_accepting():
    with pytest.raises(rq.ReviewQueueError):
        rq.make_task("new_candidates", "P2", "q", "2026-09-02T09:00:00Z",
                     restrictive_default="accept")
    with pytest.raises(rq.ReviewQueueError):
        rq.make_task("new_candidates", "P2", "q", "2026-09-02T09:00:00Z",
                     restrictive_default="publish")


def test_handling_paths():
    assert rq.handling_path("P0") == "emergency"
    assert rq.handling_path("P1") == "same_day"
    assert rq.handling_path("P2") == "weekly_pack"
    assert rq.handling_path("P3") == "weekly_pack"


def test_unanswered_expires_to_restrictive_never_acceptance():
    q = rq.ReviewQueue()
    t = rq.make_task("uncertain", "P2", "boundary uncertain?", "2026-09-02T09:00:00Z",
                     ttl_hours=1)
    q.add(t, "2026-09-02T09:00:00Z")
    # before expiry: nothing applied
    assert q.expire_unanswered("2026-09-02T09:30:00Z") == []
    # after expiry: resolved to the restrictive default
    applied = q.expire_unanswered("2026-09-02T11:00:00Z")
    assert len(applied) == 1
    disp = applied[0]["disposition"]
    assert disp in rq.RESTRICTIVE_DEFAULTS
    assert disp not in ("accept", "publish", "include")


def test_backpressure_pauses_low_priority_but_preserves_p0_p1():
    q = rq.ReviewQueue(p01_backpressure_threshold=3)
    at = "2026-09-02T09:00:00Z"
    assert q.backpressure_paused_queues() == []
    for i in range(3):
        q.add(rq.make_task("uncertain", "P1", f"q{i}", at), at)
    paused = q.backpressure_paused_queues()
    assert set(paused) == set(rq.LOW_PRIORITY_QUEUES)
    # P0/P1 queues are never in the paused set
    assert "uncertain" not in paused and "quarantine" not in paused


def test_metrics_measurable_by_queue():
    q = rq.ReviewQueue()
    a = "2026-09-02T09:00:00Z"
    t1 = rq.make_task("new_candidates", "P2", "q1", a)
    t2 = rq.make_task("new_candidates", "P2", "q2", a)
    q.add(t1, a)
    q.add(t2, a)
    q.resolve(t1["task_id"], "2026-09-02T10:00:00Z", reason="approved", resolution="include")
    m = q.metrics("new_candidates", "2026-09-02T11:00:00Z")
    assert m["arrivals"] == 2 and m["exits"] == 1 and m["open"] == 1
    assert m["handling_seconds"] == [3600.0]  # t1 handled in 1h
    assert m["max_open_age_seconds"] == 7200.0  # t2 open 2h
    assert m["reason_codes"] == {"approved": 1}


def test_task_id_stable_and_unknown_queue_rejected():
    a = "2026-09-02T09:00:00Z"
    assert rq.make_task("corrections", "P0", "x", a)["task_id"] == \
        rq.make_task("corrections", "P0", "x", a)["task_id"]
    with pytest.raises(rq.ReviewQueueError):
        rq.make_task("not_a_queue", "P2", "q", a)
