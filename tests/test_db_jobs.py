"""DOM-002/003 PostgreSQL tests: immutability triggers, atomic
domain+audit+job commit, crash safety, durable job queue semantics."""

import pytest
import sqlalchemy as sa

from atlas.db import (accept_assertion_atomic, acceptance_decisions,
                      append_audit, assertion_proposals, assertions,
                      audit_events, jobs as jobs_t, source_documents,
                      source_versions, verify_audit_chain)
from atlas.jobs import complete, enqueue, fail, heartbeat, lease, requeue_due

AT = "2026-08-31T12:00:00Z"


@pytest.fixture()
def seeded(pg_engine):
    with pg_engine.begin() as c:
        # test-harness-only reset: immutability triggers are the thing
        # under test, so cleanup must bypass them explicitly
        for t in [jobs_t, assertions, acceptance_decisions,
                  assertion_proposals, audit_events, source_versions,
                  source_documents]:
            c.execute(sa.text(f"ALTER TABLE {t.name} DISABLE TRIGGER ALL"))
            c.execute(t.delete())
            c.execute(sa.text(f"ALTER TABLE {t.name} ENABLE TRIGGER ALL"))
        c.execute(source_documents.insert().values(
            source_document_id="sdoc_t1", payload="{}"))
        c.execute(source_versions.insert().values(
            source_version_id="sver_t1", source_document_id="sdoc_t1",
            content_sha256="ab" * 32, payload="{}"))
        c.execute(assertion_proposals.insert().values(
            proposal_id="prop_t1", source_version_id="sver_t1", payload="{}"))
    return pg_engine


def _accept(engine, crash=False, job=None):
    accept_assertion_atomic(
        engine,
        proposal={"proposal_id": "prop_t1"},
        decision={"decision_id": "dec_t1", "proposal_id": "prop_t1"},
        assertion={"assertion_id": "ast_t1", "proposal_id": "prop_t1",
                   "acceptance_decision_id": "dec_t1"},
        at=AT, follow_up_job=job, crash_before_commit=crash)


def test_dedupe_same_bytes_unique_constraint(seeded):
    with pytest.raises(sa.exc.IntegrityError):
        with seeded.begin() as c:
            c.execute(source_versions.insert().values(
                source_version_id="sver_t2", source_document_id="sdoc_t1",
                content_sha256="ab" * 32, payload="{}"))


def test_dangling_references_fail(seeded):
    with pytest.raises(sa.exc.IntegrityError):
        with seeded.begin() as c:
            c.execute(assertions.insert().values(
                assertion_id="ast_x", proposal_id="prop_missing",
                acceptance_decision_id="dec_missing", payload="{}"))


def test_crash_leaves_no_partial_state(seeded):
    with pytest.raises(RuntimeError, match="simulated crash"):
        _accept(seeded, crash=True,
                job={"kind": "reverify", "payload": {},
                     "idempotency_key": "idem-crash"})
    with seeded.connect() as c:
        assert c.execute(sa.select(sa.func.count()).select_from(
            assertions)).scalar() == 0
        assert c.execute(sa.select(sa.func.count()).select_from(
            audit_events)).scalar() == 0
        assert c.execute(sa.select(sa.func.count()).select_from(
            jobs_t)).scalar() == 0


def test_atomic_accept_then_immutable(seeded):
    _accept(seeded, job={"kind": "reverify", "payload": {"a": 1},
                         "idempotency_key": "idem-1"})
    with seeded.connect() as c:
        assert verify_audit_chain(c) == 1
        assert c.execute(sa.select(sa.func.count()).select_from(
            jobs_t)).scalar() == 1
    # UPDATE/DELETE on accepted state must be refused by triggers
    with pytest.raises(sa.exc.DatabaseError):
        with seeded.begin() as c:
            c.execute(assertions.update().values(payload='{"tampered": true}'))
    with pytest.raises(sa.exc.DatabaseError):
        with seeded.begin() as c:
            c.execute(audit_events.delete())
    with pytest.raises(sa.exc.DatabaseError):
        with seeded.begin() as c:
            c.execute(acceptance_decisions.update().values(payload="{}"))
    # supersede pointer is the ONE permitted assertion change
    with seeded.begin() as c:
        c.execute(assertions.update().where(
            assertions.c.assertion_id == "ast_t1").values(
            superseded_by="ast_t2"))


def test_job_idempotency_lease_retry_deadletter(seeded):
    with seeded.begin() as c:
        j1 = enqueue(c, kind="fetch", payload={"u": 1},
                     idempotency_key="idem-A", max_attempts=3)
        j2 = enqueue(c, kind="fetch", payload={"u": 1},
                     idempotency_key="idem-A")
        assert j1 == j2  # replay creates no duplicate
    with seeded.begin() as c:
        got = lease(c, owner="w1", now=AT, lease_until="2026-08-31T12:05:00Z")
        assert got["job_id"] == j1 and got["attempts"] == 1
        heartbeat(c, j1, owner="w1", now=AT, lease_until="2026-08-31T12:10:00Z")
        with pytest.raises(RuntimeError):
            heartbeat(c, j1, owner="w2", now=AT,
                      lease_until="2026-08-31T12:10:00Z")
    with seeded.begin() as c:   # crash: lease expires, another worker takes it
        got2 = lease(c, owner="w2", now="2026-08-31T12:11:00Z",
                     lease_until="2026-08-31T12:16:00Z")
        assert got2 is not None and got2["job_id"] == j1
        assert fail(c, j1, owner="w2",
                    retry_at="2026-08-31T12:20:00Z") == "retry_scheduled"
        assert lease(c, owner="w3", now="2026-08-31T12:12:00Z",
                     lease_until="x") is None  # not due yet
        assert requeue_due(c, now="2026-08-31T12:21:00Z") == 1
    with seeded.begin() as c:
        got3 = lease(c, owner="w3", now="2026-08-31T12:22:00Z",
                     lease_until="2026-08-31T12:27:00Z")
        assert got3["attempts"] == 3  # == max_attempts(3): next fail dead-letters
        assert fail(c, j1, owner="w3",
                    retry_at="2026-08-31T12:30:00Z") == "dead_lettered"


def test_complete_is_idempotent_and_owner_checked(seeded):
    with seeded.begin() as c:
        j = enqueue(c, kind="x", payload={}, idempotency_key="idem-B")
        lease(c, owner="w1", now=AT, lease_until="2026-08-31T12:05:00Z")
        complete(c, j, owner="w1")
        complete(c, j, owner="w1")  # idempotent no-op
        row = c.execute(sa.select(jobs_t.c.state).where(
            jobs_t.c.job_id == j)).fetchone()
        assert row.state == "completed"


def test_audit_chain_tamper_detected_in_db(seeded):
    with seeded.begin() as c:
        append_audit(c, "x", "one", AT, {})
    with seeded.begin() as c:
        c.execute(sa.text(
            "ALTER TABLE audit_events DISABLE TRIGGER audit_events_freeze"))
        c.execute(sa.text(
            "UPDATE audit_events SET payload = '{\"actor\":\"evil\"}'"))
        c.execute(sa.text(
            "ALTER TABLE audit_events ENABLE TRIGGER audit_events_freeze"))
    with seeded.connect() as c:
        with pytest.raises(RuntimeError, match="audit chain broken"):
            verify_audit_chain(c)
