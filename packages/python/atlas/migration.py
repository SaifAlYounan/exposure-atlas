"""Idempotent importer and migration ledger (MIG-002).

Imports legacy records into stable IDs and records every import in the
migration ledger (SPEC §9 MIG-002). Guarantees:

- a stable record ID is derived from a fixed namespace + the (normalized)
  legacy ID; re-running identical input/config creates no new IDs or diffs;
- a merge selects a surviving stable ID and records aliases/redirects + a
  reversible merge decision — it never recomputes an ID from a mutable
  legacy-ID set; a split derives new IDs from the legacy ID + an immutable
  split-decision ID/ordinal;
- the original payload and its hash stay retrievable internally;
- every entry is `verification_migration_state: legacy_unverified` and is
  therefore never citable (excluded from REST/MCP/search);
- a secondary-only record stays awaiting-primary/quarantined;
- Unicode/case-normalization and legacy-slug redirects resolve consistently.

Pure and deterministic; no network, credentials or model calls (A0).
"""
import unicodedata

from .canonical import sha256_hex
from .identity import make_relationship
from .schemas import validate

# Fixed namespace — the ID derivation must never change for a given legacy ID.
MIG_NAMESPACE = "atlas-migration/ns/v1"
SECONDARY_DISPOSITIONS = ("awaiting_primary", "quarantined")


class MigrationError(ValueError):
    pass


def normalize_legacy_id(legacy_id: str) -> str:
    """NFC + casefold + whitespace-collapse so case/Unicode variants and slugs
    resolve to one stable identity."""
    s = unicodedata.normalize("NFC", legacy_id).strip().casefold()
    return " ".join(s.split())


def stable_record_id(legacy_id: str) -> str:
    return "rec_" + sha256_hex(f"{MIG_NAMESPACE}\n{normalize_legacy_id(legacy_id)}".encode())[:12]


def split_record_ids(legacy_id: str, split_decision_id: str, ordinals: list[int]) -> list[str]:
    """New IDs from the original legacy ID + the immutable split-decision id +
    ordinal (deterministic; re-splitting yields the same IDs)."""
    norm = normalize_legacy_id(legacy_id)
    return ["rec_" + sha256_hex(
        f"{MIG_NAMESPACE}\n{norm}\n{split_decision_id}\n{o}".encode())[:12] for o in ordinals]


class MigrationImporter:
    """In-memory idempotent importer + ledger."""

    def __init__(self):
        self._entries: dict[str, dict] = {}     # normalized legacy id -> ledger entry
        self._payloads: dict[str, bytes] = {}   # record_id -> original payload
        self._redirects: dict[str, str] = {}    # normalized slug/legacy -> record_id

    def import_record(self, legacy_id: str, payload: bytes, mapping_version: str, *,
                      disposition: str = "mapped", secondary_only: bool = False,
                      warnings: list[str] | None = None,
                      slug: str | None = None) -> dict:
        norm = normalize_legacy_id(legacy_id)
        record_id = stable_record_id(legacy_id)
        if secondary_only and disposition not in SECONDARY_DISPOSITIONS:
            disposition = "awaiting_primary"
        payload_sha = sha256_hex(payload)

        prior = self._entries.get(norm)
        if prior is not None:
            unchanged = (prior["payload_sha256"] == payload_sha
                         and prior["mapping_version"] == mapping_version
                         and prior["disposition"] == disposition)
            if unchanged:
                return {"entry": prior, "record_id": record_id, "is_new": False, "changed": False}

        entry = {
            "schema_version": "atlas-migration-ledger/v1",
            "legacy_id": legacy_id,
            "payload_sha256": payload_sha,
            "mapping_version": mapping_version,
            "target_record_ids": [record_id],
            "disposition": disposition,
            "verification_migration_state": "legacy_unverified",
        }
        if warnings:
            entry["next_action"] = "; ".join(warnings)
        validate("migration-ledger-entry.schema.json", entry)

        self._entries[norm] = entry
        self._payloads[record_id] = payload
        self._redirects[norm] = record_id
        if slug:
            self._redirects[normalize_legacy_id(slug)] = record_id
        return {"entry": entry, "record_id": record_id, "is_new": prior is None,
                "changed": prior is not None}

    def get_payload(self, record_id: str) -> bytes:
        """Original payload remains retrievable internally."""
        if record_id not in self._payloads:
            raise MigrationError(f"no payload for {record_id!r}")
        return self._payloads[record_id]

    def resolve_redirect(self, slug_or_legacy: str) -> str:
        rid = self._redirects.get(normalize_legacy_id(slug_or_legacy))
        if rid is None:
            raise MigrationError(f"no redirect for {slug_or_legacy!r}")
        return rid

    def merge(self, surviving_record_id: str, merged_record_ids: list[str],
              decided_at: str, reason: str) -> dict:
        """Select a surviving stable ID; record reversible merge relationships +
        redirects. Never recomputes the surviving ID."""
        relationships = []
        for mid in merged_record_ids:
            relationships.append(make_relationship(
                "consolidated_with", mid, surviving_record_id, "Alexios", decided_at, reason=reason))
            # redirect the merged record to the survivor
            for key, rid in list(self._redirects.items()):
                if rid == mid:
                    self._redirects[key] = surviving_record_id
        return {"surviving_record_id": surviving_record_id,
                "relationships": relationships, "reversible": True}

    def citable_entries(self) -> list[dict]:
        """No legacy_unverified record is citable — all migration entries are
        excluded from REST/MCP/search."""
        return [e for e in self._entries.values() if is_citable(e)]


def is_citable(entry: dict) -> bool:
    return entry.get("verification_migration_state") != "legacy_unverified"
