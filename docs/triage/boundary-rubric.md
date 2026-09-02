# Boundary rubric and checklist (TRIAGE-001)

Encodes the approved substantive boundary (`config/boundaries/v1.yaml`,
`boundary_version` 1.0.0, approval D-003) as a **structured checklist**.
Machine copy: `config/triage/boundary-rubric-v1.yaml`
(`schemas/domain/boundary-rubric.schema.json`); engine:
`packages/python/atlas/triage.py`.

Each criterion returns `met` / `not_met` / `uncertain` / `not_applicable`
with supporting anchors. `triage.evaluate` reconstructs the outcome
**deterministically** from the criterion results plus the boundary version,
so any decision is reproducible from its recorded checklist. This is the
manual/rule path; **TRIAGE-002** (blind model proposal runners) is A2 and is
not implemented here.

## Criteria

- **core inclusion** (all must be `met` for an include): `substantive_forum`,
  `proceeding_type`, `date_in_window`, `organisational_nexus`, `ai_nexus`.
- **gating**: `authoritative_instrument_exists` (`instrument`),
  `primary_accessible` (`accessibility`).
- **routing signal**: `announced_formal_investigation`.
- **exclusions** (any one `met` forces exclude): `press_without_primary`,
  `commentary_only`, `legislation_without_enforcement`, `ai_incidental_only`,
  `purely_private_dispute`.

## Deterministic decision order

1. **Completeness first.** If any criterion has no result, the outcome is
   `uncertain` → route `review`. **A missing criterion can never silently
   become an include.**
2. Any **exclusion** `met` → `exclude`.
3. Any **core inclusion** `not_met` → `exclude` (outside the substantive
   boundary).
4. Any **core inclusion** `uncertain`/`not_applicable` → `uncertain` → route
   `review` (a close exclusion goes to a human).
5. All core inclusion `met`:
   - `authoritative_instrument_exists` not `met`: with an announced formal
     investigation → route `awaiting_primary`; otherwise → route `review`.
   - `primary_accessible` not `met` (inaccessible primary) → route
     `awaiting_primary`.
   - otherwise → `include`.

`outcome` ∈ {`include`, `exclude`, `uncertain`} matches the
`boundary-proposal` schema; `route` additionally distinguishes `review` and
`awaiting_primary` for the candidate pipeline. `build_proposal` emits a
schema-valid `BoundaryProposal` (`proposed_by: manual`) that records **every**
criterion result, so the proposed outcome is always reconstructable.

## Acceptance (SPEC §9 TRIAGE-001) → tests

- Outcome reconstructable from criterion results + boundary version →
  `test_include_is_reconstructed_from_full_checklist`,
  `test_build_proposal_validates_and_is_reconstructable`.
- A missing criterion cannot silently include →
  `test_missing_criterion_never_silently_includes`.
- Close exclusions / inaccessible-primary route to review / awaiting_primary →
  `test_core_not_met_is_exclude_but_uncertain_is_review`,
  `test_no_instrument_routes_awaiting_or_review`,
  `test_inaccessible_primary_routes_awaiting_primary`.

## Not settled here

The rubric structures the boundary; it does not make the operator's
`BoundaryDecision`. Model-run proposals (TRIAGE-002) require A2 and are out of
scope. Criterion results themselves come from manual/authoritative review in
this path — no model call assigns them.
