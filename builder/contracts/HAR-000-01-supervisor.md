# HAR-000-01 — Provider-neutral supervisor contract (solo scale, A-001.3)

The host scheduler — not a model — owns the DAG, authorization, role
dispatch and task status (SPEC 5.5.1). At solo scale the supervisor is:
`tools/atlas_plan.py` (grown into `builder/core/` at HAR-000-03) +
versioned config under `config/` (authorization.yaml, budgets.yaml,
role policy at HAR-002).

Interface (SPEC 0.4), solo-scale binding:
- start_session/run_agent/run_specialist -> Claude Agent SDK adapter
  (HAR-003) fresh top-level sessions per assurance role.
- request_tool -> SDK permission rules + host policy recheck.
- pause_for_operator/resume_after_operator -> decision-pack answer files
  + decision-log entries; no assistant-held session.
- record_event -> transcript store (HAR-005), outside worktree.
- close_task -> TaskTransition: `done` only with a clean-checkout CI
  receipt for the exact result commit (gate enforced by atlas_plan
  gate-verify; self_asserted receipts never satisfy it).

Acceptance (unchanged from SPEC HAR-000): provider result cannot change
task/gate/authorization state; completion needs clean-checkout evidence;
supervisor state transitions fail closed on unknown fields.
