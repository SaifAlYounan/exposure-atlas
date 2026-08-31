# Security findings register

| ID | Finding | Severity | Status | Owner | Evidence |
|---|---|---|---|---|---|
| SEC-INFO-01 | Confinement egress-block VERIFIED in production: live-fetch run 33445968310 blocked `release-assets.githubusercontent.com` (setup-uv download) — an un-allowlisted host — proving harden-runner block mode enforces the pilot-host allowlist. No live fetch occurred (job died at dependency install). | informational (positive) | closed | builder | run 33445968310 job logs; ADR-0002 R3 |
| SRC-FIND-01 | CourtListener /opinion/<id>/ HTML view returns HTTP 202 with empty body to the probe; discovery (v4 search API) works but document acquisition must use the CL API opinion endpoint (JSON plain_text/html) or the storage.courtlistener.com PDF, with issuing-court corroboration (mirror custodian, SP-05). lead_id also needs the v4 result id field. | informational | open — next follow-up PR (probe->query-library/ledger wiring + CL API acquisition) | builder | run 33448842013 probe-summary |
| (none open) | | | | | |

Adversarial-security-reviewer sessions append here. This register is
never edited destructively; findings are closed with disposition rows.
