# Review queue model and priorities (REV-001)

Separate review queues with priority minimums and a restrictive default for
every item (SPEC §9 REV-001). Engine:
`packages/python/atlas/review_queue.py`; items use the existing `review-task`
schema. Pure, deterministic, A0 — no network, credentials, or model calls.

## Queues

`new_candidates`, `status_updates`, `uncertain`, `duplicates`, `corrections`,
`quarantine`, `migration`. `new_candidates` and `migration` are the
**low-priority intake** queues that backpressure may pause.

## Priorities and handling path

| Priority | Meaning | Path |
|---|---|---|
| P0 | suspected bad publication / confidentiality / security | emergency (SPEC §12) |
| P1 | material status update or record nearing stale | same-day notice |
| P2 | clean new candidate | weekly pack |
| P3 | awaiting primary / research | weekly pack |

Default TTLs by priority (overridable): P0 4h, P1 24h, P2 168h, P3 336h.

## Restrictive default — no answer is never acceptance

Every task carries a `restrictive_default` ∈ {`hold`, `exclude`,
`human_review`, `defer`}; `make_task` refuses any accepting/publishing value.
`expire_unanswered(now)` resolves every past-expiry open task to its
restrictive default — an unanswered card **never** becomes acceptance,
inclusion, or publication.

## Measurable by queue

`metrics(queue, now)` reports arrivals, exits, currently open, max open age,
handling times (seconds), and reason-code counts — all per queue.

## Backpressure

`backpressure_paused_queues()` returns the low-priority intake queues to pause
once open P0+P1 load reaches the threshold; **P0/P1 work is always
preserved** and never paused.

## Acceptance (SPEC §9 REV-001) → tests

- Arrival/exit/age/handling/reason-codes measurable by queue →
  `test_metrics_measurable_by_queue`.
- Backpressure pauses low-priority, preserves P0/P1 →
  `test_backpressure_pauses_low_priority_but_preserves_p0_p1`.
- Expiry + restrictive default; no answer → restrictive, never acceptance →
  `test_unanswered_expires_to_restrictive_never_acceptance`,
  `test_restrictive_default_cannot_be_accepting`.
- P0 emergency / P1 same-day / ordinary weekly → `test_handling_paths`.

## Not settled here

Card content (REV-002), authenticated reviewer actions (REV-003), the weekly
pack transport (REV-004), and workload calibration (REV-005) are separate
tasks. This task is the queue model only.
