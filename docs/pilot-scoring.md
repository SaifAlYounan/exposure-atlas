# Pilot-source scoring matrix (FND-007 — desk-based, pending G0-Q2)

Status of every cell: **desk assumption**. No A1 live probe has run; no
legacy dataset exists in the workspace, so the mandatory "share of
legacy records" criterion is **unscoreable** (first-turn difference M1;
G0-Q10). This matrix must be rescored when the legacy dataset arrives
and again with A1 probe evidence.

Scores 1–5 (5 best). Rights defaults are restrictive proposals, not
clearances.

| Source | Type | Access/stability | Doc diversity | Rights clarity | Monitoring | Lang/OCR | User value | Legacy share | Total/30 |
|---|---|---|---|---|---|---|---|---|---|
| CourtListener/RECAP (US federal) | court feed/API (mirror custodian) | 5 | 5 | 4 | 5 | 5 | 5 | unknown | 29 |
| FTC cases & proceedings | regulator, issuer-direct | 4 | 5 | 5 | 4 | 5 | 5 | unknown | 28 |
| UK Find Case Law | court API, issuer-direct | 5 | 4 | 5 | 4 | 5 | 4 | unknown | 27 |
| SEC enforcement | regulator, issuer-direct | 4 | 4 | 5 | 4 | 5 | 4 | unknown | 26 |
| PACER (direct) | court, issuer | 2 | 5 | 3 | 3 | 5 | 5 | unknown | 23 |
| Garante / CNIL | regulator, issuer | 3 | 4 | 3 | 3 | 2 | 4 | unknown | 19 |

Comparison trackers (COV-001 only, never fact sources): GWU AI
Litigation Database + one law-firm AI litigation tracker (exact choice
at COV-001 after rights review).

**Recommendation** (operator decision G0-Q2, contingent on A1
feasibility): jurisdiction US; court adapter CourtListener/RECAP with
the SPEC 2.2 mirror corroboration rule enforced; regulator adapter FTC.
Alternate if issuer-direct court provenance is preferred over volume:
UK Find Case Law. Unchosen sources are backlog entries with triggers;
none is represented as covered.

Per-source operational risk and review-cost notes are in the registry
drafts under `config/sources/`.
