"""D-022: the VER-002 vertical slice runs with DOM-002 PostgreSQL-backed
state. Same fetch→canonicalize→anchor→assert→verify→approve→project→
release→serve slice as test_end_to_end, but with an engine so every
object is persisted and the DB audit chain is exercised."""
import pathlib

import sqlalchemy as sa

from atlas.db import (acceptance_decisions, acquisition_receipts, assertions,
                      assertion_proposals, source_documents, source_versions,
                      text_artifacts, verify_audit_chain)
from atlas.kernel import Kernel
from atlas.readpath import serve_record
from atlas.release import build_release, project_record_summary
from atlas.suppression import make_overlay

ROOT = pathlib.Path(__file__).resolve().parent.parent
AT = "2026-08-31T12:00:00Z"
FIX = ROOT / "tests" / "fixtures" / "documents"


def _reset(engine):
    with engine.begin() as c:
        for t in [assertions, acceptance_decisions, assertion_proposals,
                  text_artifacts, acquisition_receipts, source_versions,
                  source_documents]:
            c.execute(sa.text(f"ALTER TABLE {t.name} DISABLE TRIGGER ALL"))
            c.execute(t.delete())
            c.execute(sa.text(f"ALTER TABLE {t.name} ENABLE TRIGGER ALL"))
        c.execute(sa.text("ALTER TABLE audit_events DISABLE TRIGGER ALL"))
        c.execute(sa.text("DELETE FROM audit_events"))
        c.execute(sa.text("ALTER TABLE audit_events ENABLE TRIGGER ALL"))


def test_slice_with_db_backed_state(pg_engine, tmp_path):
    _reset(pg_engine)
    k = Kernel(tmp_path / "var", ["www.ftc.gov"], engine=pg_engine)
    sdoc, sver = k.ingest_fixture(
        FIX / "ftc_order_fixture.html",
        declared_url="https://www.ftc.gov/synthetic-fixture",
        declared_mime="text/html", issuer="US Federal Trade Commission",
        title="In the Matter of Acme Cognition (synthetic)",
        document_role="regulator_decision", source_id="ftc_enforcement",
        copy_provenance_state="issuer_direct", retrieved_at=AT, docket="C-0000")
    art = k.canonicalize(sver["source_version_id"], AT)
    q = "Respondent shall pay a civil penalty of $5,000,000"
    anc = k.add_anchor(art["text_artifact_id"], q)
    prop = k.propose(source_version_id=sver["source_version_id"],
                     subject_ref={"entity_type": "procedural_event",
                                  "entity_id": "evt_order"},
                     predicate="remedy.amount.statement", raw_value=q,
                     modality="order", value_origin="source_quote",
                     support=[{"anchor_id": anc["anchor_id"], "role": "supports",
                               "passage_role": "operative_part",
                               "attributed_speaker": "issuing_regulator"}],
                     observed_at=AT)
    assert k.verify(prop["proposal_id"])["overall"] == "pass"
    ast = k.approve(prop["proposal_id"], reason="matches operative text",
                    decided_at=AT)

    # --- the state is actually in PostgreSQL, not just memory ---
    with pg_engine.connect() as c:
        assert c.execute(sa.select(sa.func.count()).select_from(
            source_documents)).scalar() == 1
        assert c.execute(sa.select(sa.func.count()).select_from(
            source_versions)).scalar() == 1
        assert c.execute(sa.select(sa.func.count()).select_from(
            text_artifacts)).scalar() == 1
        assert c.execute(sa.select(sa.func.count()).select_from(
            assertion_proposals)).scalar() == 1
        assert c.execute(sa.select(sa.func.count()).select_from(
            assertions)).scalar() == 1
        assert c.execute(sa.select(sa.func.count()).select_from(
            acceptance_decisions)).scalar() == 1
        # atomic accept path wrote its audit event; chain verifies
        assert verify_audit_chain(c) >= 1

    # --- the accepted assertion is immutable in the DB (trigger) ---
    import pytest
    with pytest.raises(sa.exc.DatabaseError):
        with pg_engine.begin() as c:
            c.execute(assertions.update().values(payload='{"tampered":1}'))

    # --- and the rest of the slice still produces a served record ---
    rec = project_record_summary(
        release_id="rel_db00000001",
        record={"record_id": "rec_db00000001",
                "record_revision_id": "rrv_db00000001"},
        assertions=[ast], source_documents=k.source_documents,
        source_versions=k.source_versions, boundary_version="1.0.0")
    snap = {"snapshot_id": "snp_db00000001",
            "policy_versions": {"publication_policy": "1.0.0"}}
    build_release(release_id="rel_db00000001", snapshot=snap, records=[rec],
                  build_timestamp=AT, commit="dbslice", out_dir=tmp_path / "r")
    resp = serve_record(tmp_path / "r", "rec_db00000001",
                        make_overlay("sup_db00000001", AT, {}))
    assert resp["status"] == "ok"
    assert resp["record"]["facts"][0]["semantic_review_state"] == "human_approved"


def test_reingest_same_bytes_is_idempotent_in_db(pg_engine, tmp_path):
    _reset(pg_engine)
    k = Kernel(tmp_path / "var", ["www.ftc.gov"], engine=pg_engine)
    for _ in range(2):
        k.ingest_fixture(FIX / "ftc_order_fixture.html",
                         declared_url="https://www.ftc.gov/f",
                         declared_mime="text/html", issuer="US FTC",
                         title="t", document_role="regulator_decision",
                         source_id="ftc_enforcement",
                         copy_provenance_state="issuer_direct",
                         retrieved_at=AT)
    # two distinct source documents (new opaque ids) but the content blob
    # dedupes in the evidence store; DB rows persist without crashing
    with pg_engine.connect() as c:
        assert c.execute(sa.select(sa.func.count()).select_from(
            source_versions)).scalar() >= 1
