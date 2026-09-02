"""REV-005 — workload calibration.

Covers SPEC §9 acceptance:
- weekly capacity derived from measured handling with 60-90 min reserved;
- initial §0.2 caps enforced until three real packs + operator revision;
- demand over capacity pauses low-value discovery/migration before evidence
  gates change;
- operator-unavailability freezes decisions/releases, monitoring continues,
  degraded states visible;
- single-operator delayed re-review is never inter-reviewer agreement.
Deterministic; no network, credentials or model calls.
"""
import pytest

from atlas import calibration as cal


def test_stats_median_p95_edit_deferral_by_card_type():
    c = cal.Calibration()
    for m in (5, 10, 15, 20, 100):
        c.record("clean", m)
    c.record("clean", 8, edited=True, deferred=True)
    s = c.stats_by_card_type()["clean"]
    assert s["n"] == 6
    assert s["median_minutes"] == cal.median([5, 10, 15, 20, 100, 8])
    assert s["p95_minutes"] >= s["median_minutes"]
    assert 0 < s["edit_rate"] <= 1 and 0 < s["deferral_rate"] <= 1


def test_available_minutes_reserves_60_to_90():
    assert cal.available_review_minutes(75) == 165  # 240 - 75
    assert cal.available_review_minutes(60) == 180
    assert cal.available_review_minutes(90) == 150
    with pytest.raises(cal.CalibrationError):
        cal.available_review_minutes(30)
    with pytest.raises(cal.CalibrationError):
        cal.available_review_minutes(120)


def test_initial_caps_enforced_until_three_packs_and_operator_revision():
    assert cal.enforced_caps(0) == cal.INITIAL_CAPS
    assert cal.enforced_caps(2, {"review_minutes": 300}) == cal.INITIAL_CAPS  # < 3 packs
    assert cal.enforced_caps(3) == cal.INITIAL_CAPS  # 3 packs but no operator revision
    revised = {"review_minutes": 300, "decision_cards": 30,
               "record_reviews": 15, "complex_decisions": 4}
    assert cal.enforced_caps(3, revised) == revised  # 3 packs + operator revision


def test_throttle_discovery_triggers():
    base = dict(trailing_3wk_arrivals=50, review_capacity=100,
                pending_weeks_of_capacity=1, oldest_ordinary_days=5,
                oldest_status_correction_hours=10, deferral_rate_two_packs=0.05)
    assert cal.throttle_discovery(**base) is False
    assert cal.throttle_discovery(**{**base, "trailing_3wk_arrivals": 85}) is True  # >80%
    assert cal.throttle_discovery(**{**base, "pending_weeks_of_capacity": 3}) is True
    assert cal.throttle_discovery(**{**base, "oldest_ordinary_days": 22}) is True
    assert cal.throttle_discovery(**{**base, "oldest_status_correction_hours": 49}) is True
    assert cal.throttle_discovery(**{**base, "deferral_rate_two_packs": 0.25}) is True


def test_demand_over_capacity_pauses_before_changing_gates():
    over = cal.demand_response(300, 165)
    assert over["over_capacity"] is True
    assert over["actions"] == ["pause_low_value_discovery", "pause_migration"]
    assert over["change_evidence_gates"] is False  # gates never changed to absorb demand
    under = cal.demand_response(100, 165)
    assert under["over_capacity"] is False and under["actions"] == []
    assert under["change_evidence_gates"] is False


def test_operator_unavailable_mode_freezes_but_keeps_monitoring():
    m = cal.operator_unavailable_mode()
    assert m["decisions"] == "frozen" and m["releases"] == "frozen"
    assert m["monitoring"] == "active" and m["degraded_states_visible"] is True


def test_single_operator_resample_is_never_inter_reviewer():
    assert cal.resample_label(same_operator=True) == "intra_rater_reliability"
    assert cal.resample_label(same_operator=False) == "inter_reviewer_agreement"
    cal.validate_report_labeling([{"same_operator": True, "label": "intra_rater_reliability"}])
    with pytest.raises(cal.CalibrationError):
        cal.validate_report_labeling([{"same_operator": True, "label": "inter_reviewer_agreement"}])
