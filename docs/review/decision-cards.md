# Review-task builder — decision cards (REV-002)

Assembles one decision card that asks a single bounded question and carries
the evidence to answer it (SPEC §9 REV-002). Engine:
`packages/python/atlas/review_card.py`; card shape:
`schemas/domain/review-card.schema.json`. Pure, deterministic, A0 — no
network, credentials, or model calls (it *displays* model votes; it never
calls a model).

## Enforced invariants

- **Evidence-linked assertions.** A `source_derived` assertion must carry
  non-empty anchor `support`; a `derived` edit must carry accepted
  `parent_assertion_ids` + a `transform_version`. `build_card` raises
  `CardError` otherwise (schema also enforces this per-item).
- **Warnings cannot be hidden.** `ocr_detected` / `superseded_source` are
  surfaced as `warnings`; the builder has no switch to suppress them.
- **Classification edits need a taxonomy rationale, not anchors.** An
  `is_edit` classification requires `taxonomy_rationale` and must not carry
  source anchors.
- **Restricted content never leaves via a channel-safe summary.**
  `channel_safe_summary(card)` returns only routing metadata (question,
  rights/security state, restrictive default, expiry, warning *kinds*) and
  `authenticated_view_required: true`; when `restricted`, it omits
  `canonical`, `assertions`, `model_votes`, `classifications`,
  `diff_summary`, `verifier_results`, and even the proposed answer. Only the
  authenticated view carries content.
- **Model votes are short evidence, never chain-of-thought.** A
  `chain_of_thought` / `reasoning_trace` field is rejected; rationales are
  capped at 600 chars. Votes are evidence, never a substitute for the
  operator's judgment.

## Card fields

One bounded `question`; `requested_decision` + `proposed_answer` +
`alternatives`; `issuer` (authority role + name); `source_version_id`;
`rights_state` / `security_state` / `restricted`; `canonical`
(hash + anchors, never restricted raw bytes); `assertions`;
`classifications`; `model_votes`; `boundary_ref`; `verifier_results`;
`duplicates`; `diff_summary`; `options` (each with publication / freshness /
downstream consequences); `warnings`; `restrictive_default`; `expiry`.

## Acceptance (SPEC §9 REV-002) → tests

- Source-derived → evidence; derived → parents + transform →
  `test_source_derived_assertion_requires_anchor_support`,
  `test_derived_assertion_requires_parents_and_transform`.
- OCR/superseded warnings cannot be hidden →
  `test_ocr_and_superseded_warnings_cannot_be_hidden`.
- Classification edits require taxonomy rationale, not anchors →
  `test_classification_edit_requires_taxonomy_rationale_not_anchors`.
- Card never exposes restricted content through a summary →
  `test_channel_safe_summary_hides_restricted_content`.
- Model rationales short, no chain-of-thought →
  `test_model_votes_reject_chain_of_thought_and_cap_length`.

## Not settled here

Authenticated reviewer actions (REV-003), the weekly pack transport
(REV-004), and workload calibration (REV-005) are separate tasks.
