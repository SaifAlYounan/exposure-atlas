"""Facts/record revision manifests and derived lifecycle (DOM-005).

FactsRevision is an immutable manifest of accepted assertion IDs, not a
second mutable copy of the domain. Displayed workflow state is derived
from append-only lifecycle events; publication is release inclusion.
"""
import secrets

from .schemas import validate
from .states import transition


def _oid(prefix):
    return f"{prefix}_{secrets.token_hex(6)}"


def make_facts_revision(record_id: str, assertion_ids: list[str], at: str) -> dict:
    fr = {"schema_version": "atlas-facts-revision/v1",
          "facts_revision_id": _oid("fct"), "record_id": record_id,
          "assertion_ids": sorted(set(assertion_ids)), "created_at": at}
    validate("facts-revision.schema.json", fr)
    return fr


def make_record_revision(record_id: str, facts_revision_id: str, *,
                         boundary_version: str, at: str,
                         classification_revision_id: str | None = None,
                         parent_revision_id: str | None = None) -> dict:
    rr = {"schema_version": "atlas-record-revision/v1",
          "record_revision_id": _oid("rrv"), "record_id": record_id,
          "facts_revision_id": facts_revision_id,
          "classification_revision_id": classification_revision_id,
          "boundary_version": boundary_version,
          "parent_revision_id": parent_revision_id, "created_at": at}
    validate("record-revision-manifest.schema.json", rr)
    return rr


def append_lifecycle_event(events: list[dict], record_revision_id: str,
                           to_state: str, *, at: str, actor: str,
                           release_id: str | None = None) -> dict:
    current = derive_state(events, record_revision_id)
    transition("revision", current, to_state)
    if to_state == "published" and release_id is None:
        raise ValueError("publication is release inclusion: release_id required")
    ev = {"schema_version": "atlas-revision-lifecycle/v1",
          "event_id": _oid("rle"), "record_revision_id": record_revision_id,
          "from_state": current, "to_state": to_state, "at": at,
          "actor": actor, "release_id": release_id}
    validate("revision-lifecycle-event.schema.json", ev)
    events.append(ev)
    return ev


def derive_state(events: list[dict], record_revision_id: str) -> str:
    state = "draft"
    for ev in events:
        if ev["record_revision_id"] == record_revision_id:
            state = ev["to_state"]
    return state
