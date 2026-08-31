"""REL-000/API-000/COR-000 tests: determinism, tamper, canary,
suppression precedence."""
import json
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

from atlas.readpath import serve_record
from atlas.release import build_release, project_record_summary, verify_release
from atlas.suppression import make_overlay

AT = "2026-08-31T12:00:00Z"
SNAP = {"snapshot_id": "snp_abcdef123456",
        "policy_versions": {"publication_policy": "1.0.0",
                            "boundary": "1.0.0"}}
SDOC = {"source_document_id": "sdoc_abcdef123456",
        "issuer": "US Federal Trade Commission",
        "title": "In the Matter of Acme (synthetic)", "docket": "C-0000"}
SVER = {"source_version_id": "sver_abcdef123456",
        "source_document_id": "sdoc_abcdef123456", "content_sha256": "ab" * 32}
ASSERTION = {"predicate": "remedy.amount.statement",
             "raw_value": "shall pay $5,000,000",
             "normalized_value": {"decimal": "5000000.00", "currency": "USD",
                                  "amount_type": "penalty"},
             "procedural_modality": "order",
             "semantic_review_state": "human_approved",
             "source_version_id": "sver_abcdef123456",
             "reviewer_note": "INTERNAL_CANARY should never leak"}
RECORD_IDS = {"record_id": "rec_abcdef123456",
              "record_revision_id": "rrv_abcdef123456"}


def _records():
    rec = project_record_summary(
        release_id="rel_abcdef123456", record=RECORD_IDS,
        assertions=[ASSERTION], source_documents={"sdoc_abcdef123456": SDOC},
        source_versions={"sver_abcdef123456": SVER}, boundary_version="1.0.0")
    return [rec]


def _build(out):
    return build_release(release_id="rel_abcdef123456", snapshot=SNAP,
                         records=_records(), build_timestamp=AT,
                         commit="deadbeef", out_dir=out)


def test_release_determinism(tmp_path):
    m1 = _build(tmp_path / "b1")
    m2 = _build(tmp_path / "b2")
    assert m1["root_hash"] == m2["root_hash"]
    assert m1["artifact_hashes"] == m2["artifact_hashes"]
    b1 = (tmp_path / "b1" / "records" / "rec_abcdef123456.json").read_bytes()
    b2 = (tmp_path / "b2" / "records" / "rec_abcdef123456.json").read_bytes()
    assert b1 == b2


def test_allowlist_projection_drops_internal_fields(tmp_path):
    _build(tmp_path / "b")
    body = json.loads((tmp_path / "b" / "records" / "rec_abcdef123456.json").read_text())
    assert "reviewer_note" not in json.dumps(body)
    assert body["facts"][0]["source_citation"]["issuer"] == SDOC["issuer"]


def test_unapproved_assertion_cannot_project():
    bad = dict(ASSERTION, semantic_review_state="model_only")
    with pytest.raises(ValueError):
        project_record_summary(release_id="rel_abcdef123456", record=RECORD_IDS,
                               assertions=[bad],
                               source_documents={"sdoc_abcdef123456": SDOC},
                               source_versions={"sver_abcdef123456": SVER},
                               boundary_version="1.0.0")


def test_canary_in_public_bytes_fails_build(tmp_path):
    rec = _records()[0]
    rec = dict(rec, record_id="rec_abcdef123456")
    rec["facts"][0]["raw_value"] = "INTERNAL_CANARY leaked"
    with pytest.raises(RuntimeError):
        build_release(release_id="rel_abcdef123456", snapshot=SNAP,
                      records=[rec], build_timestamp=AT, commit="deadbeef",
                      out_dir=tmp_path / "b")


def test_tampered_artifact_fails_verification(tmp_path):
    _build(tmp_path / "b")
    p = tmp_path / "b" / "records" / "rec_abcdef123456.json"
    p.write_bytes(p.read_bytes().replace(b"5,000,000", b"5,000,001"))
    with pytest.raises(RuntimeError):
        verify_release(tmp_path / "b")


def test_suppression_outranks_release_and_absence_semantics(tmp_path):
    _build(tmp_path / "b")
    overlay = make_overlay("sup_abcdef123456", AT,
                           {"rec_abcdef123456": "sealing order (fixture)"})
    resp = serve_record(tmp_path / "b", "rec_abcdef123456", overlay)
    assert resp["status"] == "suppressed" and "tombstone" in resp
    empty = make_overlay("sup_abcdef123457", AT, {})
    resp = serve_record(tmp_path / "b", "rec_abcdef123456", empty)
    assert resp["status"] == "ok"
    assert resp["record"]["facts"][0]["procedural_modality"] == "order"
    resp = serve_record(tmp_path / "b", "rec_000000000000", empty)
    assert resp["status"] == "not_found_in_atlas"
    assert resp["no_match_is_not_absence"] is True


def test_tampered_overlay_rejected(tmp_path):
    _build(tmp_path / "b")
    overlay = make_overlay("sup_abcdef123456", AT, {})
    overlay["denied_record_ids"] = ["rec_abcdef123456"]  # tamper
    with pytest.raises(RuntimeError):
        serve_record(tmp_path / "b", "rec_abcdef123456", overlay)
