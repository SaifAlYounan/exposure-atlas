# ADR-0001: Infrastructure and cryptography (PLAN-002 — PROPOSED)

Status: **proposed** — becomes approved only through the G0 operator
decision (pack item G0-Q9 acknowledgement + explicit ADR approval).

## Runtime environments
- **Local development:** docker-compose stack — PostgreSQL 16 (pinned
  digest), MinIO (pinned digest), one Python worker process, no external
  network beyond allowlisted registries. SPEC 5.1 defaults adopted:
  Python 3.12+, FastAPI, Pydantic v2, SQLAlchemy 2, Alembic, uv; pnpm +
  Next.js for reviewer/public web when those tasks start.
- **A3 internal environment:** one small operator-paid cloud VM or
  container host (vendor is an operator choice at the A3 decision;
  candidates: Hetzner/Fly.io/AWS Lightsail — cost vs lock-in tradeoff:
  commodity VM minimizes lock-in, managed platform minimizes ops time).
  Operator-only access via WebAuthn; separate OS users/db roles per
  runtime trust boundary (SPEC 3.4).
- **A4 beta:** separate account/namespace, separate credentials,
  read-only release/overlay store, no route to evidence systems.
  Version-controlled reproducible deployment (compose/terraform-lite),
  full reviewed IaC deferred to A5 per section 3.1.

## Storage
- Operational DB: PostgreSQL (also durable job queue + scheduler —
  leases/heartbeats/idempotency per DOM-003; Temporal only on measured
  trigger per section 3.1).
- Evidence vault: S3-compatible versioned object store (MinIO locally;
  provider bucket at A3+) — private, content-addressed.
- Release-control repository: separate private Git repo (G0-Q10 names
  it), generated only by the release builder.

## Identity, roles, IAM mapping
Every SPEC 3.4 runtime role maps to: distinct OS process/container +
distinct PostgreSQL role (GRANT-limited) + distinct object-store
credential + distinct egress policy. Minimum DB roles:
acquisition_writer, artifact_writer, proposal_writer, validation_writer,
review_decider, release_reader, release_bot, public_reader. Conformance
tests run under the deployed identities (PLT-004/PLT-005).

## Cryptography and signing
- G1–G3 fixtures: disposable, clearly-marked test keys (Ed25519 via
  age/minisign-style tooling; canonical byte format defined at
  SEC-002-01).
- Before A4: operator hardware-backed non-exportable key (two hardware
  authenticators + separately encrypted recovery, per section 3.1 row 1)
  for release/suppression/checkpoint signing; checkpoints copied to an
  account the builder/release bot cannot write.
- Before A5: managed KMS/HSM.
- Builder, runtime workers and release bot never hold private signing
  keys.

## Operator authentication
WebAuthn/passkey for the reviewer surface (REV-003); role definitions in
code, movable to OIDC groups when a second human is provisioned.

## Backup/restore
Nightly PostgreSQL + object-store manifests to a separate account/
location; restore tested (OPS-003); ordinary backups never contain
private signing keys.

## Sandbox / root of trust
A-001.3 solo scale: the operator-provisioned box of handoff section 2 is
the boundary; SDK permission rules/hooks are the inner layer; builder
code adds only budget ledger, evidence writer, transcript store,
completion gate. Current deviation (managed remote session) recorded in
D-002/as-built; G0-Q11 decides.

## External provisioning
All external provisioning is `blocked_external`/`blocked_authorization`
until the matching A-level decision. Nothing in this ADR provisions
anything.
