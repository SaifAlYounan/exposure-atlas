"""Review queue model and priorities (REV-001).

Separate queues, priority minimums, and a restrictive default for every item
(SPEC §9 REV-001). Guarantees:

- arrival, exit, age, handling time and reason codes are measurable **by
  queue**;
- backpressure can pause low-priority discovery/migration while preserving
  P0/P1 work;
- every item has an expiry and a restrictive default disposition — no answer
  resolves to a restrictive state (``hold`` / ``exclude`` / ``human_review``
  / ``defer``), **never** acceptance or publication;
- P0 uses the emergency path, P1 gets same-day notice, ordinary items wait
  for the weekly pack.

Pure and deterministic; no network, credentials or model calls (A0). Tasks
validate against the existing ``review-task`` schema.
"""
import datetime

from .canonical import sha256_hex
from .schemas import validate

QUEUES = ("new_candidates", "status_updates", "uncertain", "duplicates",
          "corrections", "quarantine", "migration")
PRIORITIES = ("P0", "P1", "P2", "P3")
RESTRICTIVE_DEFAULTS = ("hold", "exclude", "human_review", "defer")
# Low-priority intake queues that backpressure may pause.
LOW_PRIORITY_QUEUES = ("new_candidates", "migration")

# Restrictive default disposition per queue (never acceptance/publication).
QUEUE_DEFAULT_DISPOSITION = {
    "new_candidates": "human_review",
    "status_updates": "defer",
    "uncertain": "human_review",
    "duplicates": "human_review",
    "corrections": "hold",
    "quarantine": "hold",
    "migration": "defer",
}
# Default time-to-live (hours) by priority: P0 emergency, P1 same-day,
# ordinary items wait for the weekly / fortnightly pack.
PRIORITY_TTL_HOURS = {"P0": 4, "P1": 24, "P2": 168, "P3": 336}


class ReviewQueueError(ValueError):
    pass


def handling_path(priority: str) -> str:
    """P0 -> emergency (section 12); P1 -> same-day notice; else weekly pack."""
    if priority == "P0":
        return "emergency"
    if priority == "P1":
        return "same_day"
    return "weekly_pack"


def _parse(ts: str) -> datetime.datetime:
    return datetime.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def _iso(dt: datetime.datetime) -> str:
    return dt.astimezone(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def make_task(queue: str, priority: str, question: str, created_at: str,
              restrictive_default: str | None = None, ttl_hours: int | None = None,
              input_hashes: dict | None = None) -> dict:
    """Build a schema-valid ReviewTask with an expiry and restrictive default.

    The restrictive default cannot be an accepting/publishing state; if none is
    given, the queue's default (always restrictive) is used.
    """
    if queue not in QUEUES:
        raise ReviewQueueError(f"unknown queue {queue!r}")
    if priority not in PRIORITIES:
        raise ReviewQueueError(f"unknown priority {priority!r}")
    default = restrictive_default or QUEUE_DEFAULT_DISPOSITION[queue]
    if default not in RESTRICTIVE_DEFAULTS:
        raise ReviewQueueError(f"restrictive_default must be restrictive, got {default!r}")
    ttl = ttl_hours if ttl_hours is not None else PRIORITY_TTL_HOURS[priority]
    created = _parse(created_at)
    expiry = created + datetime.timedelta(hours=ttl)
    task = {
        "schema_version": "atlas-review-task/v1",
        "task_id": "rvt_" + sha256_hex(f"{queue}\n{question}\n{created_at}".encode())[:12],
        "queue": queue,
        "priority": priority,
        "question": question,
        "restrictive_default": default,
        "created_at": created_at,
        "expiry": _iso(expiry),
    }
    if input_hashes:
        task["input_hashes"] = input_hashes
    validate("review-task.schema.json", task)
    return task


class ReviewQueue:
    """In-memory queue index with by-queue metrics and backpressure."""

    def __init__(self, p01_backpressure_threshold: int = 5):
        self._open: dict[str, dict] = {}       # task_id -> task
        self._arrived: dict[str, str] = {}     # task_id -> arrived_at
        self._exits: list[dict] = []           # {task_id, queue, priority, arrived, exited, reason, resolution}
        self._threshold = p01_backpressure_threshold

    def add(self, task: dict, at: str) -> None:
        validate("review-task.schema.json", task)
        self._open[task["task_id"]] = task
        self._arrived[task["task_id"]] = at

    def resolve(self, task_id: str, at: str, reason: str, resolution: str) -> None:
        task = self._open.pop(task_id, None)
        if task is None:
            raise ReviewQueueError(f"no open task {task_id!r}")
        self._exits.append({
            "task_id": task_id, "queue": task["queue"], "priority": task["priority"],
            "arrived": self._arrived.pop(task_id), "exited": at,
            "reason": reason, "resolution": resolution,
        })

    def expire_unanswered(self, now: str) -> list[dict]:
        """Resolve every open task past its expiry to its restrictive default.

        Returns the applied dispositions; the resolution is ALWAYS restrictive
        — an unanswered card never becomes acceptance or publication.
        """
        applied = []
        for task_id, task in list(self._open.items()):
            if _parse(now) >= _parse(task["expiry"]):
                disp = task["restrictive_default"]
                self.resolve(task_id, now, reason="expired_unanswered", resolution=disp)
                applied.append({"task_id": task_id, "queue": task["queue"], "disposition": disp})
        return applied

    def open_by_priority(self) -> dict:
        counts = {p: 0 for p in PRIORITIES}
        for t in self._open.values():
            counts[t["priority"]] += 1
        return counts

    def backpressure_paused_queues(self) -> list[str]:
        """Low-priority intake queues to pause when P0+P1 load is high; P0/P1
        work is always preserved (never paused)."""
        load = self.open_by_priority()
        if load["P0"] + load["P1"] >= self._threshold:
            return list(LOW_PRIORITY_QUEUES)
        return []

    def metrics(self, queue: str, now: str) -> dict:
        """By-queue: arrivals, exits, currently open, ages and handling times."""
        if queue not in QUEUES:
            raise ReviewQueueError(f"unknown queue {queue!r}")
        opens = [(tid, t) for tid, t in self._open.items() if t["queue"] == queue]
        exits = [e for e in self._exits if e["queue"] == queue]
        ages = [(_parse(now) - _parse(self._arrived[tid])).total_seconds() for tid, _ in opens]
        handling = [(_parse(e["exited"]) - _parse(e["arrived"])).total_seconds() for e in exits]
        reason_codes: dict[str, int] = {}
        for e in exits:
            reason_codes[e["reason"]] = reason_codes.get(e["reason"], 0) + 1
        return {
            "queue": queue,
            "arrivals": len(opens) + len(exits),
            "exits": len(exits),
            "open": len(opens),
            "max_open_age_seconds": max(ages, default=0.0),
            "handling_seconds": sorted(handling),
            "reason_codes": reason_codes,
        }
