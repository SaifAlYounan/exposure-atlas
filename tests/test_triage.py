"""TRIAGE-001 — boundary rubric and checklist.

Covers SPEC §9 acceptance:
- the final outcome is reconstructable from criterion results + boundary
  version (evaluate is a pure function);
- a missing criterion cannot silently become an include;
- close exclusions and inaccessible-primary cases route to review /
  awaiting_primary.
Deterministic; no network, credentials or model calls.
"""
import pytest

from atlas import triage
from atlas.schemas import validate


def rubric():
    return triage.load_rubric()


# a fully in-scope, includable checklist
INCLUDE = {
    "substantive_forum": "met",
    "proceeding_type": "met",
    "date_in_window": "met",
    "organisational_nexus": "met",
    "ai_nexus": "met",
    "authoritative_instrument_exists": "met",
    "primary_accessible": "met",
    "announced_formal_investigation": "not_applicable",
    "press_without_primary": "not_met",
    "commentary_only": "not_met",
    "legislation_without_enforcement": "not_met",
    "ai_incidental_only": "not_met",
    "purely_private_dispute": "not_met",
}


def _with(**over):
    d = dict(INCLUDE)
    d.update(over)
    return d


def test_rubric_config_validates_and_binds_boundary():
    r = rubric()
    assert r["schema_version"] == "atlas-boundary-rubric/v1"
    assert r["boundary_version"] == "1.0.0"
    kinds = {c["kind"] for c in r["criteria"]}
    assert {"core_inclusion", "exclusion", "instrument", "accessibility"} <= kinds


def test_include_is_reconstructed_from_full_checklist():
    r = rubric()
    out = triage.evaluate(INCLUDE, r)
    assert out["outcome"] == "include" and out["route"] == "include"
    assert out["boundary_version"] == "1.0.0"
    # deterministic: same inputs -> same outcome
    assert triage.evaluate(INCLUDE, r) == out


def test_missing_criterion_never_silently_includes():
    r = rubric()
    partial = dict(INCLUDE)
    del partial["ai_nexus"]  # drop a core criterion
    out = triage.evaluate(partial, r)
    assert out["outcome"] != "include"
    assert out["route"] == "review"
    assert "missing" in out["reason"]


def test_exclusion_forces_exclude():
    r = rubric()
    out = triage.evaluate(_with(ai_incidental_only="met"), r)
    assert out["outcome"] == "exclude" and out["route"] == "exclude"


def test_core_not_met_is_exclude_but_uncertain_is_review():
    r = rubric()
    assert triage.evaluate(_with(ai_nexus="not_met"), r)["outcome"] == "exclude"
    close = triage.evaluate(_with(ai_nexus="uncertain"), r)
    assert close["outcome"] == "uncertain" and close["route"] == "review"


def test_no_instrument_routes_awaiting_or_review():
    r = rubric()
    # announced investigation, no instrument yet -> awaiting_primary
    inv = triage.evaluate(_with(authoritative_instrument_exists="not_met",
                                announced_formal_investigation="met"), r)
    assert inv["route"] == "awaiting_primary" and inv["outcome"] == "uncertain"
    # no instrument and no investigation -> review
    none = triage.evaluate(_with(authoritative_instrument_exists="not_met",
                                 announced_formal_investigation="not_met"), r)
    assert none["route"] == "review" and none["outcome"] == "uncertain"


def test_inaccessible_primary_routes_awaiting_primary():
    r = rubric()
    out = triage.evaluate(_with(primary_accessible="not_met"), r)
    assert out["route"] == "awaiting_primary" and out["outcome"] == "uncertain"


def test_invalid_result_value_rejected():
    r = rubric()
    with pytest.raises(triage.RubricError):
        triage.evaluate(_with(ai_nexus="MAYBE"), r)
    with pytest.raises(triage.RubricError):
        triage.evaluate({**INCLUDE, "not_a_criterion": "met"}, r)


def test_build_proposal_validates_and_is_reconstructable():
    r = rubric()
    p = triage.build_proposal("cnd_abcdef123456", INCLUDE, r)
    validate("boundary-proposal.schema.json", p)
    assert p["proposed_outcome"] == "include"
    assert p["proposed_by"] == "manual"
    # the proposal carries every criterion result -> outcome reconstructable
    got = {c["criterion"]: c["result"] for c in p["criteria"]}
    assert got == INCLUDE
    assert triage.evaluate(got, r)["outcome"] == p["proposed_outcome"]
    # stable id for the same checklist
    assert triage.build_proposal("cnd_abcdef123456", INCLUDE, r)["proposal_id"] == p["proposal_id"]
