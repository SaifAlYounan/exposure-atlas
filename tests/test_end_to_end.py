"""G1 vertical slice: one PDF and one HTML fixture pass
fetch -> canonicalize -> assert -> verify -> approve -> project ->
release -> serve, with no AI service (VER-002 acceptance)."""
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent

from atlas.audit import verify_chain
from atlas.kernel import Kernel
from atlas.readpath import serve_record
from atlas.release import build_release, project_record_summary
from atlas.suppression import make_overlay

AT = "2026-08-31T12:00:00Z"
FIX = ROOT / "tests" / "fixtures" / "documents"
HOSTS = ["www.ftc.gov", "www.courtlistener.com"]


def test_full_manual_slice(tmp_path):
    k = Kernel(tmp_path / "var", HOSTS)

    # --- HTML regulator fixture ---
    sdoc_h, sver_h = k.ingest_fixture(
        FIX / "ftc_order_fixture.html",
        declared_url="https://www.ftc.gov/synthetic-fixture",
        declared_mime="text/html", issuer="US Federal Trade Commission",
        title="In the Matter of Acme Cognition (synthetic fixture)",
        document_role="regulator_decision", source_id="ftc_enforcement",
        copy_provenance_state="issuer_direct", retrieved_at=AT, docket="C-0000")
    art_h = k.canonicalize(sver_h["source_version_id"], AT)
    assert b"should never appear" not in k.canonical_texts[art_h["text_artifact_id"]]
    q_h = "Respondent shall pay a civil penalty of $5,000,000"
    anc_h = k.add_anchor(art_h["text_artifact_id"], q_h)
    prop_h = k.propose(source_version_id=sver_h["source_version_id"],
                       subject_ref={"entity_type": "procedural_event",
                                    "entity_id": "evt_order_h"},
                       predicate="remedy.amount.statement", raw_value=q_h,
                       modality="order", value_origin="source_quote",
                       support=[{"anchor_id": anc_h["anchor_id"],
                                 "role": "supports",
                                 "passage_role": "operative_part",
                                 "attributed_speaker": "issuing_regulator"}],
                       observed_at=AT)
    assert k.verify(prop_h["proposal_id"])["overall"] == "pass"
    ast_h = k.approve(prop_h["proposal_id"],
                      reason="operative order text matches quote exactly",
                      decided_at=AT)

    # --- PDF court fixture ---
    sdoc_p, sver_p = k.ingest_fixture(
        FIX / "court_opinion_fixture.pdf",
        declared_url="https://www.courtlistener.com/synthetic-fixture.pdf",
        declared_mime="application/pdf", issuer="US District Court (synthetic)",
        title="Doe v. Acme Cognition (synthetic fixture)",
        document_role="judgment_or_order", source_id="courtlistener_recap",
        copy_provenance_state="digest_crossmatched", retrieved_at=AT,
        docket="1:26-cv-01234")
    art_p = k.canonicalize(sver_p["source_version_id"], AT)
    q_p = "Plaintiffs' motion for class certification is GRANTED."
    anc_p = k.add_anchor(art_p["text_artifact_id"], q_p)
    prop_p = k.propose(source_version_id=sver_p["source_version_id"],
                       subject_ref={"entity_type": "procedural_event",
                                    "entity_id": "evt_cert_p"},
                       predicate="procedural_event.certification",
                       raw_value=q_p, modality="order",
                       value_origin="source_quote",
                       support=[{"anchor_id": anc_p["anchor_id"],
                                 "role": "supports",
                                 "passage_role": "operative_part",
                                 "attributed_speaker": "issuing_court"}],
                       observed_at=AT)
    assert k.verify(prop_p["proposal_id"])["overall"] == "pass"
    ast_p = k.approve(prop_p["proposal_id"],
                      reason="operative order text matches quote exactly",
                      decided_at=AT)

    # --- policy, projection, release ---
    for ast in (ast_h, ast_p):
        pol = k.policy_check(ast["assertion_id"], AT,
                             effective_distribution_decision="cleared_public")
        assert pol["decision"] == "allow"

    recs = []
    for rid, rrv, ast in [("rec_fixture00001", "rrv_fixture00001", ast_h),
                          ("rec_fixture00002", "rrv_fixture00002", ast_p)]:
        recs.append(project_record_summary(
            release_id="rel_fixture00001",
            record={"record_id": rid, "record_revision_id": rrv},
            assertions=[ast], source_documents=k.source_documents,
            source_versions=k.source_versions, boundary_version="1.0.0"))
    snap = {"snapshot_id": "snp_fixture00001",
            "policy_versions": {"publication_policy": "1.0.0",
                                "boundary": "1.0.0",
                                "canonicalizer": "1.0.0",
                                "verifier": "1.0.0"}}
    m1 = build_release(release_id="rel_fixture00001", snapshot=snap,
                       records=recs, build_timestamp=AT, commit="e2e",
                       out_dir=tmp_path / "r1")
    m2 = build_release(release_id="rel_fixture00001", snapshot=snap,
                       records=recs, build_timestamp=AT, commit="e2e",
                       out_dir=tmp_path / "r2")
    assert m1["root_hash"] == m2["root_hash"]

    overlay = make_overlay("sup_fixture00001", AT, {})
    resp = serve_record(tmp_path / "r1", "rec_fixture00001", overlay)
    assert resp["status"] == "ok"
    fact = resp["record"]["facts"][0]
    assert fact["semantic_review_state"] == "human_approved"
    assert fact["source_citation"]["content_sha256"] == sver_h["content_sha256"]

    # complete provenance chain exists for each public proposition
    assert ast_h["acceptance_decision_id"] in k.decisions
    assert k.decisions[ast_h["acceptance_decision_id"]]["decided_by"] == "Alexios"
    verify_chain(k.audit_path)
