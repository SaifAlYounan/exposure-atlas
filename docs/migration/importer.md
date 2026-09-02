# Idempotent importer and migration ledger (MIG-002)

Imports legacy records into stable IDs and records each import in the
migration ledger (SPEC §9 MIG-002). Engine:
`packages/python/atlas/migration.py`; entries use the existing
`migration-ledger-entry` schema. Pure, deterministic, A0 — no network,
credentials, or model calls.

## Stable IDs

`stable_record_id(legacy_id)` = `rec_` + hash of a **fixed namespace** +
the **normalized** legacy id. Normalization is NFC + casefold +
whitespace-collapse, so case/Unicode variants and legacy slugs resolve to one
identity. Re-running identical input/config yields the same ID and no diff.

- **Merge** (`merge`) selects a surviving stable ID and records
  aliases/redirects plus a **reversible** `RecordRelationship`
  (`consolidated_with`); it never recomputes the surviving ID from a mutable
  legacy-ID set.
- **Split** (`split_record_ids`) derives new IDs from the legacy id + the
  immutable split-decision id + ordinal — deterministic across re-splits.

## Ledger entry & verification state

Each entry stores the original payload hash, mapping version, target IDs,
disposition, and warnings, and is always
`verification_migration_state: legacy_unverified`. Any canonical revision
created from it is independently a draft proposal until accepted.

## Guarantees → SPEC §9 acceptance

- **Idempotent re-import** — identical input/config → no new IDs or diffs
  (`test_reimport_identical_is_idempotent`).
- **Original payload + hash retrievable internally** — `get_payload`
  (`test_original_payload_retrievable_internally`).
- **Secondary-only stays awaiting-primary/quarantined**
  (`test_secondary_only_stays_awaiting_primary`).
- **No `legacy_unverified` record is citable** — `citable_entries()` excludes
  them all; `is_citable` is false (`test_no_legacy_unverified_is_citable`).
- **Collision / Unicode-case / legacy-slug redirect** —
  `test_unicode_and_case_normalization_collapse_to_one_id`,
  `test_legacy_slug_redirect_resolves`.
- **Reversible merge, deterministic split** —
  `test_merge_is_reversible_and_keeps_surviving_id`,
  `test_split_ids_are_deterministic`.

## Not settled here

MIG-003 (representative migration pilot) is A2. This closes the A0
review-workflow lane; the model core (AI/TRIAGE-002/EXT/CLASS/ROUTE) remains
behind an A2 decision.
