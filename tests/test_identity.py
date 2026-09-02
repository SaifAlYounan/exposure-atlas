"""ID-001 — exact identity resolution.

Covers SPEC §9 acceptance:
- exact matches are idempotent;
- appeals and consolidations create typed links, never destructive merges;
- a source-document duplicate does not imply two matters are identical.
Deterministic; no network, credentials or model calls.
"""
import pytest

from atlas import identity
from atlas.schemas import validate

H1 = "a" * 64
H2 = "b" * 64


def test_exact_match_is_idempotent():
    r = identity.IdentityResolver()
    rid1, new1 = r.resolve([{"kind": "docket_id", "value": "US-DC-SDNY 1:23-cv-4567"}])
    assert new1 is True
    rid2, new2 = r.resolve([{"kind": "docket_id", "value": "us-dc-sdny 1:23-cv-4567"}])
    assert rid2 == rid1 and new2 is False  # normalized, same record, no duplicate


def test_record_id_is_deterministic_and_order_independent():
    a = identity.IdentityResolver()
    b = identity.IdentityResolver()
    ids = [{"kind": "neutral_citation", "value": "2024 US 12"},
           {"kind": "authoritative_id", "value": "FTC-C-4999"}]
    ra, _ = a.resolve(ids)
    rb, _ = b.resolve(list(reversed(ids)))
    assert ra == rb  # highest-precedence (authoritative_id) drives the id, order-free


def test_new_alias_attaches_without_changing_record_id():
    r = identity.IdentityResolver()
    rid, _ = r.resolve([{"kind": "docket_id", "value": "court-x 99"}])
    # a later-discovered authoritative id for the same matter attaches as alias
    rid2, new2 = r.resolve([{"kind": "docket_id", "value": "court-x 99"},
                            {"kind": "authoritative_id", "value": "AUTH-1"}])
    assert rid2 == rid and new2 is False
    aliases = r.aliases(rid)
    assert "docket_id:court-x 99" in aliases and "authoritative_id:auth-1" in aliases


def test_artifact_hash_alone_cannot_establish_a_matter():
    r = identity.IdentityResolver()
    with pytest.raises(ValueError):
        r.resolve([{"kind": "artifact_hash", "value": H1}])


def test_shared_document_does_not_merge_matters():
    r = identity.IdentityResolver()
    m1, _ = r.resolve([{"kind": "docket_id", "value": "case-1"},
                       {"kind": "artifact_hash", "value": H1}])
    m2, _ = r.resolve([{"kind": "docket_id", "value": "case-2"},
                       {"kind": "artifact_hash", "value": H1}])  # same exhibit
    assert m1 != m2  # distinct matters despite the shared document
    assert r.matters_sharing_document(H1) == {m1, m2}


def test_conflicting_identifiers_raise_instead_of_merging():
    r = identity.IdentityResolver()
    a, _ = r.resolve([{"kind": "docket_id", "value": "trial-1"}])
    b, _ = r.resolve([{"kind": "docket_id", "value": "appeal-1"}])
    assert a != b
    # a later record carrying BOTH identifiers must NOT merge them
    with pytest.raises(identity.IdentityConflict) as ei:
        r.resolve([{"kind": "docket_id", "value": "trial-1"},
                   {"kind": "docket_id", "value": "appeal-1"}])
    assert set(ei.value.record_ids) == {a, b}


def test_appeal_is_a_typed_reversible_link_not_a_merge():
    r = identity.IdentityResolver()
    trial, _ = r.resolve([{"kind": "docket_id", "value": "trial-1"}])
    appeal, _ = r.resolve([{"kind": "docket_id", "value": "appeal-1"}])
    rln = identity.make_relationship("appeal_of", appeal, trial,
                                     "Alexios", "2026-09-02T12:00:00Z",
                                     reason="direct appeal")
    validate("record-relationship.schema.json", rln)
    assert rln["kind"] == "appeal_of" and rln["reversible"] is True
    # both matters still exist as distinct records
    assert trial != appeal
    # relationship id is stable for the same triple
    assert identity.make_relationship("appeal_of", appeal, trial, "Alexios",
                                      "2026-09-02T12:00:00Z")["relationship_id"] == rln["relationship_id"]


def test_build_identity_validates_and_lists_aliases():
    r = identity.IdentityResolver()
    rid, _ = r.resolve([{"kind": "authoritative_id", "value": "FTC-C-1"},
                        {"kind": "docket_id", "value": "d-1"}])
    ident = r.build_identity(rid)
    validate("record-identity.schema.json", ident)
    assert ident["record_id"] == rid
    assert "authoritative_id:ftc-c-1" in ident["aliases"]


def test_bad_artifact_hash_rejected():
    with pytest.raises(ValueError):
        identity.normalize_identifier("artifact_hash", "not-a-hash")
