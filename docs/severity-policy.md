# Severity policy (FND-005 — draft pending G0-Q6)

Severity classes and minimum contents are fixed by
`config/quality-gates/v1.yaml` (critical/major/minor per SPEC FND-005).
Reason codes are stable identifiers of the form `SEV-<class>-<slug>`.
Critical errors, failed deterministic invariants and missing/unknown
policy inputs block release. Severity fixtures land with VER-001/
EVAL-002; alert severity mapping (Sev1/Sev2/Sev3) is OPS-002.
