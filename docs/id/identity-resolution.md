# Exact identity resolution (ID-001)

Resolves matters by **matter-level** identifiers first — authoritative ids,
docket/entry ids and neutral citations — and treats **artifact hashes** as a
document-level signal only. Engine:
`packages/python/atlas/identity.py`; identity and relationship objects use the
existing `record-identity` and `record-relationship` schemas.

Pure, deterministic, A0: no network, credentials, or model calls. Fuzzy
matching (ID-002) is separate and never auto-merges.

## Precedence

`authoritative_id` > `docket_id` > `neutral_citation`. A new `record_id` is
derived from the highest-precedence identifier present (then lexicographically
smallest), so it is **order-independent and stable**. Additional identifiers
for the same matter attach as **aliases** without changing the id.

`artifact_hash` is **not** a matter identifier — it identifies a *document*.

## Guarantees (SPEC §9 ID-001 acceptance)

- **Idempotent exact match** — the same identifier always resolves to the same
  `record_id`; re-resolving returns `is_new=False` and never duplicates
  (`test_exact_match_is_idempotent`, `test_new_alias_attaches_without_changing_record_id`).
- **Appeals/consolidations are typed links, not merges** — when identifiers
  that already belong to *different* records appear together, `resolve` raises
  `IdentityConflict`; the caller records a reversible `RecordRelationship`
  (`appeal_of`, `consolidated_with`, …) instead of destroying either record
  (`test_conflicting_identifiers_raise_instead_of_merging`,
  `test_appeal_is_a_typed_reversible_link_not_a_merge`).
- **A shared source document does not unify matters** — the same
  `artifact_hash` under two matters keeps them distinct; `matters_sharing_document`
  reports the overlap for review, but no merge occurs
  (`test_shared_document_does_not_merge_matters`).

## Not settled here

- ID-002 (fuzzy proposals) — normalized names/forum/dates/titles propose
  possible duplicates/relations, always into review, never auto-merge.
- The operator decides every relationship (`decided_by: Alexios`,
  `reversible: true`); this module only builds the schema-valid objects.
