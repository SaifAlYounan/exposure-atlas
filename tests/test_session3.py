"""G1 session 3 tests: DOM-005 revisions/lifecycle, DOM-006 detail/
citation projections + citation check, SRC-001 adapter conformance,
REL-001A snapshot purity, DOC-003 language exclusion."""
import pathlib

import pytest

from atlas.adapters import FixtureAdapter, load_registry, run_conformance
from atlas.kernel import Kernel, UnsupportedLanguageError
from atlas.projections import (build_citation_bundle, build_record_detail,
                               citation_check)
from atlas.revisions import (append_lifecycle_event, derive_state,
                             make_facts_revision, make_record_revision)
from atlas.snapshot import build_snapshot
from atlas.states import TransitionError

ROOT = pathlib.Path(__file__).resolve().parent.parent
AT = "2026-08-31T12:00:00Z"
FIX = ROOT / "tests" / "fixtures" / "documents"


# ---- DOM-005 --------------------------------------------------------
def test_revision_manifests_and_lifecycle():
    fr = make_facts_revision("rec_abcdef123456",
                             ["ast_bbbbbbbbbbbb", "ast_aaaaaaaaaaaa",
                              "ast_aaaaaaaaaaaa"], AT)
    assert fr["assertion_ids"] == ["ast_aaaaaaaaaaaa", "ast_bbbbbbbbbbbb"]
    rr = make_record_revision("rec_abcdef123456", fr["facts_revision_id"],
                              boundary_version="1.0.0", at=AT)
    events: list[dict] = []
    append_lifecycle_event(events, rr["record_revision_id"], "in_review",
                           at=AT, actor="builder")
    append_lifecycle_event(events, rr["record_revision_id"], "approved",
                           at=AT, actor="operator:Alexios")
    with pytest.raises(ValueError, match="release_id required"):
        append_lifecycle_event(events, rr["record_revision_id"], "published",
                               at=AT, actor="release_bot")
    append_lifecycle_event(events, rr["record_revision_id"], "published",
                           at=AT, actor="release_bot",
                           release_id="rel_abcdef123456")
    assert derive_state(events, rr["record_revision_id"]) == "published"
    # no direct draft -> published
    with pytest.raises(TransitionError):
        append_lifecycle_event([], "rrv_abcdef123499", "published",
                               at=AT, actor="x")
    # classification-only change reuses the facts revision
    rr2 = make_record_revision("rec_abcdef123456", fr["facts_revision_id"],
                               boundary_version="1.0.0", at=AT,
                               classification_revision_id="cls_abcdef123456",
                               parent_revision_id=rr["record_revision_id"])
    assert rr2["facts_revision_id"] == rr["facts_revision_id"]


# ---- DOM-006 --------------------------------------------------------
APPROVED = {"predicate": "remedy.amount.statement", "raw_value": "shall pay",
            "normalized_value": None, "procedural_modality": "order",
            "value_origin": "source_quote",
            "semantic_review_state": "human_approved",
            "reviewer_note": "INTERNAL_CANARY"}


def test_record_detail_separates_facts_and_classification():
    detail = build_record_detail(
        release_id="rel_abcdef123456",
        record={"record_id": "rec_abcdef123456",
                "record_revision_id": "rrv_abcdef123456"},
        approved_assertions=[APPROVED],
        classification={"taxonomy_version": "1.0.0", "assignments": [
            {"labels": ["deceptive_practices"], "review_state": "human_approved"},
            {"labels": ["x"], "review_state": "unreviewed"}]},
        boundary_version="1.0.0")
    assert "reviewer_note" not in str(detail)
    assert detail["facts"]["assertions"][0]["procedural_modality"] == "order"
    assert len(detail["classification"]["assignments"]) == 1  # unreviewed dropped
    with pytest.raises(ValueError):
        build_record_detail(release_id="rel_abcdef123456",
                            record={"record_id": "rec_abcdef123456",
                                    "record_revision_id": "rrv_abcdef123456"},
                            approved_assertions=[dict(APPROVED,
                                semantic_review_state="model_only")],
                            classification=None, boundary_version="1.0.0")


def test_citation_bundle():
    b = build_citation_bundle(
        release_id="rel_abcdef123456", record_revision_id="rrv_abcdef123456",
        source_document={"issuer": "US FTC", "title": "Order", "docket": "C-1"},
        source_version={"copy_provenance_state": "digest_crossmatched",
                        "content_sha256": "ab" * 32},
        anchor={"page_label": "3"}, official_url="https://www.ftc.gov/x",
        verification_date="2026-08-31", warnings=["ocr_supported"])
    assert b["custodian_status"] == "mirror_corroborated"
    assert b["pinpoint"] == "page 3"


def test_citation_check_semantics():
    dec = {"decision_id": "bnd_abcdef123456", "outcome": "exclude",
           "boundary_version": "1.0.0", "decided_at": AT}
    kw = dict(release_id="rel_abcdef123456",
              matches={"key-match": "rec_abcdef123456"},
              boundary_decisions={"key-oos": dec},
              pending_keys={"key-pending"})
    assert citation_check(normalized_key="key-match", **kw)["status"] == "matched"
    oos = citation_check(normalized_key="key-oos", **kw)
    assert oos["status"] == "confirmed_out_of_scope"
    assert oos["boundary_decision_id"] == "bnd_abcdef123456"
    # absence NEVER becomes out-of-scope; pending never leaks
    assert citation_check(normalized_key="key-unknown", **kw)[
        "status"] == "not_found_in_atlas"
    assert citation_check(normalized_key="key-pending", **kw)[
        "status"] == "not_found_in_atlas"
    assert citation_check(normalized_key="key-pending",
                          audience_may_see_candidates=True, **kw)[
        "status"] == "candidate_pending"
    # an include decision can never produce confirmed_out_of_scope
    with pytest.raises(ValueError):
        citation_check(release_id="rel_abcdef123456", normalized_key="k",
                       matches={},
                       boundary_decisions={"k": dict(dec, outcome="include")})


# ---- SRC-001 --------------------------------------------------------
def _adapter():
    registry = load_registry(ROOT / "config" / "sources")
    leads = [{"lead_id": f"L{i}", "url": "https://www.ftc.gov/synthetic",
              "fixture_path": str(FIX / "ftc_order_fixture.html")}
             for i in range(5)]
    return FixtureAdapter(registry["ftc_enforcement"], leads)


def test_registry_validates_and_adapter_conforms():
    registry = load_registry(ROOT / "config" / "sources")
    assert {"courtlistener_recap", "ftc_enforcement"} <= set(registry)
    failures = run_conformance(_adapter())
    assert failures == []


def test_adapter_cannot_reach_unregistered_host():
    a = _adapter()
    with pytest.raises(Exception):
        a.fetch({"lead_id": "x", "url": "https://evil.example/y",
                 "fixture_path": "/dev/null"})


# ---- REL-001A -------------------------------------------------------
def test_snapshot_is_pure_and_release_uses_only_it(tmp_path):
    from atlas.release import build_release
    snap = build_snapshot(record_revision_ids=["rrv_abcdef123456"],
                          policy_versions={"publication_policy": "1.0.0"},
                          suppression_overlay_id="sup_abcdef123456", at=AT)
    m = build_release(release_id="rel_abcdef123456", snapshot=snap,
                      records=[], build_timestamp=AT, commit="x",
                      out_dir=tmp_path / "r")
    assert m["snapshot_id"] == snap["snapshot_id"]
    assert m["policy_versions"] == snap["policy_versions"]


# ---- DOC-003 --------------------------------------------------------
def test_unsupported_language_routes_to_awaiting_capability(tmp_path):
    k = Kernel(tmp_path, ["www.ftc.gov"])
    with pytest.raises(UnsupportedLanguageError):
        k.ingest_fixture(FIX / "ftc_order_fixture.html",
                         declared_url="https://www.ftc.gov/fr-fixture",
                         declared_mime="text/html", issuer="CNIL",
                         title="Décision (synthetic)",
                         document_role="regulator_decision",
                         source_id="ftc_enforcement",
                         copy_provenance_state="issuer_direct",
                         retrieved_at=AT, language="fr")
