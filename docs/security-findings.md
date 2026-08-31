# Security findings register

| ID | Finding | Severity | Status | Owner | Evidence |
|---|---|---|---|---|---|
| SEC-INFO-01 | Confinement egress-block VERIFIED in production: live-fetch run 33445968310 blocked `release-assets.githubusercontent.com` (setup-uv download) — an un-allowlisted host — proving harden-runner block mode enforces the pilot-host allowlist. No live fetch occurred (job died at dependency install). | informational (positive) | closed | builder | run 33445968310 job logs; ADR-0002 R3 |
| (none open) | | | | | |

Adversarial-security-reviewer sessions append here. This register is
never edited destructively; findings are closed with disposition rows.
