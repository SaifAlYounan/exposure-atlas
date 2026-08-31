# Risk register

Rows 1–13 are the SPEC section 3.1 solo-operator deviations. They are
PROPOSALS until acknowledged at G0 (pack item G0-Q9); on acknowledgement
each receives a decision ID (D-003…) and expiry. `Max auth` is a hard
ceiling while the deferred control is incomplete.

| # | Deferred full control | Interim control | Max auth | Reinstatement | Status |
|---|---|---|---|---|---|
| 1 | Managed KMS/HSM signing + anchored audit chain | Hardware-backed operator signing by A4; external checkpoint copy | A4 | KMS/HSM + Merkle checkpoints before A5 | acknowledged (D-011) |
| 2 | Five reviewer roles + backup approver | One operator; roles distinct in code | A5 (narrow) | Role separation when second human joins | acknowledged (D-011) |
| 3 | Independent security reviewer | Separate-session adversarial subagent through A4 | A4 (named unpaid beta) | External human assessment before A5 | acknowledged (D-011) |
| 4 | Full staging/production IaC | Local + isolated operator-only env at A3; separated beta at A4 | A4 | Reviewed IaC before A5 | acknowledged (D-011) |
| 5 | Separate services/IAM per role | Separate processes, identities, db users, egress in one env | A4 | Separate security domains before A5 | acknowledged (D-011) |
| 6 | Temporal/outbox orchestration | PostgreSQL durable job table | A5 | Outbox/workflow engine on measured trigger | acknowledged (D-011) |
| 7 | Webhooks/tiers/bulk-export tiers | RSS/JSON feeds, one key tier, one pinned export | A4 | Before first paid scope needing them | acknowledged (D-011) |
| 8 | Full reviewer web app | Decision packs + minimal authenticated view | A5 (one operator) | Full workflow when second human | acknowledged (D-011) |
| 9 | Dual adjudication | Model-diverse disagreement signal + later-day same-operator confirmation (never called dual control) | A5 (approved scope) | Second qualified adjudicator | acknowledged (D-011) |
| 10 | 100–150 eval items pre-claim | 30–50 at G2, +10–20/month | A4 (named approved scope) | Per-slice thresholds; G6 evidence for automation | acknowledged (D-011) |
| 11 | All 22 runbooks rehearsed | All written; 3 rehearsed before A4; rest automated-tested | A4 | Every Sev1/Sev2 path rehearsed before A5 | acknowledged (D-011) |
| 12 | Load/soak at 2× forecast | Forecast-volume load at named-beta scale | A4 | 2× forecast before A5 | acknowledged (D-011) |
| 13 | (A-001.4) Dual-profile builder conformance | Selected-profile (Claude) conformance only; OpenAI adapter in backlog (HAR-900) | unaffected | A-001.5 trigger | recorded (D-001) |

## Additional current residual risks
| ID | Risk | Interim control | Status |
|---|---|---|---|
| R-14 | Builder runs in managed remote session, not handoff sandbox (M4) | A0 doc/schema scope only; branch-limited git; recorded in D-002 | resolved: accepted for A0–G0, sandbox before G1 (D-013) |
| R-15 | No numeric cost ceilings (M3) | plan-next fails closed; harness session ceilings | resolved: subscription limits are the ceilings; notional ledger caps set (D-009) |
| R-16 | Legacy dataset absent; baseline 0 ≠ 316 (M1) | Migration/baseline tasks blocked_external; §0.3.3 stop honored | held: no dataset exists; migration blocked_external (D-012/D-014) |
| R-17 | Product repo is now PUBLIC (D-025) to enable branch-protection enforcement | Code-only content verified safe (secret scan clean, sources never committed, var/ gitignored); published record JSON + excerpts + controlled material MUST go to a separate access-controlled release-control store (SPEC 5.2/5.3.1), never this repo; a public clone cannot be recalled by later suppression — documented consumer caveat | open — hard constraint enforced by CI canary scan (SEC-09) + review; revisit release-control repo before first records reach a release |
