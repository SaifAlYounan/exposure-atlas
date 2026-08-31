# Threat model v1 (FND-006 — draft pending G0-Q3/Q4)

Scope: full SPEC FND-006 threat list. Format: threat → preventive /
detective controls → owning task(s). Runtime-role permission tables are
completed at PLT-003/PLT-005; this version records design commitments.

| Threat | Preventive controls | Detective controls | Tasks |
|---|---|---|---|
| Malicious files (PDF/HTML polyglots, active content) | Isolated unprivileged no-network parser containers; file-signature validation; quarantine-until-assessed; inert rendering | SEC-01..05 fixtures; quarantine metrics | SRC-002, DOC-001, SEC-001 |
| SSRF / DNS rebinding | Scheme+host allowlist; resolved-peer-IP validation at every hop; block private/link-local/metadata ranges | SEC-02 fixture; egress logs | SRC-002, SEC-001 |
| Prompt injection in source text | No-tool runtime models; strict structured output; instruction text inert by design | SEC-01, SEC-07 fixtures | AI-001, SEC-001 |
| Source compromise / drift | Immutable byte versions; drift classifier; supersession requires official metadata or human decision | MON-003 alerts; VER fixtures | SRC-002, MON-003 |
| Parser/OCR failure | Pinned toolchains; new TextArtifact per toolchain change; reproducibility checks | DOC-001 impact reports | DOC-001 |
| Model/provider drift | Exact pinned snapshots; alias ban; fallback detection fails runs | AI-001 run manifests; EVAL-003 | AI-001, EVAL-003 |
| Reviewer (operator account) compromise | WebAuthn/passkey; nonce/expiry-bound decisions; assistant never holds session; deny-only freeze | Audit chain; runbook 20 | REV-003, SEC-002 |
| Secret exposure | No ambient credentials; secret scanning; log redaction | PLT-003/PLT-004 scans | PLT-003, PLT-004 |
| Rights withdrawal / sealing | Deny-only signed suppression overlay outranks releases/caches/backups | COR-002 drills; RGT-04 fixture | COR-000, COR-002, GOV-001 |
| Malicious downstream content (XSS, formula injection) | Escaping everywhere; export neutralization | SEC-06 fixture | WEB-001, EXPORT-001, SEC-001 |
| Release tampering | Signed manifests; two-build determinism; checkpoint outside builder-writable accounts | SEC-13 fixture; REL-003 verify | REL-003, SEC-002 |
| Builder overreach | Host-owned control plane; branch-limited git; completion gate outside model; A-001.3 solo controls | Conformance suite BOOT-060/070 | HAR-001..005 |

Every identified high/critical threat above has at least one preventive
and one detective control; unknown rights and unknown provenance fail
closed everywhere (config/rights/v1.yaml, config/source-policy/v1.yaml).
