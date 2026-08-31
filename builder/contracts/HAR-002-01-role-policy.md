# HAR-002-01 — Role/tool policy contract (solo scale)

One declarative policy file (config/builder-roles.yaml, created at
HAR-002) compiled into Claude Agent SDK subagent `tools` +
`disallowedTools` + permission rules. Inputs: role, task, authorization
level, repo/network scope, operator decision IDs, expiry. Roles and
their tool profiles are SPEC 0.5's table. Omitted tools must be
unavailable, not discouraged; every side-effect executor rechecks policy
pre-action; policy changes are versioned and require requalification
(BOOT-060/070) and never retroactively alter receipts.
