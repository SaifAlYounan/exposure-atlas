# A2 decision pack — pilot processing / runtime-model core (immutable manifest)

Created 2026-09-02 by the builder coordinator under A0. Answer in
`2026-A2-model-core-answers.yaml` (new decision IDs D-031+). Est. ≈60 min.

**Why now.** The G2 A0 lane is complete and merged: evaluation governance
(EVAL-000), boundary rubric (TRIAGE-001), identity (ID-001 exact, ID-002
fuzzy), the full human-review workflow (REV-001…005) and the idempotent
importer (MIG-002). Both pilot sources meet SRC-004-80 live acceptance
(FTC 8/8, CL 10/10). Test suite: **279 green**; every task carries a
CI-backed, non-self-asserted receipt.

**The boundary.** Everything left in G2 — AI-001/002/003 (provider-neutral
model gateway, prompt/rubric/taxonomy registries, long-document evidence
planner), TRIAGE-002 (blind proposal runners), EXT-001/002 (atomic
extraction, semantic support), CLASS-001 (classification ensemble) and
ROUTE-001 (publication-policy routing) — is the model-execution core. Per
SPEC §0.6 and §11.9, **runtime-model processing on real documents requires
the exact A2 scope**, which is ungranted. A2 is a separate written operator
decision; the builder will not cross it.

## What A2 authorizes (SPEC §0.6)

> A2 — Pilot processing: approved pilot ingestion and runtime-model
> processing in the isolated pilot environment; decision packs. **Excludes**
> deployment to any externally reachable reader.

Standing limits that remain regardless: no model writes accepted facts,
decisions or releases; a model reading source text gets no shell/browser/
storage-write/publication/network tools; **agreement among models never
satisfies a G2 operator decision** (§8.7 / §11.9); runtime models are
qualified only for shadow/routing use at G2.

## What the builder proposes to build once A2 is granted

1. **AI-001 gateway** — approved providers + **exact snapshot IDs** (aliases
   like `latest`/`opus` forbidden, §0.1.16 / §5); structured-output schema
   enforcement; budgets, timeouts, retry rules; full run provenance
   (input/prompt/rubric hashes, exact snapshot, no-tool proof, rights
   pre-call result, cost receipt, held-out isolation — §11.9 receipt).
2. **AI-002/003, TRIAGE-002, EXT-001/002, CLASS-001, ROUTE-001** on that
   gateway, each with strict schemas and held-out isolation.
3. **Execution stays gated per run**, exactly as live-fetch was for A1: model
   calls on real documents run only inside the operator-approved isolated
   pilot environment, and the builder returns for the final "activate"
   confirmation before the first real-document call.

## Questions only the operator can answer

| Item | Question | Proposed | Est. min |
|---|---|---|---|
| A2-Q1 | Grant A2 (approved pilot ingestion + runtime-model processing in the isolated pilot environment), keeping "no external reader" excluded? | Operator to decide | 10 |
| A2-Q2 | Name the **approved model provider(s) and exact snapshot identifiers** for runtime use (no aliases). This is a missing-workspace-input the builder cannot choose (§0.7). | Operator to name | 15 |
| A2-Q3 | Set runtime-model **budgets/timeouts/retry + spend caps** (per-call, per-pack, per-day). `config/budgets.yaml` fails closed while null. | Operator to set | 10 |
| A2-Q4 | Confirm **shadow/routing only** at G2 — models never write accepted facts/decisions; model agreement never satisfies a G2 decision. | Confirm | 5 |
| A2-Q5 | Confirm the **isolated pilot environment + credential handling**: reuse the ADR-0002 confinement, add the model-API host to the egress allowlist, and provision the model API key as an operator-held protected-environment secret (as with `CL_API_TOKEN`). | Operator to confirm | 10 |
| A2-Q6 | Confirm the **held-out isolation prerequisite** (EVAL-000): runtime credentials cannot read held-out labels; no qualification claim before the EVAL corpus (EVAL-001) exists. | Confirm | 5 |
| A2-Q7 | Confirm the **rights pre-call gate**: no real document is sent to a model unless its rights/personal-data state permits it (internal-only is fine for internal shadow); a failing axis fails closed. | Confirm | 5 |
| A2-Q8 | Confirm **data-handling** for sending real documents to the provider — acceptable under the provider's terms/retention, or require a zero-retention/no-training endpoint. | Operator to specify | 5 |

If you decline A2, the builder holds: the A0 half of G2 stands complete and
green, and no runtime model touches a real document. Declining any of
A2-Q2/Q3/Q5 individually blocks only the parts that depend on it; the builder
will say so rather than dilute the requirement.
