"""REV-002 — review-task builder (decision cards).

Covers SPEC §9 acceptance:
- source-derived assertions link to evidence; derived edits link to accepted
  parents + a versioned transform;
- OCR and superseded-source warnings cannot be hidden;
- classification edits require a taxonomy rationale, not source anchors;
- the channel-safe summary never exposes restricted content;
- model rationales are short evidence, never chain-of-thought.
Deterministic; no network, credentials or model calls.
"""
import pytest

from atlas import review_card as rc
from atlas.schemas import validate

BASE = dict(
    task_id="rvt_0123456789ab",
    question="Include this matter?",
    requested_decision="boundary_include",
    proposed_answer="include",
    issuer={"authority_role": "issuer_direct", "name": "US FTC"},
    source_version_id="srcv_abc123",
    rights_state="internal_only",
    security_state="clean",
    restricted=False,
    restrictive_default="human_review",
    expiry="2026-09-09T09:00:00Z",
    options=[{"option": "include", "consequences": {
        "publication": "eligible", "freshness": "fresh", "downstream": "creates record"}}],
)


def test_valid_card_builds_and_validates():
    card = rc.build_card(
        assertions=[{"assertion_ref": "asp_1", "kind": "source_derived",
                     "modality": "finding", "attribution": "order", "support": ["anc_1"]}],
        **BASE)
    validate("review-card.schema.json", card)
    assert card["card_id"].startswith("rvc_")


def test_source_derived_assertion_requires_anchor_support():
    with pytest.raises(rc.CardError):
        rc.build_card(
            assertions=[{"assertion_ref": "asp_x", "kind": "source_derived",
                         "modality": "finding", "attribution": "order", "support": []}],
            **BASE)


def test_derived_assertion_requires_parents_and_transform():
    with pytest.raises(rc.CardError):
        rc.build_card(
            assertions=[{"assertion_ref": "asp_d", "kind": "derived",
                         "modality": "normalized", "attribution": "derived",
                         "derivation": {"parent_assertion_ids": [], "transform_version": ""}}],
            **BASE)
    # valid derived assertion passes
    card = rc.build_card(
        assertions=[{"assertion_ref": "asp_d", "kind": "derived",
                     "modality": "normalized", "attribution": "derived",
                     "derivation": {"parent_assertion_ids": ["asp_1"], "transform_version": "t/v1"}}],
        **BASE)
    validate("review-card.schema.json", card)


def test_ocr_and_superseded_warnings_cannot_be_hidden():
    card = rc.build_card(ocr_detected=True, superseded_source=True, **BASE)
    kinds = {w["kind"] for w in card["warnings"]}
    assert "ocr" in kinds and "superseded_source" in kinds


def test_classification_edit_requires_taxonomy_rationale_not_anchors():
    with pytest.raises(rc.CardError):
        rc.build_card(classifications=[{"labels": ["x"], "taxonomy_version": "1.0.0",
                                        "is_edit": True}], **BASE)
    with pytest.raises(rc.CardError):
        rc.build_card(classifications=[{"labels": ["x"], "taxonomy_version": "1.0.0",
                                        "is_edit": True, "taxonomy_rationale": "ok",
                                        "support": ["anc_1"]}], **BASE)
    card = rc.build_card(classifications=[{"labels": ["x"], "taxonomy_version": "1.0.0",
                                          "is_edit": True, "taxonomy_rationale": "matches"}], **BASE)
    validate("review-card.schema.json", card)


def test_model_votes_reject_chain_of_thought_and_cap_length():
    with pytest.raises(rc.CardError):
        rc.build_card(model_votes=[{"assessor": "m", "result": "include",
                                    "rationale": "ok", "chain_of_thought": "..."}], **BASE)
    with pytest.raises(rc.CardError):
        rc.build_card(model_votes=[{"assessor": "m", "result": "include",
                                    "rationale": "x" * 601}], **BASE)


def test_channel_safe_summary_hides_restricted_content():
    card = rc.build_card(
        restricted=True,
        canonical={"sha256": "a" * 64, "anchors": ["anc_secret"]},
        assertions=[{"assertion_ref": "asp_1", "kind": "source_derived",
                     "modality": "finding", "attribution": "sealed order", "support": ["anc_secret"]}],
        model_votes=[{"assessor": "m", "result": "include", "rationale": "sensitive detail"}],
        **{k: v for k, v in BASE.items() if k != "restricted"})
    s = rc.channel_safe_summary(card)
    blob = repr(s)
    # none of the restricted content leaks into the summary
    assert "anc_secret" not in blob and "sensitive detail" not in blob and "sealed order" not in blob
    for f in ("canonical", "assertions", "model_votes", "proposed_answer"):
        assert f not in s
    assert s["authenticated_view_required"] is True
    assert s["question"] == card["question"]  # routing metadata is safe
    # warning kinds are safe to surface (not their content)
    assert isinstance(s["warning_kinds"], list)


def test_non_restricted_summary_may_include_proposed_answer():
    card = rc.build_card(**BASE)
    s = rc.channel_safe_summary(card)
    assert s["proposed_answer"] == "include"
    assert s["option_labels"] == ["include"]
