"""Exact identity resolution (ID-001).

Resolves matters first by authoritative identifiers, docket/entry ids and
neutral citations; artifact hashes identify *documents*, not matters. Design
guarantees (SPEC §9 ID-001 acceptance):

- **Idempotent exact match** — the same identifier always resolves to the
  same ``record_id``; re-resolving never creates a duplicate.
- **No destructive merge** — when two identifiers that already belong to
  different records appear together (an appeal or consolidation), resolution
  raises ``IdentityConflict``; the caller records a typed, reversible
  ``RecordRelationship`` (appeal_of / consolidated_with) instead of merging.
- **A shared source document does not unify matters** — an artifact hash is a
  document-level signal only; the same document appearing under two matters
  keeps them distinct records.

Pure and deterministic: no network, no credentials, no model calls (A0).
"""
from .canonical import sha256_hex
from .schemas import validate

# Matter-level identifier kinds, in precedence order (strongest first). An
# artifact hash is deliberately NOT here — it identifies a document.
MATTER_ID_KINDS = ("authoritative_id", "docket_id", "neutral_citation")
ARTIFACT_KIND = "artifact_hash"


class IdentityConflict(ValueError):
    """Two matter identifiers already map to different records; resolve with a
    typed relationship, never a destructive merge."""

    def __init__(self, keys, record_ids):
        self.keys = keys
        self.record_ids = sorted(record_ids)
        super().__init__(f"identifiers span multiple records {self.record_ids}; "
                         "create a typed relationship, do not merge")


def normalize_identifier(kind: str, value: str) -> str:
    """Canonical, comparison-stable form of an identifier value."""
    v = " ".join(value.strip().split())
    if kind == ARTIFACT_KIND:
        v = v.lower().replace(" ", "")
        if len(v) != 64 or any(c not in "0123456789abcdef" for c in v):
            raise ValueError(f"artifact_hash must be a 64-hex sha256, got {value!r}")
        return v
    if kind == "neutral_citation":
        return v.upper().replace(" ", "")
    if kind == "docket_id":
        return v.lower()
    if kind == "authoritative_id":
        return v.lower()
    raise ValueError(f"unknown identifier kind {kind!r}")


def identity_key(kind: str, value: str) -> str:
    return f"{kind}:{normalize_identifier(kind, value)}"


def _new_record_id(matter_keys: list[str]) -> str:
    # Deterministic and order-independent: pick the highest-precedence kind
    # present, then the lexicographically smallest key of that kind.
    for kind in MATTER_ID_KINDS:
        of_kind = sorted(k for k in matter_keys if k.startswith(kind + ":"))
        if of_kind:
            return "rec_" + sha256_hex(of_kind[0].encode())[:12]
    raise ValueError("no matter-level identifier to derive a record id from")


class IdentityResolver:
    """In-memory exact-identity index (DOM-002 tables persist it when wired)."""

    def __init__(self):
        self._by_key: dict[str, str] = {}          # matter identity_key -> record_id
        self._aliases: dict[str, set[str]] = {}    # record_id -> matter keys
        self._doc_index: dict[str, set[str]] = {}  # artifact_hash -> record_ids

    def resolve(self, identifiers: list[dict]) -> tuple[str, bool]:
        """Return (record_id, is_new) for a matter described by identifiers.

        ``identifiers`` is a list of {"kind", "value"}. Matter-level kinds
        establish identity; artifact hashes are indexed as document links and
        never by themselves establish or merge a matter.
        """
        matter_keys = [identity_key(i["kind"], i["value"])
                       for i in identifiers if i["kind"] in MATTER_ID_KINDS]
        if not matter_keys:
            raise ValueError("at least one matter-level identifier is required "
                             "(artifact_hash alone cannot establish a matter)")
        existing = {self._by_key[k] for k in matter_keys if k in self._by_key}
        if len(existing) > 1:
            raise IdentityConflict(matter_keys, existing)
        record_id = existing.pop() if existing else _new_record_id(matter_keys)
        is_new = not self._aliases.get(record_id)
        bucket = self._aliases.setdefault(record_id, set())
        for k in matter_keys:
            self._by_key[k] = record_id
            bucket.add(k)
        # Index any artifact hashes as document links (never identity).
        for i in identifiers:
            if i["kind"] == ARTIFACT_KIND:
                h = normalize_identifier(ARTIFACT_KIND, i["value"])
                self._doc_index.setdefault(h, set()).add(record_id)
        return record_id, is_new

    def link_document(self, record_id: str, artifact_hash: str) -> None:
        h = normalize_identifier(ARTIFACT_KIND, artifact_hash)
        self._doc_index.setdefault(h, set()).add(record_id)

    def matters_sharing_document(self, artifact_hash: str) -> set[str]:
        """Records that contain a given document. More than one is normal (a
        shared exhibit) and does NOT imply the matters are the same."""
        return set(self._doc_index.get(normalize_identifier(ARTIFACT_KIND, artifact_hash), set()))

    def aliases(self, record_id: str) -> list[str]:
        return sorted(self._aliases.get(record_id, set()))

    def build_identity(self, record_id: str) -> dict:
        doc = {"schema_version": "atlas-record-identity/v1",
               "record_id": record_id, "aliases": self.aliases(record_id)}
        validate("record-identity.schema.json", doc)
        return doc


def make_relationship(kind: str, from_record_id: str, to_record_id: str,
                      decided_by: str, decided_at: str, reason: str | None = None) -> dict:
    """Build a schema-valid, reversible RecordRelationship (typed link, never a
    destructive merge). Used for appeals, consolidations, corrections, etc."""
    rln = {
        "schema_version": "atlas-record-relationship/v1",
        "relationship_id": "rln_" + sha256_hex(
            f"{kind}\n{from_record_id}\n{to_record_id}".encode())[:12],
        "kind": kind,
        "from_record_id": from_record_id,
        "to_record_id": to_record_id,
        "decided_by": decided_by,
        "decided_at": decided_at,
        "reversible": True,
    }
    if reason is not None:
        rln["reason"] = reason
    validate("record-relationship.schema.json", rln)
    return rln
