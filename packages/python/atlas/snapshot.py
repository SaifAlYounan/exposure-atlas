"""Release input snapshot (REL-001A core): the release builder consumes
only this frozen object, never mutable operational rows."""
import secrets

from .schemas import validate


def build_snapshot(*, record_revision_ids: list[str],
                   policy_versions: dict[str, str],
                   suppression_overlay_id: str, at: str) -> dict:
    snap = {"schema_version": "atlas-release-snapshot/v1",
            "snapshot_id": f"snp_{secrets.token_hex(6)}",
            "created_at": at,
            "record_revision_ids": sorted(record_revision_ids),
            "policy_versions": dict(policy_versions),
            "suppression_overlay_id": suppression_overlay_id}
    validate("release-input-snapshot.schema.json", snap)
    return snap
