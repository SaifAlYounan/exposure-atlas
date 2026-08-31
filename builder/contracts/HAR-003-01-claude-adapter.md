# HAR-003-01 — Claude Agent SDK adapter contract

Per SPEC 5.5.2, all ten numbered requirements adopted verbatim. Key
bindings: pin exact SDK + bundled Claude Code + full model IDs (no
aliases); fresh top-level sessions for implementer/security-reviewer/
verifier-auditor; headless dontAsk with launcher validation rejecting
bypassPermissions/acceptEdits; host-owned pre-tool admission + full
event capture; draft-07 projection then canonical 2020-12 revalidation;
resolved-model fallback fails the run; redacted transcript receipts;
provider budget controls + host ledger; TaskCompleted/stop hooks are
advisory only.

First implementation step (HAR-003): read current official SDK docs
(subagents/hooks/permissions/secure-deployment), pin exact package
versions, and record versions + doc URLs + qualification results in
docs/as-built.md. Qualify installed behavior, not documentation parity.
