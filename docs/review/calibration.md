# Workload calibration (REV-005)

Derives weekly review capacity from measured handling data and enforces the
SPEC §0.2 guardrails (SPEC §9 REV-005). Engine:
`packages/python/atlas/calibration.py`. Pure, deterministic, A0 — these are
operational metrics, not a persisted domain object; no network, credentials,
or model calls.

## Measured metrics

`Calibration.record(card_type, handling_minutes, edited=, deferred=)` then
`stats_by_card_type()` → per type: `n`, `median_minutes`, `p95_minutes`,
`edit_rate`, `deferral_rate`. (Arrival rate, interruptions and intra-rater
change rate feed in from the same measured stream.)

## Capacity and caps

- `available_review_minutes(reserve)` = 240 − reserve, with **reserve required
  in 60-90 min** for releases/incidents/operational review.
- `enforced_caps(packs_completed, operator_approved_revision)` returns the
  **§0.2 initial caps** (240 / 25 / 12 / 3) until **three real packs AND an
  operator-approved revision** justify a change.
- `throttle_discovery(...)` fires on any §0.2 rule-7 trigger: trailing-3-week
  arrivals > 80% of capacity, pending > 2 weeks of capacity, an ordinary item
  older than 21 days, a status/correction item older than 48h, or > 20%
  deferral across two consecutive packs.

## Demand, unavailability, labeling

- `demand_response(demand, capacity)` — when demand exceeds capacity, pause
  low-value discovery and migration; **evidence gates are never changed** to
  absorb demand (`change_evidence_gates: false`).
- `operator_unavailable_mode()` — decisions and releases **frozen**, monitoring
  **active**, degraded/stale states **visible**.
- `resample_label(same_operator)` / `validate_report_labeling(...)` — a
  single-operator delayed re-review is **intra-rater reliability** and is
  rejected if a report tries to describe it as **inter-reviewer agreement**.

## Acceptance (SPEC §9 REV-005) → tests

- Capacity from measured handling with 60-90 reserved →
  `test_available_minutes_reserves_60_to_90`,
  `test_stats_median_p95_edit_deferral_by_card_type`.
- Initial caps until 3 packs + operator revision →
  `test_initial_caps_enforced_until_three_packs_and_operator_revision`.
- Demand over capacity pauses low-value discovery/migration before gates →
  `test_demand_over_capacity_pauses_before_changing_gates`,
  `test_throttle_discovery_triggers`.
- Operator-unavailability freezes but keeps monitoring →
  `test_operator_unavailable_mode_freezes_but_keeps_monitoring`.
- Single-operator re-review never inter-reviewer →
  `test_single_operator_resample_is_never_inter_reviewer`.

## Not settled here

MIG-002 (idempotent importer) closes the A0 review-workflow lane. The model
core (AI/TRIAGE-002/EXT/CLASS) remains behind an A2 decision.
