"""REV-003 — authenticated reviewer actions.

Covers SPEC §9 acceptance:
- session auth/expiry/CSRF, nonce replay, optimistic locking, idempotency;
- an edited fact without valid support/derivation cannot be saved approved;
- every decision records actor/role/input-version/time/reason/output-version;
- concurrent decisions cannot silently overwrite;
- material/policy/rights changes need a later-day cooling-period confirmation;
- sensitive classes can never be bulk-approved.
Deterministic; no network, credentials or model calls.
"""
import pytest

from atlas import reviewer_actions as ra
from atlas.schemas import validate

FUTURE = "2026-12-31T00:00:00Z"
NOW = "2026-09-02T10:00:00Z"


def session(roles=ra.HUMAN_ROLES, actor="Alexios", authenticated=True,
            expires=FUTURE, csrf="csrf1"):
    return ra.Session(actor=actor, roles=frozenset(roles),
                      authenticated=authenticated, expires_at=expires, csrf_token=csrf)


def req(**over):
    base = dict(task_id="rvt_0123456789ab", action="approve",
                role="operator_reviewer", decision_class="ordinary_review",
                target_ref="rec_x", expected_version="v0", reason="looks correct",
                nonce="n1", idempotency_key="k1", csrf="csrf1",
                input_hashes={"source": "a" * 64})
    base.update(over)
    return ra.ActionRequest(**base)


def test_valid_action_records_decision_and_bumps_version():
    p = ra.ActionProcessor()
    r = p.process(session(), req(), NOW)
    validate("review-decision.schema.json", r["decision"])
    assert r["decision"]["decided_by"] == "Alexios"
    assert r["decision"]["role"] == "operator_reviewer"
    assert r["input_version"] == "v0" and r["output_version"] == "v1"
    assert p.current_version("rec_x") == "v1"


def test_session_auth_expiry_csrf_and_assistant_not_reviewer():
    p = ra.ActionProcessor()
    with pytest.raises(ra.AuthError):
        p.process(session(authenticated=False), req(), NOW)
    with pytest.raises(ra.AuthError):
        p.process(session(expires="2026-09-02T09:00:00Z"), req(), NOW)  # expired
    with pytest.raises(ra.AuthError):
        p.process(session(), req(csrf="wrong"), NOW)
    with pytest.raises(ra.AuthError):
        p.process(session(actor="assistant"), req(), NOW)  # assistant is never a reviewer


def test_role_separation_between_decision_types():
    p = ra.ActionProcessor()
    # release_bot cannot make review decisions
    with pytest.raises(ra.RoleError):
        p.process(session(roles=("release_bot",)), req(role="release_bot"), NOW)
    # a suppression needs the rights adjudicator, not the ordinary reviewer
    with pytest.raises(ra.RoleError):
        p.process(session(), req(action="suppress", decision_class="suppression_retraction",
                                 role="operator_reviewer"), NOW)
    # correct role works
    r = p.process(session(), req(action="suppress", decision_class="suppression_retraction",
                                 role="policy_rights_adjudicator"), NOW)
    assert r["decision"]["role"] == "policy_rights_adjudicator"


def test_nonce_replay_rejected():
    p = ra.ActionProcessor()
    p.process(session(), req(nonce="n1", idempotency_key="k1"), NOW)
    with pytest.raises(ra.ReplayError):
        p.process(session(), req(nonce="n1", idempotency_key="k2", expected_version="v1"), NOW)


def test_idempotent_retry_returns_same_result_without_reapplying():
    p = ra.ActionProcessor()
    r1 = p.process(session(), req(idempotency_key="k1"), NOW)
    r2 = p.process(session(), req(idempotency_key="k1"), NOW)  # identical retry
    assert r1 == r2
    assert p.current_version("rec_x") == "v1"  # not bumped twice


def test_optimistic_locking_blocks_stale_write():
    p = ra.ActionProcessor()
    with pytest.raises(ra.ConcurrencyError):
        p.process(session(), req(expected_version="v1"), NOW)  # current is v0
    # two writers off the same v0: first wins, second (stale) is rejected
    p2 = ra.ActionProcessor()
    p2.process(session(), req(nonce="a", idempotency_key="ka", expected_version="v0"), NOW)
    with pytest.raises(ra.ConcurrencyError):
        p2.process(session(), req(nonce="b", idempotency_key="kb", expected_version="v0"), NOW)


def test_edited_fact_without_support_cannot_be_approved():
    p = ra.ActionProcessor()
    bad = req(action="edit", edited_assertion={"assertion_ref": "a1",
                                               "kind": "source_derived", "support": []})
    with pytest.raises(ra.SupportError):
        p.process(session(), bad, NOW)
    ok = req(action="edit", nonce="n2", idempotency_key="k2",
             edited_assertion={"assertion_ref": "a1", "kind": "source_derived",
                               "support": ["anc_1"]})
    r = p.process(session(), ok, NOW)
    assert r["output_version"] == "v1"


def test_cooling_period_requires_later_day_and_fresh_diff():
    p = ra.ActionProcessor()
    mc = dict(action="correct", decision_class="material_correction",
              role="operator_reviewer", target_ref="rec_m", fresh_diff_hash="d1")
    # no staged intent -> refused
    with pytest.raises(ra.CoolingPeriodError):
        p.process(session(), req(nonce="m0", idempotency_key="km0", **mc), NOW)
    p.stage_cooling_period("rec_m", "material_correction", "2026-09-02T10:00:00Z", "d1")
    # same calendar day -> refused
    with pytest.raises(ra.CoolingPeriodError):
        p.process(session(), req(nonce="m1", idempotency_key="km1", **mc),
                  "2026-09-02T15:00:00Z")
    # later day, wrong diff -> refused
    with pytest.raises(ra.CoolingPeriodError):
        p.process(session(), req(nonce="m2", idempotency_key="km2",
                                 **{**mc, "fresh_diff_hash": "d2"}), "2026-09-03T09:00:00Z")
    # later day, matching diff -> allowed
    r = p.process(session(), req(nonce="m3", idempotency_key="km3", **mc),
                  "2026-09-03T09:00:00Z")
    assert r["decision"]["action"] == "correct"


def test_sensitive_classes_cannot_be_bulk_approved():
    p = ra.ActionProcessor()
    with pytest.raises(ra.BulkForbiddenError):
        p.process_bulk(session(), [
            req(nonce="b1", idempotency_key="kb1", target_ref="r1"),
            req(nonce="b2", idempotency_key="kb2", target_ref="r2",
                action="suppress", decision_class="suppression_retraction",
                role="policy_rights_adjudicator"),
        ], NOW)
    # a bulk of only ordinary reviews is allowed
    out = p.process_bulk(session(), [
        req(nonce="c1", idempotency_key="kc1", target_ref="r1"),
        req(nonce="c2", idempotency_key="kc2", target_ref="r2"),
    ], NOW)
    assert len(out) == 2 and all(o["output_version"] == "v1" for o in out)
