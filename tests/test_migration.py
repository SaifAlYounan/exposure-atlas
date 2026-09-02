"""MIG-002 — idempotent importer and ledger.

Covers SPEC §9 acceptance:
- re-running identical input/config creates no new IDs or diffs;
- original payload + hash retrievable internally;
- a secondary-only record stays awaiting-primary/quarantined;
- no legacy_unverified record is citable;
- collision / Unicode-case-normalization / legacy-slug redirect tests pass;
- merges are reversible and never recompute the surviving ID; splits are
  deterministic from legacy id + split-decision + ordinal.
Deterministic; no network, credentials or model calls.
"""
import pytest

from atlas import migration as mig
from atlas.schemas import validate


def test_reimport_identical_is_idempotent():
    imp = mig.MigrationImporter()
    r1 = imp.import_record("LEGACY-1", b"payload-a", "map/v1")
    assert r1["is_new"] is True
    validate("migration-ledger-entry.schema.json", r1["entry"])
    r2 = imp.import_record("LEGACY-1", b"payload-a", "map/v1")
    assert r2["is_new"] is False and r2["changed"] is False
    assert r2["record_id"] == r1["record_id"]
    assert r2["entry"] == r1["entry"]  # no diff


def test_unicode_and_case_normalization_collapse_to_one_id():
    # case + surrounding whitespace + NFC variants map to the same stable id
    assert mig.stable_record_id("Acme Corp") == mig.stable_record_id("  acme   corp ")
    a = mig.stable_record_id("Caf\u00e9")        # NFC: e-acute as one codepoint
    b = mig.stable_record_id("Cafe\u0301")       # NFD: e + combining acute
    assert a == b


def test_legacy_slug_redirect_resolves():
    imp = mig.MigrationImporter()
    r = imp.import_record("matter-42", b"p", "map/v1", slug="Matter 42 (Old Slug)")
    assert imp.resolve_redirect("matter-42") == r["record_id"]
    assert imp.resolve_redirect("matter 42 (old slug)") == r["record_id"]
    with pytest.raises(mig.MigrationError):
        imp.resolve_redirect("nonexistent")


def test_secondary_only_stays_awaiting_primary():
    imp = mig.MigrationImporter()
    r = imp.import_record("sec-1", b"p", "map/v1", secondary_only=True, disposition="mapped")
    assert r["entry"]["disposition"] in mig.SECONDARY_DISPOSITIONS
    r2 = imp.import_record("sec-1", b"p", "map/v1", secondary_only=True, disposition="mapped")
    assert r2["entry"]["disposition"] in mig.SECONDARY_DISPOSITIONS  # stays


def test_no_legacy_unverified_is_citable():
    imp = mig.MigrationImporter()
    imp.import_record("L1", b"p1", "map/v1")
    imp.import_record("L2", b"p2", "map/v1")
    assert imp.citable_entries() == []  # all legacy_unverified -> none citable
    assert mig.is_citable({"verification_migration_state": "legacy_unverified"}) is False


def test_original_payload_retrievable_internally():
    imp = mig.MigrationImporter()
    r = imp.import_record("L1", b"the original bytes", "map/v1")
    assert imp.get_payload(r["record_id"]) == b"the original bytes"
    assert r["entry"]["payload_sha256"] == __import__("hashlib").sha256(b"the original bytes").hexdigest()


def test_merge_is_reversible_and_keeps_surviving_id():
    imp = mig.MigrationImporter()
    a = imp.import_record("A", b"pa", "map/v1")["record_id"]
    b = imp.import_record("B", b"pb", "map/v1")["record_id"]
    out = imp.merge(a, [b], "2026-09-02T12:00:00Z", "operator-approved merge")
    assert out["surviving_record_id"] == a  # never recomputed
    assert out["reversible"] is True
    for rln in out["relationships"]:
        validate("record-relationship.schema.json", rln)
        assert rln["reversible"] is True and rln["kind"] == "consolidated_with"
    # the merged record now redirects to the survivor
    assert imp.resolve_redirect("B") == a


def test_split_ids_are_deterministic():
    ids1 = mig.split_record_ids("L1", "split_dec_1", [0, 1])
    ids2 = mig.split_record_ids("L1", "split_dec_1", [0, 1])
    assert ids1 == ids2 and len(set(ids1)) == 2
    # a different split decision yields different ids
    assert mig.split_record_ids("L1", "split_dec_2", [0]) != mig.split_record_ids("L1", "split_dec_1", [0])
