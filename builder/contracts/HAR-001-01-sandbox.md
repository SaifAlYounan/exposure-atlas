# HAR-001-01 — Sandbox and capability broker contract (solo scale)

Boundary = the operator-provisioned box (handoff section 2): repo-only
mounts, scrubbed env, deny-by-default egress via allowlisting proxy,
single injected model key, branch-limited git, clean-checkout CI under
an identity the builder cannot read, session/day ceilings, transcripts
outside the worktree. Current-state deviation recorded in docs/as-built.md
(M4) pending G0-Q11.

Acceptance targets (SPEC HAR-001, tested at BOOT-060): read-only mounts
for planner/reviewer/auditor; no ambient credentials readable; symlink/
traversal/subprocess/package-script escapes fail; deny-by-default
network with connected-peer validation; agent cannot modify host policy,
audit log or CI identity.
