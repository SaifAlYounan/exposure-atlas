# Fuzzy match proposals (ID-002)

Uses normalized party **names, forum, dates and titles only** to *propose*
possible duplicates/relations — advisory input to human review. Engine:
`packages/python/atlas/fuzzy.py`; proposals use the existing
`identity-match-proposal` schema. Pure, deterministic, A0 — no network,
credentials, or model calls. Model-scored variants are out of scope (A2).

## What it does — and never does

- Emits an `IdentityMatchProposal` with `match_kind: fuzzy`, the `features`
  used, the `rule_version` (`fuzzy-rules/v1`), and a `score`.
- **Never auto-merges.** The module holds no resolver state and writes
  nothing; generating proposals is read-only. An incorrect proposal cannot
  mutate any record identity.
- An accepted proposal is applied **only** as a typed, reversible
  `RecordRelationship` (`atlas.identity.make_relationship`,
  `reversible: true`) — so merge / split / link stay reversible.

## Scoring (float-free)

`score` and numeric features are emitted as **decimal strings** (the
canonical serializer forbids floats). Features: `name_jaccard`,
`title_jaccard`, `forum_match` (bool), `date_gap_days` (int). Weighted score
= 0.55·name + 0.20·title + 0.15·forum + 0.10·date-closeness, in [0,1].
Proposals are emitted only at/above `PROPOSE_THRESHOLD` (0.5000); everything
else yields no proposal. Names are normalized by lowercasing, stripping
punctuation and organisation suffixes (Inc, LLC, Corp, Ltd, …).

## Acceptance (SPEC §9 ID-002) → tests

- Every fuzzy result enters review → `test_proposal_above_threshold_validates_and_is_fuzzy`,
  `test_propose_matches_sorted_and_advisory_only`.
- Incorrect-match fixtures cannot mutate record identity →
  `test_incorrect_match_cannot_mutate_record_identity`.
- Merge/split/link reversible →
  `test_accepted_proposal_applies_only_as_reversible_relationship`.

## Not settled here

The operator reviews and decides every proposal; acceptance is a separate,
reversible relationship, never an automatic merge. `rule_version` is
persisted so a scoring change is traceable and could trigger re-review.
