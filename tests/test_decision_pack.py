"""REV-004 — weekly decision pack and transport.

Covers SPEC §9 acceptance:
- packs are capped; excess stays queued and discovery throttles;
- single-use view links expire; replayed links/envelopes fail;
- channel carries only rights-permitted summaries; a link is never a bearer
  credential (channel compromise alone cannot approve/publish);
- proposed actions bind to exact input hashes; a change invalidates the draft;
- unanswered cards expire into their restrictive state.
Deterministic; no network, credentials or model calls.
"""
import pytest

from atlas import decision_pack as dp
from atlas import review_card as rc
from atlas.schemas import validate

H = "a" * 64
FAR = "2027-01-01T00:00:00Z"


def _item(i, priority="P2", minutes=20, complex=False, expiry=FAR):
    return {"priority": priority, "age_seconds": 1000 - i, "value": i,
            "question": f"q{i}", "proposed_answer": "include",
            "restrictive_default": "human_review", "estimated_minutes": minutes,
            "input_hashes": {"source": H}, "expiry": expiry, "complex": complex}


def test_pack_capped_by_minutes_excess_queued_and_throttles():
    items = [_item(i, minutes=20) for i in range(30)]  # 30*20=600 min >> 240 cap
    out = dp.build_pack(items, "2026-W36", "2026-09-02T09:00:00Z")
    assert out["pack"]["estimated_review_minutes"] <= dp.CAPS["review_minutes"]
    assert len(out["items"]) == 12  # 240/20
    assert len(out["excess"]) == 18
    assert out["throttle_discovery"] is True
    validate("decision-pack.schema.json", out["pack"])
    assert out["pack"]["caps"] == dp.CAPS


def test_pack_orders_p0_p1_first():
    items = ([_item(i, priority="P2", minutes=5) for i in range(3)]
             + [_item(100, priority="P1", minutes=5), _item(101, priority="P0", minutes=5)])
    out = dp.build_pack(items, "2026-W36", "2026-09-02T09:00:00Z")
    first_two_qs = [it["question"] for it in out["items"][:2]]
    assert first_two_qs == ["q101", "q100"]  # P0 then P1 before the P2s


def test_complex_decisions_capped_at_three():
    items = [_item(i, minutes=5, complex=True) for i in range(6)]
    out = dp.build_pack(items, "2026-W36", "2026-09-02T09:00:00Z")
    assert len(out["items"]) == 3 and len(out["excess"]) == 3


def test_view_link_single_use_and_expiry():
    store = dp.ViewLinkStore()
    tok = store.issue("pck_x-000", "2026-09-03T00:00:00Z", salt="s1")
    assert store.consume(tok, "2026-09-02T10:00:00Z") == "pck_x-000"
    with pytest.raises(dp.DecisionPackError):  # replay
        store.consume(tok, "2026-09-02T11:00:00Z")
    tok2 = store.issue("pck_x-001", "2026-09-02T00:00:00Z", salt="s2")
    with pytest.raises(dp.DecisionPackError):  # expired
        store.consume(tok2, "2026-09-02T10:00:00Z")


def test_envelope_binds_to_input_hashes():
    item = {"item_id": "pck_x-000", "input_hashes": {"source": H}}
    env = dp.draft_envelope(item, "approve")
    assert env["bearer_credential"] is False and env["requires_operator_confirmation"] is True
    assert dp.envelope_valid(env, {"source": H}) is True
    # a changed source/proposal/policy invalidates the draft
    assert dp.envelope_valid(env, {"source": "b" * 64}) is False


def test_transport_is_rights_safe_and_not_a_bearer_credential():
    card = rc.build_card(
        task_id="rvt_0123456789ab", question="Include?", requested_decision="boundary_include",
        proposed_answer="include", issuer={"authority_role": "issuer_direct", "name": "FTC"},
        source_version_id="srcv_1", rights_state="restricted", security_state="clean",
        restricted=True, restrictive_default="human_review", expiry=FAR,
        options=[{"option": "include", "consequences": {"publication": "x", "freshness": "y", "downstream": "z"}}],
        canonical={"sha256": H, "anchors": ["anc_secret"]})
    payload = dp.transport_payload({"pack_id": "pck_x", "week": "2026-W36", "item_ids": ["i0"]},
                                   {"i0": card})
    blob = repr(payload)
    assert "anc_secret" not in blob  # restricted content never in the channel
    assert payload["bearer_credential"] is False
    assert dp.can_approve_from_channel(payload) is False


def test_unanswered_cards_expire_to_restrictive_state():
    items = [{"item_id": "i0", "expiry": "2026-09-02T09:00:00Z", "restrictive_default": "hold"},
             {"item_id": "i1", "expiry": "2027-01-01T00:00:00Z", "restrictive_default": "defer"}]
    out = dp.expire_unanswered(items, "2026-09-02T12:00:00Z")
    assert out == [{"item_id": "i0", "disposition": "hold"}]
    assert all(o["disposition"] not in ("accept", "publish", "include") for o in out)
