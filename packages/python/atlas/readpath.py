"""Minimal fixture read path (API-000).

Serves exactly the signed release artifact bytes, applying the current
suppression overlay BEFORE anything else. No second projection
implementation exists: this reads what the release builder wrote.
"""
import json
import pathlib

from .release import verify_release
from .suppression import is_denied


def serve_record(release_dir: pathlib.Path, record_id: str, overlay: dict) -> dict:
    manifest = verify_release(release_dir)
    if is_denied(overlay, record_id):
        return {"status": "suppressed", "record_id": record_id,
                "release_id": manifest["release_id"],
                "tombstone": "content withheld under the current signed suppression overlay",
                "suppression_overlay_id": overlay["overlay_id"]}
    rel_path = f"records/{record_id}.json"
    if rel_path not in manifest["artifact_hashes"]:
        return {"status": "not_found_in_atlas", "record_id": record_id,
                "release_id": manifest["release_id"],
                "no_match_is_not_absence": True}
    body = json.loads((pathlib.Path(release_dir) / rel_path).read_text())
    return {"status": "ok", "release_id": manifest["release_id"],
            "suppression_overlay_id": overlay["overlay_id"],
            "record": body}
