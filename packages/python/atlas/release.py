"""Deterministic fixture release builder (REL-000 / REL-001 core).

Public artifacts are generated through an EXPLICIT ALLOWLIST projection
(never internal-minus-denylist). Two clean builds with identical
supplied build metadata must be byte-identical; the signing block wraps
the already-compared root hash and is excluded from equality.
"""
import json
import pathlib

from .canonical import canonical_json_bytes, obj_sha256, sha256_hex
from .schemas import validate
from .suppression import TEST_KEY_ID

CANARY_MARKERS = ("INTERNAL_CANARY", "reviewer_note", "internal_url")


def project_record_summary(*, release_id: str, record: dict,
                           assertions: list[dict],
                           source_documents: dict,
                           source_versions: dict,
                           boundary_version: str) -> dict:
    """Allowlist serializer: only the fields written here can ever
    appear, whatever extra keys the inputs carry."""
    facts = []
    for a in assertions:
        if a["semantic_review_state"] != "human_approved":
            raise ValueError("unapproved assertion reached projection")
        sv = source_versions[a["source_version_id"]]
        sd = source_documents[sv["source_document_id"]]
        facts.append({
            "predicate": a["predicate"],
            "raw_value": a["raw_value"],
            "normalized_value": a.get("normalized_value"),
            "procedural_modality": a["procedural_modality"],
            "semantic_review_state": "human_approved",
            "source_citation": {"issuer": sd["issuer"], "title": sd["title"],
                                "docket": sd.get("docket"),
                                "content_sha256": sv["content_sha256"]},
        })
    out = {"schema_version": "atlas-record-summary/v1",
           "projection_version": "V1",
           "release_id": release_id,
           "record_id": record["record_id"],
           "record_revision_id": record["record_revision_id"],
           "boundary_version": boundary_version,
           "facts": facts,
           "notices": {"no_match_is_not_absence": True,
                       "not_legal_advice": True}}
    validate("record-summary-v1.schema.json", out)
    return out


def build_release(*, release_id: str, snapshot: dict, records: list[dict],
                  build_timestamp: str, commit: str,
                  out_dir: pathlib.Path,
                  prior_release_id: str | None = None) -> dict:
    out_dir = pathlib.Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    artifact_hashes = {}
    for rec in sorted(records, key=lambda r: r["record_id"]):
        rel_path = f"records/{rec['record_id']}.json"
        data = canonical_json_bytes(rec)
        _canary_scan(data)
        p = out_dir / rel_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        artifact_hashes[rel_path] = sha256_hex(data)
    root = obj_sha256(artifact_hashes)
    manifest = {"schema_version": "atlas-release-manifest/v1",
                "release_id": release_id,
                "snapshot_id": snapshot["snapshot_id"],
                "prior_release_id": prior_release_id,
                "created_from_commit": commit,
                "artifact_hashes": artifact_hashes,
                "root_hash": root,
                "policy_versions": snapshot["policy_versions"],
                "build_meta": {"build_timestamp": build_timestamp,
                               "builder": "atlas-release-builder/0.1"},
                "signing": {"scheme": "test_key_sha256",
                            "key_id": TEST_KEY_ID,
                            "payload_sha256": root}}
    validate("release-manifest.schema.json", manifest)
    (out_dir / "release-manifest.json").write_bytes(canonical_json_bytes(manifest))
    return manifest


def _canary_scan(data: bytes) -> None:
    text = data.decode("utf-8", "replace")
    for marker in CANARY_MARKERS:
        if marker in text:
            raise RuntimeError(f"private canary {marker!r} in public artifact; build fails")


def verify_release(out_dir: pathlib.Path) -> dict:
    out_dir = pathlib.Path(out_dir)
    manifest = json.loads((out_dir / "release-manifest.json").read_text())
    validate("release-manifest.schema.json", manifest)
    for rel_path, digest in manifest["artifact_hashes"].items():
        data = (out_dir / rel_path).read_bytes()
        if sha256_hex(data) != digest:
            raise RuntimeError(f"artifact hash mismatch: {rel_path}")
    if obj_sha256(manifest["artifact_hashes"]) != manifest["root_hash"]:
        raise RuntimeError("root hash mismatch")
    return manifest
