"""Durable PostgreSQL job queue (DOM-003): leases, heartbeats,
idempotency keys, retry scheduling, dead-letter. No Temporal until the
section 3 trigger is measured."""
import json
import secrets

import sqlalchemy as sa

from .db import jobs
from .states import transition


def enqueue(conn, *, kind: str, payload: dict, idempotency_key: str,
            max_attempts: int = 3) -> str:
    existing = conn.execute(sa.select(jobs.c.job_id).where(
        jobs.c.idempotency_key == idempotency_key)).fetchone()
    if existing:
        return existing[0]
    job_id = f"job_{secrets.token_hex(6)}"
    conn.execute(jobs.insert().values(
        job_id=job_id, idempotency_key=idempotency_key, kind=kind,
        state="ready", payload=json.dumps(payload, sort_keys=True),
        max_attempts=max_attempts))
    return job_id


def lease(conn, *, owner: str, now: str, lease_until: str) -> dict | None:
    row = conn.execute(
        sa.select(jobs)
        .where(sa.or_(jobs.c.state == "ready",
                      sa.and_(jobs.c.state == "leased",
                              jobs.c.lease_expires_at < now)))
        .order_by(jobs.c.job_id).limit(1)
        .with_for_update(skip_locked=True)).fetchone()
    if row is None:
        return None
    if row.state == "ready":
        transition("job", "ready", "leased")
    # expired lease re-lease: still 'leased', new owner takes over
    conn.execute(jobs.update().where(jobs.c.job_id == row.job_id).values(
        state="leased", lease_owner=owner, lease_expires_at=lease_until,
        heartbeat_at=now, attempts=row.attempts + 1))
    return {"job_id": row.job_id, "kind": row.kind,
            "payload": json.loads(row.payload), "attempts": row.attempts + 1}


def heartbeat(conn, job_id: str, *, owner: str, now: str, lease_until: str) -> None:
    res = conn.execute(jobs.update().where(
        (jobs.c.job_id == job_id) & (jobs.c.lease_owner == owner)
        & (jobs.c.state == "leased")).values(
        heartbeat_at=now, lease_expires_at=lease_until))
    if res.rowcount != 1:
        raise RuntimeError("heartbeat on a lease this owner does not hold")


def complete(conn, job_id: str, *, owner: str) -> None:
    row = conn.execute(sa.select(jobs.c.state, jobs.c.lease_owner).where(
        jobs.c.job_id == job_id)).fetchone()
    if row.state == "completed":
        return  # idempotent completion
    transition("job", row.state, "completed")
    if row.lease_owner != owner:
        raise RuntimeError("completion by non-owner")
    conn.execute(jobs.update().where(jobs.c.job_id == job_id).values(
        state="completed", lease_owner=None, lease_expires_at=None))


def fail(conn, job_id: str, *, owner: str, retry_at: str) -> str:
    row = conn.execute(sa.select(jobs).where(jobs.c.job_id == job_id)).fetchone()
    if row.lease_owner != owner or row.state != "leased":
        raise RuntimeError("failure report from non-lease-holder")
    if row.attempts >= row.max_attempts:
        transition("job", "leased", "dead_lettered")
        conn.execute(jobs.update().where(jobs.c.job_id == job_id).values(
            state="dead_lettered", lease_owner=None, lease_expires_at=None))
        return "dead_lettered"
    transition("job", "leased", "retry_scheduled")
    conn.execute(jobs.update().where(jobs.c.job_id == job_id).values(
        state="retry_scheduled", retry_at=retry_at, lease_owner=None,
        lease_expires_at=None))
    return "retry_scheduled"


def requeue_due(conn, *, now: str) -> int:
    res = conn.execute(jobs.update().where(
        (jobs.c.state == "retry_scheduled") & (jobs.c.retry_at <= now)
    ).values(state="ready", retry_at=None))
    return res.rowcount
