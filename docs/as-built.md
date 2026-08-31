# As-built (living document)

## Workspace fingerprint (BOOT-010)
- Date: 2026-08-31
- Repository: SaifAlYounan/exposure-atlas
- Base commit (pre-build): `4b1e287dbbe865cba0128efbedb05bb645f68870`
- Branch: `claude/exposure-atlas-coordinator-qgd90l`
- Deployment identifier: none (no deployment exists)
- Seed file hashes (SHA-256):
  - SPEC.md `6663e17e61a94e8052f017f7d3960e20a329e1487e0878e5e940aed518463723`
  - CLAUDE.md `63ff1dfe1cfdee469a8fb9450e24fff56afe6381ed2d54cb1892b756f9f9a068`
  - docs/atlas-handoff.md `44576ca8eef664d7af52dc502439c0102de3eb6630c36f95a32a3842100fc23b`

## Builder control plane (actual, not target)
- Harness: Claude Code managed remote session (Claude Agent SDK family),
  configured model ID `claude-fable-5` at time of writing.
- Git: branch-limited push to `claude/exposure-atlas-coordinator-qgd90l`;
  `main` untouched by the builder.
- Network: outbound via the environment's allowlisting HTTPS proxy.
- DEVIATION vs handoff section 2 sandbox: recorded in D-002 and
  first-turn difference M4; accepted for A0 documentation/schema/fixture
  work only, pending G0-Q11.
- Cost ceilings: numeric ceilings UNSET (G0-Q7); interim containment is
  the managed session's own harness ceilings.

## Toolchain (bootstrap)
- Python 3.11.15 (system; product target is 3.12+ per SPEC 5.1 — pinned
  at PLT-001), GNU make, git 2.43.0, uv.
- Bootstrap venv (`.venv`, not committed): jsonschema==4.23.0,
  pyyaml==6.0.2, pytest==8.3.3. Proper lockfile-and-hash pinning is
  PLT-001/PLT-004 work; this interim pin is recorded here per SPEC
  0.3(16-17).

## SDK documentation pinning (HAR-003-01 input)
Not yet read/pinned in this turn; the adapter contract marks exact SDK
package/version pinning as its first implementation step (network
read-only access to official SDK docs is A0-permitted).

## G1 session 1 (2026-08-31, under D-017)
- CI: GitHub Actions (`.github/workflows/ci.yml`) — clean checkout,
  uv-pinned bootstrap, plan-validate, ruff, pytest (39 tests),
  two-build release determinism. The builder cannot read the Actions
  identity; receipts referencing a green run ID are non-self-asserted.
- Package: `atlas` (packages/python/atlas), hatchling build, deps pinned
  in pyproject: jsonschema 4.23.0, pyyaml 6.0.2, pymupdf 1.24.10;
  dev: pytest 8.3.3, ruff 0.6.9. Layout mapping vs SPEC 5.3 recorded in
  ADR-0001 (single distribution, module boundaries preserved).
- Interim persistence: in-memory kernel + content-addressed filesystem
  evidence store + hash-chained audit JSONL. PostgreSQL persistence
  (DOM-002/DOM-003 full) is the next G1 session.
- Versions: canonicalizer 1.0.0, verifier 1.0.0, publication policy
  1.0.0. Test-key signing only (scheme test_key_sha256), real signing
  is SEC-002 (G3+).

## G1 session 2 (2026-08-31)
- Persistence: PostgreSQL 16 (system package; tests run an ephemeral
  initdb cluster on a unix socket, as `postgres` user when root). Deps
  added, pinned: sqlalchemy 2.0.35, psycopg[binary] 3.2.3. Alembic
  migrations begin at the first schema change (expand/contract per
  DOM-002); current DDL is the versioned baseline in atlas/db.py.
- Immutability: DB triggers refuse UPDATE/DELETE on acquisition
  receipts, acceptance decisions, audit events; assertions allow only
  the supersede pointer.
- MON-000: freshness aggregation rule v1.0.0; live overlay vs release
  snapshot represented as separate schemas.

## G1 session 3 (2026-08-31)
- Schema catalogue complete: 62 domain schemas under schemas/domain/,
  every one with a validating positive fixture and a generic
  unknown-property negative (tests/test_schema_catalogue.py).
- DOM-005/006 revision + projection builders; SRC-001 adapter SDK with
  conformance kit; REL-001A snapshot builder; DOC-003 language gate.
- 138 tests. Remaining G1: HAR-000-03..HAR-005, BOOT-060/070 harness
  qualification (capability report with honest substitutions for the
  managed environment per D-017), SRC-003 archive interface, kernel→DB
  integration, SEC-001-01 full coverage.

## G1 session 4 (2026-08-31)
- builder/core: compiled role policy (config/builder-roles.yaml, hashed,
  deny-by-default), budget ledger (reserve/reconcile/exhaustion), and
  the provider-neutral completion gate wrapping atlas_plan verification.
- builder/conformance/claude-capability-report.json: 8 capabilities
  proven by executable tests; 4 confinement capabilities explicitly NOT
  claimed — deferred to the operator sandbox as an A1 precondition
  (D-017), with substitution rows. Exact SDK pin happens at sandbox
  qualification.
- SRC-003 archive gate (disabled by default, fail-closed, attempt
  records); kernel acceptance-replay guard (SEC-08).

## G1 session 5 / close-out (2026-08-31)
- PLT-003 typed config + redaction; PLT-002 health checks with named
  missing dependencies; infra/local/docker-compose.yml written with
  explicit DIGEST-PINNING-REQUIRED markers (no docker daemon here).
- DEVIATION (G1 pack G1-Q3): the evidence store is a content-addressed
  filesystem store, not MinIO, until the sandbox/local stack exists.
  Never-overwrite and integrity-on-read are test-proven either way.
- Kernel-to-PostgreSQL integration decision: the G1 fixture slice
  remains file/memory-backed. Crash-safety and immutability claims are
  proven AT THE DOM-002/003 LAYER against real PostgreSQL; the G1
  vertical-slice acceptance (VER-002) does not require DB-backed state.
  Wiring the pipeline onto the DB is the first G2 implementation step
  and is listed in the G1 pack so the operator sees it explicitly.

## Confinement qualification design (2026-08-31, D-019)
- ADR-0002: GitHub-hosted confinement for HAR-001/HAR-003, honest
  residuals R1–R3. Verdict: qualifiable on GitHub-hosted infra
  conditional on four operator-only R1 controls.
- confinement.yml (A0-safe self-test, harden-runner audit) +
  live-fetch.yml.template (inert, A1-gated, harden-runner block with
  pilot-host allowlist + protected environment). CODEOWNERS added.
- tests/test_confinement.py (4 fixtures) proves the in-code egress
  blocks, host-policy denial enforcement of the SDK-denial fixture set,
  and that the ADR residuals cannot be silently removed.
- Proposed to the operator as pack 2026-W38-G1b.

## G2 first step — kernel↔PostgreSQL integration (2026-08-31, D-022)
- atlas/kernel.py takes an optional `engine`; when set, ingest/
  canonicalize/propose persist rows through atlas/db.py and approve uses
  accept_assertion_atomic (decision+assertion+audit in one transaction).
  The in-memory/file path is unchanged when engine is None.
- tests/test_db_integration.py runs the full VER-002 slice DB-backed:
  state is in PostgreSQL, the DB audit chain verifies, accepted
  assertions are immutable via the trigger, and the slice still serves.
- This is the acknowledged first G2 implementation step; it needs no new
  authorization (A0) and does not touch A1/live scope.

## G2 — pilot adapters + gated probe (2026-09-01, A1 preconditions met)
- atlas/pilot_adapters.py: CourtListener/RECAP (mirror custodian; copy
  provenance stays unverified until corroborated) and FTC (issuer_direct)
  adapters over synthetic cassettes (tests/fixtures/cassettes/). No live
  network; conformance kit passes.
- atlas/probe.py (SRC-004-80): live-probe entrypoint enforcing D-021 caps
  (<=50 docs/source, host allowlist, connected-peer-IP validation,
  recorded receipts, no model calls). run_live_probe REFUSES without the
  activation token that only the protected live-fetch environment injects
  (D-027); plan_probe is the network-free dry-run the operator reviews.
- live-fetch.yml.template stays INERT. Awaiting the operator's explicit
  "activate" confirmation before any live fetch (D-027).
