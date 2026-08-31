"""Operational persistence (DOM-002/DOM-003 core), PostgreSQL.

Rules enforced here and by DB triggers:
- accepted assertions, acceptance decisions, acquisition receipts and
  audit events cannot be UPDATEd or DELETEd (append/supersede only);
- every domain change commits atomically with its audit event and any
  follow-up job row — a crash cannot create accepted state without its
  audit/job consequences;
- identical source bytes dedupe by (source_document_id, content_sha256)
  while every acquisition receipt is preserved.
"""
import json

import sqlalchemy as sa

from .canonical import canonical_json_bytes, sha256_hex

metadata = sa.MetaData()

source_documents = sa.Table(
    "source_documents", metadata,
    sa.Column("source_document_id", sa.Text, primary_key=True),
    sa.Column("payload", sa.Text, nullable=False))

source_versions = sa.Table(
    "source_versions", metadata,
    sa.Column("source_version_id", sa.Text, primary_key=True),
    sa.Column("source_document_id", sa.Text,
              sa.ForeignKey("source_documents.source_document_id"),
              nullable=False),
    sa.Column("content_sha256", sa.Text, nullable=False),
    sa.Column("payload", sa.Text, nullable=False),
    sa.UniqueConstraint("source_document_id", "content_sha256",
                        name="uq_sourcever_doc_hash"))

acquisition_receipts = sa.Table(
    "acquisition_receipts", metadata,
    sa.Column("acquisition_id", sa.Text, primary_key=True),
    sa.Column("source_version_id", sa.Text,
              sa.ForeignKey("source_versions.source_version_id"),
              nullable=False),
    sa.Column("payload", sa.Text, nullable=False))

text_artifacts = sa.Table(
    "text_artifacts", metadata,
    sa.Column("text_artifact_id", sa.Text, primary_key=True),
    sa.Column("source_version_id", sa.Text,
              sa.ForeignKey("source_versions.source_version_id"),
              nullable=False),
    sa.Column("canonical_sha256", sa.Text, nullable=False),
    sa.Column("payload", sa.Text, nullable=False))

assertion_proposals = sa.Table(
    "assertion_proposals", metadata,
    sa.Column("proposal_id", sa.Text, primary_key=True),
    sa.Column("source_version_id", sa.Text,
              sa.ForeignKey("source_versions.source_version_id"),
              nullable=False),
    sa.Column("payload", sa.Text, nullable=False))

acceptance_decisions = sa.Table(
    "acceptance_decisions", metadata,
    sa.Column("decision_id", sa.Text, primary_key=True),
    sa.Column("proposal_id", sa.Text,
              sa.ForeignKey("assertion_proposals.proposal_id"),
              nullable=False),
    sa.Column("payload", sa.Text, nullable=False))

assertions = sa.Table(
    "assertions", metadata,
    sa.Column("assertion_id", sa.Text, primary_key=True),
    sa.Column("proposal_id", sa.Text,
              sa.ForeignKey("assertion_proposals.proposal_id"),
              nullable=False),
    sa.Column("acceptance_decision_id", sa.Text,
              sa.ForeignKey("acceptance_decisions.decision_id"),
              nullable=False),
    sa.Column("superseded_by", sa.Text, nullable=True),
    sa.Column("payload", sa.Text, nullable=False))

audit_events = sa.Table(
    "audit_events", metadata,
    sa.Column("seq", sa.BigInteger, sa.Identity(), primary_key=True),
    sa.Column("prev_hash", sa.Text, nullable=False),
    sa.Column("event_hash", sa.Text, nullable=False),
    sa.Column("payload", sa.Text, nullable=False))

jobs = sa.Table(
    "jobs", metadata,
    sa.Column("job_id", sa.Text, primary_key=True),
    sa.Column("idempotency_key", sa.Text, nullable=False, unique=True),
    sa.Column("kind", sa.Text, nullable=False),
    sa.Column("state", sa.Text, nullable=False, server_default="ready"),
    sa.Column("payload", sa.Text, nullable=False),
    sa.Column("lease_owner", sa.Text, nullable=True),
    sa.Column("lease_expires_at", sa.Text, nullable=True),
    sa.Column("heartbeat_at", sa.Text, nullable=True),
    sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
    sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
    sa.Column("retry_at", sa.Text, nullable=True))

IMMUTABLE_TABLES = ["acquisition_receipts", "acceptance_decisions",
                    "audit_events"]

_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION atlas_forbid_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'table %% is append-only (SPEC 2.5)', TG_TABLE_NAME;
END; $$ LANGUAGE plpgsql;
"""

_ASSERTION_TRIGGER_SQL = """
CREATE OR REPLACE FUNCTION atlas_assertions_guard() RETURNS trigger AS $$
BEGIN
  IF TG_OP = 'DELETE' THEN
    RAISE EXCEPTION 'assertions are append-only; supersede instead';
  END IF;
  IF OLD.payload IS DISTINCT FROM NEW.payload
     OR OLD.assertion_id IS DISTINCT FROM NEW.assertion_id THEN
    RAISE EXCEPTION 'accepted assertions cannot be updated in place; supersede instead';
  END IF;
  RETURN NEW;  -- only superseded_by may change
END; $$ LANGUAGE plpgsql;
"""


def create_all(engine) -> None:
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql(_TRIGGER_SQL)
        conn.exec_driver_sql(_ASSERTION_TRIGGER_SQL)
        for t in IMMUTABLE_TABLES:
            conn.exec_driver_sql(
                f"DROP TRIGGER IF EXISTS {t}_freeze ON {t};"
                f"CREATE TRIGGER {t}_freeze BEFORE UPDATE OR DELETE ON {t} "
                f"FOR EACH ROW EXECUTE FUNCTION atlas_forbid_mutation();")
        conn.exec_driver_sql(
            "DROP TRIGGER IF EXISTS assertions_freeze ON assertions;"
            "CREATE TRIGGER assertions_freeze BEFORE UPDATE OR DELETE ON assertions "
            "FOR EACH ROW EXECUTE FUNCTION atlas_assertions_guard();")


def append_audit(conn, actor: str, action: str, at: str, detail: dict) -> str:
    row = conn.execute(sa.select(audit_events.c.event_hash)
                       .order_by(audit_events.c.seq.desc()).limit(1)).fetchone()
    prev = row[0] if row else "genesis"
    payload = {"actor": actor, "action": action, "at": at, "detail": detail}
    ev_hash = sha256_hex(canonical_json_bytes({"prev": prev, **payload}))
    conn.execute(audit_events.insert().values(
        prev_hash=prev, event_hash=ev_hash,
        payload=json.dumps(payload, sort_keys=True)))
    return ev_hash


def verify_audit_chain(conn) -> int:
    prev = "genesis"
    n = 0
    for row in conn.execute(sa.select(audit_events).order_by(audit_events.c.seq)):
        payload = json.loads(row.payload)
        expect = sha256_hex(canonical_json_bytes({"prev": prev, **payload}))
        if row.prev_hash != prev or row.event_hash != expect:
            raise RuntimeError(f"audit chain broken at seq {row.seq}")
        prev = row.event_hash
        n += 1
    return n


def accept_assertion_atomic(engine, *, proposal: dict, decision: dict,
                            assertion: dict, at: str,
                            follow_up_job: dict | None = None,
                            crash_before_commit: bool = False) -> None:
    """Decision + assertion + audit (+ job) in ONE transaction."""
    with engine.begin() as conn:
        conn.execute(acceptance_decisions.insert().values(
            decision_id=decision["decision_id"],
            proposal_id=decision["proposal_id"],
            payload=json.dumps(decision, sort_keys=True)))
        conn.execute(assertions.insert().values(
            assertion_id=assertion["assertion_id"],
            proposal_id=assertion["proposal_id"],
            acceptance_decision_id=assertion["acceptance_decision_id"],
            superseded_by=None,
            payload=json.dumps(assertion, sort_keys=True)))
        append_audit(conn, "operator:Alexios", "assertion_accepted", at,
                     {"assertion_id": assertion["assertion_id"],
                      "decision_id": decision["decision_id"]})
        if follow_up_job is not None:
            from .jobs import enqueue
            enqueue(conn, **follow_up_job)
        if crash_before_commit:
            raise RuntimeError("simulated crash before commit")
