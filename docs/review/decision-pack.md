# Weekly decision pack and transport (REV-004)

Builds one immutable weekly pack manifest and the rights-safe transport around
it (SPEC §9 REV-004). Engine: `packages/python/atlas/decision_pack.py`; the
pack and its items use the existing `decision-pack` / `decision-pack-item`
schemas. Pure, deterministic, A0 — no network, credentials, or model calls.

## Pack build

`build_pack(items, week, created_at)`:
- **orders P0/P1 first**, then oldest-first (age), then value;
- **caps** by the measured capacity rules (SPEC §0.2, pinned by the schema):
  240 review minutes, 25 decision cards, 3 complex decisions, 12 record
  reviews. Items that don't fit are returned as **excess** (they stay queued)
  and `throttle_discovery` is set when any excess remains;
- emits a schema-valid immutable `DecisionPack` + `DecisionPackItem`s, each
  binding its exact `input_hashes`.

## Transport — rights-safe, never a bearer credential

- `transport_payload(pack, cards)` carries only `channel_safe_summary`
  projections (never restricted content) and is flagged
  `bearer_credential: false`. `can_approve_from_channel(...)` is always
  `False` — **channel compromise alone cannot approve or publish**; approval
  goes through the authenticated command API (REV-003).
- `ViewLinkStore` issues **single-use, expiring** view links; a replayed or
  expired link raises. A consumed link grants *view* access only, never
  approval.

## Draft envelopes bound to input hashes

`draft_envelope(item, action)` is a non-bearer draft the assistant may
prepare; `envelope_valid(envelope, live_input_hashes)` is true only if the
live hashes still match exactly — **a changed source/proposal/policy
invalidates the draft decision**.

## Unanswered cards expire restrictively

`expire_unanswered(items, now)` resolves every past-expiry card to its
`restrictive_default` — never acceptance or publication.

## Acceptance (SPEC §9 REV-004) → tests

- Capped; excess queued; discovery throttles →
  `test_pack_capped_by_minutes_excess_queued_and_throttles`,
  `test_complex_decisions_capped_at_three`, `test_pack_orders_p0_p1_first`.
- Single-use expiring view links; replays fail →
  `test_view_link_single_use_and_expiry`.
- Channel-safe, not a bearer credential →
  `test_transport_is_rights_safe_and_not_a_bearer_credential`.
- Actions bound to exact input hashes → `test_envelope_binds_to_input_hashes`.
- Unanswered cards expire restrictively →
  `test_unanswered_cards_expire_to_restrictive_state`.

## Not settled here

The concrete Slack/email/assistant transport and the authenticated view
service are deployment bindings; workload calibration is REV-005.
