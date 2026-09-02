# Authenticated reviewer actions (REV-003)

The decision core behind the authenticated command API (SPEC §9 REV-003).
Engine: `packages/python/atlas/reviewer_actions.py`; decisions use the
existing `review-decision` schema (immutable, `decided_by: Alexios`).

**Deployment binding.** Real WebAuthn/passkey authentication, session
establishment, CSRF issuance and HTTP transport live at the service layer and
hand this core an already-authenticated `Session`. This module enforces the
security *properties* deterministically and is pure A0 — no network,
credentials, or model calls. (Mirrors how the live-fetch probe injected its
fetcher.)

## Actions and roles

Actions: approve, reject, edit, request_source, merge, link, split, escalate,
correct, withdraw, suppress, retract, defer.

Four logical roles — `operator_reviewer`, `policy_rights_adjudicator`,
`release_approver` (human, all bound to Alexios's one account) and
`release_bot` (automation, never a review decision). **Decision types stay
separate:** each decision class requires its specific role, so an earlier
ordinary-review approval never satisfies a later rights, policy, or release
decision. The operator's assistant is never a reviewer (a non-Alexios actor is
rejected).

## Enforced guarantees

- **Session** must be authenticated, unexpired, and present the correct CSRF
  token; the actor must be the operator.
- **Nonce replay** is rejected; **idempotency keys** make retries safe (the
  prior result is returned, never re-applied).
- **Optimistic locking** — a write whose `expected_version` != the current
  version is rejected, so concurrent decisions cannot silently overwrite.
- **Edited fact support** — an `edited_assertion` must have valid
  support/derivation (source-derived → anchors; derived → accepted parents +
  transform) or it cannot be saved approved.
- **Cooling-period confirmation** — material corrections and
  boundary/rubric/source-policy/rights-policy changes must be *staged* on day 1
  and *confirmed by the same operator on a later calendar day* against the same
  fresh diff. This is a cooling period, not dual adjudication.
- **No bulk approval** for sensitive classes (rights/personal-data, conflicts,
  identity merge/split, policy override, material correction,
  suppression/retraction, release approval, automation qualification).

Every applied decision yields an immutable, schema-valid `ReviewDecision`
recording actor, role, input version(s), time and reason, and the result also
carries the output version.

## Acceptance (SPEC §9 REV-003) → tests

- Auth/expiry/CSRF, replay, optimistic locking, idempotency →
  `test_session_auth_expiry_csrf_and_assistant_not_reviewer`,
  `test_nonce_replay_rejected`, `test_optimistic_locking_blocks_stale_write`,
  `test_idempotent_retry_returns_same_result_without_reapplying`.
- Edited fact without support cannot be approved →
  `test_edited_fact_without_support_cannot_be_approved`.
- Decision records actor/role/input-version/time/reason/output-version →
  `test_valid_action_records_decision_and_bumps_version`.
- Role separation between decision types →
  `test_role_separation_between_decision_types`.
- Cooling-period confirmation →
  `test_cooling_period_requires_later_day_and_fresh_diff`.
- No bulk approval for sensitive classes →
  `test_sensitive_classes_cannot_be_bulk_approved`.

## Not settled here

The service-layer WebAuthn/CSRF/session transport, and the weekly pack
(REV-004) and calibration (REV-005), are separate.
