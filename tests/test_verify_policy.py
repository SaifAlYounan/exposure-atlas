"""VER-001/POL-001 tests including SP-01/SP-08-style fixtures and
fail-closed policy behavior."""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

import yaml
from atlas.kernel import Kernel
from atlas.policy import evaluate
from atlas.verify import ROLE_MODALITIES

AT = "2026-08-31T12:00:00Z"
FIX = ROOT / "tests" / "fixtures" / "documents"
HOSTS = ["www.ftc.gov", "www.courtlistener.com"]


@pytest.fixture()
def ftc(tmp_path):
    k = Kernel(tmp_path, HOSTS)
    sdoc, sver = k.ingest_fixture(
        FIX / "ftc_order_fixture.html",
        declared_url="https://www.ftc.gov/synthetic-fixture",
        declared_mime="text/html", issuer="US Federal Trade Commission",
        title="In the Matter of Acme Cognition (synthetic fixture)",
        document_role="regulator_decision", source_id="ftc_enforcement",
        copy_provenance_state="issuer_direct", retrieved_at=AT)
    art = k.canonicalize(sver["source_version_id"], AT)
    return k, sdoc, sver, art


def test_role_matrix_matches_config():
    cfg = yaml.safe_load((ROOT / "config" / "source-policy" / "v1.yaml").read_text())
    for role, spec in cfg["document_roles"].items():
        assert set(spec.get("may_establish", [])) == ROLE_MODALITIES[role], role


def test_quote_assertion_verifies(ftc):
    k, sdoc, sver, art = ftc
    quote = "Respondent shall pay a civil penalty of $5,000,000"
    anc = k.add_anchor(art["text_artifact_id"], quote)
    prop = k.propose(source_version_id=sver["source_version_id"],
                     subject_ref={"entity_type": "procedural_event",
                                  "entity_id": "evt_order"},
                     predicate="remedy.amount.statement", raw_value=quote,
                     modality="order", value_origin="source_quote",
                     support=[{"anchor_id": anc["anchor_id"], "role": "supports",
                               "passage_role": "operative_part",
                               "attributed_speaker": "issuing_regulator"}],
                     observed_at=AT)
    report = k.verify(prop["proposal_id"])
    assert report["overall"] == "pass"
    sem = [c for c in report["checks"] if c["check"] == "semantic_support"][0]
    assert sem["result"] == "indeterminate"  # never auto-approved


def test_sp08_declined_amount_cannot_become_ordered(ftc):
    """SP-08: the $9m the Commission DECLINED must not verify as an
    ordered penalty via mechanical quote presence: the declined-quote
    text differs from a bare amount claim, and semantic support stays
    indeterminate either way."""
    k, sdoc, sver, art = ftc
    quote = "The Commission declined to impose the proposed $9,000,000 penalty"
    anc = k.add_anchor(art["text_artifact_id"], quote)
    prop = k.propose(source_version_id=sver["source_version_id"],
                     subject_ref={"entity_type": "procedural_event",
                                  "entity_id": "evt_order"},
                     predicate="remedy.amount.statement",
                     raw_value="$9,000,000",  # mismatched: not the quote bytes
                     modality="order", value_origin="source_quote",
                     support=[{"anchor_id": anc["anchor_id"], "role": "supports",
                               "passage_role": "operative_part",
                               "attributed_speaker": "issuing_regulator"}],
                     observed_at=AT)
    report = k.verify(prop["proposal_id"])
    assert report["overall"] == "fail"  # quote != raw_value → mechanical fail


def test_sp01_press_release_cannot_carry_finding(ftc, tmp_path):
    k = Kernel(tmp_path / "k2", HOSTS)
    sdoc, sver = k.ingest_fixture(
        FIX / "ftc_order_fixture.html",
        declared_url="https://www.ftc.gov/press-fixture",
        declared_mime="text/html", issuer="US Federal Trade Commission",
        title="Press release (synthetic)", document_role="official_press_release",
        source_id="ftc_enforcement", copy_provenance_state="issuer_direct",
        retrieved_at=AT)
    art = k.canonicalize(sver["source_version_id"], AT)
    quote = "Respondent shall pay a civil penalty of $5,000,000"
    anc = k.add_anchor(art["text_artifact_id"], quote)
    prop = k.propose(source_version_id=sver["source_version_id"],
                     subject_ref={"entity_type": "procedural_event",
                                  "entity_id": "evt_x"},
                     predicate="outcome.finding", raw_value=quote,
                     modality="finding", value_origin="source_quote",
                     support=[{"anchor_id": anc["anchor_id"], "role": "supports",
                               "passage_role": "issuer_text",
                               "attributed_speaker": "issuer"}],
                     observed_at=AT)
    report = k.verify(prop["proposal_id"])
    fails = {c["check"]: c for c in report["checks"]}
    assert fails["source_role_permits_modality"]["result"] == "fail"
    assert report["overall"] == "fail"


def test_unverified_mirror_copy_blocks(ftc, tmp_path):
    k = Kernel(tmp_path / "k3", HOSTS)
    sdoc, sver = k.ingest_fixture(
        FIX / "ftc_order_fixture.html",
        declared_url="https://www.courtlistener.com/mirror-fixture",
        declared_mime="text/html", issuer="US District Court (synthetic)",
        title="Mirror copy (synthetic)", document_role="judgment_or_order",
        source_id="courtlistener_recap", copy_provenance_state="unverified",
        retrieved_at=AT)
    art = k.canonicalize(sver["source_version_id"], AT)
    anc = k.add_anchor(art["text_artifact_id"],
                       "Respondent shall pay a civil penalty of $5,000,000")
    prop = k.propose(source_version_id=sver["source_version_id"],
                     subject_ref={"entity_type": "procedural_event",
                                  "entity_id": "evt_y"},
                     predicate="remedy.amount.statement",
                     raw_value="Respondent shall pay a civil penalty of $5,000,000",
                     modality="order", value_origin="source_quote",
                     support=[{"anchor_id": anc["anchor_id"], "role": "supports",
                               "passage_role": "operative_part",
                               "attributed_speaker": "issuing_court"}],
                     observed_at=AT)
    report = k.verify(prop["proposal_id"])
    assert {c["check"]: c["result"] for c in report["checks"]}["copy_provenance"] == "fail"


def test_policy_fails_closed():
    ok = {"overall": "pass"}
    r = evaluate(validation_report=None, semantic_review_state=None,
                 effective_distribution_decision=None, suppression_denied=False,
                 operation="publish_public", evaluated_at=AT)
    assert r["decision"] == "deny"
    assert "rights_state_missing_fails_closed" in r["reasons"]
    r = evaluate(validation_report=ok, semantic_review_state="model_only",
                 effective_distribution_decision="cleared_public",
                 suppression_denied=False, operation="publish_public",
                 evaluated_at=AT, boundary_version="1.0.0")
    assert r["decision"] == "human_review"
    r = evaluate(validation_report=ok, semantic_review_state="human_approved",
                 effective_distribution_decision="internal_only",
                 suppression_denied=False, operation="publish_public",
                 evaluated_at=AT, boundary_version="1.0.0")
    assert r["decision"] == "deny"
    r = evaluate(validation_report=ok, semantic_review_state="human_approved",
                 effective_distribution_decision="cleared_public",
                 suppression_denied=True, operation="publish_public",
                 evaluated_at=AT, boundary_version="1.0.0")
    assert r["decision"] == "deny"
    r = evaluate(validation_report=ok, semantic_review_state="human_approved",
                 effective_distribution_decision="cleared_public",
                 suppression_denied=False, operation="publish_public",
                 evaluated_at=AT, boundary_version="1.0.0")
    assert r["decision"] == "allow"
