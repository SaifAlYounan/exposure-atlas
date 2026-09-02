# Evaluation governance (EVAL-000) — frozen before prompt/model development

Status: **frozen, v1.0.0** (2026-09-02). Authoritative machine copy:
`config/eval/governance.yaml` (validated by
`schemas/domain/eval-governance.schema.json`); executable rules in
`packages/python/atlas/evalgov.py`; per-item shape in
`schemas/domain/eval-item.schema.json`.

This document freezes how the pilot is evaluated **before** any prompt or
model development, so prompt/rubric authors cannot tune against the answers.
It implements SPEC §9 EVAL-000. Nothing here calls a runtime model or
touches the network (A0/A1 scope); runtime-model use on real documents
remains A2 and ungranted.

## Data partitions and one-time assignment

Four partitions, physically/access-separated:

| Partition | Purpose | Labels visible to authors? |
|---|---|---|
| `examples` | teaching examples, freely shown | yes |
| `development` | building prompts/rubrics | yes |
| `calibration` | blinded tuning of thresholds | no (blinded) |
| `held_out` | final answer keys | **no — never to runtime, release, or the builder** |

Assignment is a **one-time, deterministic** function of the item key and a
frozen salt (`sha256_bucket`), so re-running assignment can never move an
item between partitions — held-out items cannot leak into development. See
`evalgov.assign_partition`.

## Held-out access control

`holdout_access.runtime_can_read_labels` is pinned `false`. Only the operator
may read held-out labels/answer keys; runtime workers, the release bot, and
the builder are all denied (`evalgov.can_read_holdout` returns true only for
`operator`). Answer keys live outside any automated read path — not in the
repository and not in job payloads.

## Single adjudicator (disclosed)

One human adjudicator: **Alexios**. This limitation is disclosed. No model,
and no separate model family, counts as a second human; agreement among
models never substitutes for a human and never satisfies a G2 operator
decision.

## Blinded ordering and reconsideration

For blinded (`calibration`/`held_out`) items, the operator commits the
initial label **before** any model votes are revealed
(`label_commit.committed_at ≤ votes_revealed_at`; enforced by
`evalgov.blinded_ordering_ok` and required by the item schema). A later
**same-operator reconsideration** is retained separately
(`reconsideration.retained_separately: true`) and is **not** dual
adjudication.

## Evaluation item per stage

One item type per stage (`eval-item.schema.json`):

- **discovery** — a known eligible/ineligible matter within a frozen
  source/time snapshot;
- **boundary** — a candidate plus authoritative document set and adjudicated
  criterion outcomes;
- **extraction** — a document/matter with atomic expected propositions,
  acceptable anchors and modalities;
- **identity** — a candidate-to-matter/relationship decision;
- **classification** — a pinned facts revision plus acceptable
  labels/abstention;
- **monitoring** — a prior/current source-state pair with expected detected
  change and latency;
- **end_to_end** — a candidate expected to `publish`, `abstain`, `exclude`
  or `await_primary`.

## Pre-registered metrics, severity, and underpowered slices

Each stage pre-registers its metrics and error-severity codes
(`stage_metrics` in the config). A slice with fewer than
`min_items_supported` adjudicated items resolves to the governance
`underpowered_disposition` (`review_only`) and is **never** silently pooled
into an aggregate reliability claim (`evalgov.slice_disposition`).

## No self-certification

Prompt/rubric authors cannot self-certify G2. Certification requires the
**operator** (not an author) acting with the operator's **frozen labels**
AND the operator's **gate decision** (`evalgov.can_certify_gate`;
`self_certification.authors_may_self_certify: false`).

## What this task does and does not settle

- **Does:** freeze the governance framework, partitions, access model, item
  shapes, metrics, and severity — the structure the pilot is measured
  against.
- **Does not:** populate held-out labels (operator-committed later), run any
  model, or grant the G2 gate. The G2 gate decision remains the operator's,
  backed by their frozen labels.
