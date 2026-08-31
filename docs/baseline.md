# Reversible baseline (FND-000 / BOOT-020 / BOOT-030)

Recorded 2026-08-31 under decisions D-012 and D-014.

## BOOT-020 — legacy dataset count, export, hash
- **Counting rule:** legacy Atlas record objects (files or rows) in the
  repository worktree or full git history, excluding specification and
  handoff documents.
- **baseline_record_count: 0** (from actual inventory). Expected 316.
- Canonical export: `migrations/legacy/baseline-export.jsonl` (empty),
  SHA-256 `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (hash of the empty export).
- Per-row IDs/hashes: none (zero rows).
- **Mismatch consequence (SPEC 0.3.3 / BOOT-020):** every migration task
  is `blocked_external`. Unblocking requires a future written operator
  decision supplying a dataset or re-baselining the expected count.
  The operator confirmed no dataset exists outside this repository
  (D-012) and chose to hold (D-014).

## FND-000 — reversible baseline
- Baseline state: seed commit `4b1e287dbbe865cba0128efbedb05bb645f68870`.
- Restore command (non-destructive check-out of the pre-build state):
  `git checkout 4b1e287 -- .` in a scratch clone, or
  `git clone <origin> && git checkout 4b1e287`.
- Existing user changes: none existed; nothing to preserve beyond the
  three seed files (hashes in docs/as-built.md).
- Pre-existing tests/builds: none existed; nothing predates this
  project.

## BOOT-030 — restorable backup receipt
- Backup practice (existing repository practice per D-012: git):
  the GitHub remote `origin` holds the full history; branch
  `claude/exposure-atlas-coordinator-qgd90l`.
- Restore check: performed non-destructively (fresh clone into the
  session scratch area; HEAD hash compared equal) — see evidence
  receipt rcpt_boot-030 in plan/evidence.jsonl.
- Encryption/retention: GitHub-hosted private-repo storage under the
  operator's account; no separate backup target exists yet (D-012).
  A dedicated backup target becomes OPS-003 scope.

## FND-002 — legacy record inventory
- Migration ledger: `migrations/legacy/ledger.jsonl` (empty).
- Reconciliation: 0 ledger entries == baseline_record_count 0. Vacuously
  complete; no record is labelled verified by inventory (none exist).
