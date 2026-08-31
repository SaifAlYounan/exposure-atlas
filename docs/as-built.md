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
