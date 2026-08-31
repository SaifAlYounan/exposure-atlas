# HAR-005-01 — Evidence, transcripts, budgets, completion contract

- Raw session/tool-event logs live OUTSIDE the worktree; the repository
  ledger (plan/evidence.jsonl) holds immutable receipt references only
  (schema schemas/plan/task-evidence-receipt.schema.json).
- Receipt binds task, provider, run, tool-policy hash, sandbox identity,
  base/result commits, configuration, commands, artifact hashes.
- Pre-action/success/failure/denial/interruption/crash all represented.
- Budget: reserve conservative worst case before each run; reconcile
  observed usage; exhaustion -> blocked_budget, never degraded rigour.
  Ceilings live in config/budgets.yaml (null = fail closed; G0-Q7).
- Completion: interruption, API failure, max-turn exit, or provider
  success-without-valid-output cannot complete a task; clean-checkout
  CI receipts under an identity the builder cannot read (A-001.3) are
  the only gate-satisfying evidence — already enforced by gate-verify's
  self_asserted rule.
