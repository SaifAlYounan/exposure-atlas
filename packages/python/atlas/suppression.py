"""Deny-only suppression overlay primitive (COR-000 core).

Test-key signing only (SEC-002-01 real signing is G3 scope): the
"signature" is a keyed payload hash with an explicit test scheme marker
so nothing can mistake it for production signing.
"""
from .canonical import obj_sha256
from .schemas import validate

TEST_KEY_ID = "atlas-test-key-1"


def make_overlay(overlay_id: str, as_of: str, denied: dict[str, str]) -> dict:
    payload = {"overlay_id": overlay_id, "as_of": as_of,
               "denied_record_ids": sorted(denied),
               "denial_reasons": denied}
    overlay = {"schema_version": "atlas-suppression-overlay/v1",
               **payload,
               "signing": {"scheme": "test_key_sha256", "key_id": TEST_KEY_ID,
                           "payload_sha256": obj_sha256(payload)}}
    validate("suppression-overlay.schema.json", overlay)
    return overlay


def verify_overlay(overlay: dict) -> None:
    validate("suppression-overlay.schema.json", overlay)
    payload = {"overlay_id": overlay["overlay_id"], "as_of": overlay["as_of"],
               "denied_record_ids": overlay["denied_record_ids"],
               "denial_reasons": overlay["denial_reasons"]}
    if obj_sha256(payload) != overlay["signing"]["payload_sha256"]:
        raise RuntimeError("suppression overlay integrity check failed")


def is_denied(overlay: dict, record_id: str) -> bool:
    verify_overlay(overlay)
    return record_id in overlay["denied_record_ids"]
