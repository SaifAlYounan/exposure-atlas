# Exposure Atlas — decision log

Append-only. Every entry binds a decision to its exact inputs (commit,
file hashes) and records scope and expiry. Authorization grants,
deviations and expiries are recorded here per SPEC.md section 0.3(4).

---

## D-001 — Operator Amendment A-001 (constituting SPEC v2.2)

- **Decision ID:** D-001
- **Recorded:** 2026-08-31 (builder first read-only turn, per CLAUDE.md
  and the operator kickoff message; this write was expressly authorized)
- **Decider:** Alexios (operator), under the specification's own
  authority (SPEC.md "Operator Amendment A-001")
- **Recorded by:** builder coordinator (Claude Agent SDK profile),
  session authorization A0
- **Bound to:**
  - repository commit `4b1e287dbbe865cba0128efbedb05bb645f68870`
  - `SPEC.md` SHA-256
    `6663e17e61a94e8052f017f7d3960e20a329e1487e0878e5e940aed518463723`
- **Decision:** Amendment A-001 is adopted and governs wherever it
  conflicts with the SPEC body. Summary of its operative clauses:
  - **A-001.1 Harness selection.** The Claude Agent SDK is the sole
    qualified builder harness. All dual-profile / `BUILDER_PROFILE=openai`
    / `HARNESS=openai` / "second SDK adapter" language reads as the
    selected profile only. `builder_profiles` is `[claude]`.
  - **A-001.2 Struck.** Task `HAR-004` and all atoms; task `HAR-006` and
    all atoms (including `HAR-006-03`, `HAR-006-04`); section 5.5.3; the
    `HARNESS=openai` and `make harness-parity` commands in sections
    5.5.5, 8.6 and 11.9; the dual-profile requirement inside `BOOT-070`
    and the G1 evidence paragraphs. `BOOT-070` now reads: "Before G1,
    complete conformance qualification of the selected SDK adapter
    against the full fixture set; any unsupported SDK feature is
    supplied by the host control plane." Dependencies on struck tasks
    are satisfied when the selected-profile equivalent passes. Release
    determinism remains governed by `REL-000`/`REL-003`.
  - **A-001.3 Resized.** `HAR-000`–`HAR-002` are implemented at solo
    scale: (a) the operator-provisioned sandbox from the handoff
    checklist, (b) the selected SDK's permission rules, hooks and
    subagent tool restrictions, and (c) builder-written code only for
    the budget ledger, evidence writer, transcript store and completion
    gate. Workspace broker and compiled capability policy collapse into
    versioned configuration under `config/`. `HAR-003` and `HAR-005`
    acceptance criteria apply unchanged; `HAR-005` receipts come from
    clean-checkout CI under an identity the builder cannot read.
  - **A-001.4 Waiver clause struck.** The section 0.8 sentence that no
    operator waiver can replace dual-profile conformance is deleted.
    This amendment is disclosed in the release manifest like any other
    risk acceptance.
  - **A-001.5 Backlog row added** (SPEC backlog table; the amendment
    text cites "section 20", the backlog table in this document is
    section 18 — see the deviation note below): OpenAI Agents SDK
    adapter, conformance run and parity suite (former `HAR-004`,
    `HAR-006`, 5.5.3, 11.9 dual-profile runs). Trigger: a Claude harness
    outage longer than the operator-unavailable freeze window, a pricing
    or terms change the operator names, or the arrival of a second
    builder. Maximum authorization unaffected.
  - **A-001.6 Gate rename.** G1 is "evidence kernel"; its evidence is
    the selected profile's confinement, structured-output,
    failure-completion, transcript and cost normalization, and
    deterministic-release receipts, plus the rest of the G1 catalogue.
- **Scope:** entire build; every struck item is treated as deleted.
- **Expiry:** none (standing amendment). The struck dual-profile work
  survives only as the triggered backlog row in A-001.5.
- **Deviation notes recorded with this entry** (internal reference
  errors in the seeded documents; interpretation recorded here so no
  later reader re-derives it differently):
  - CLAUDE.md and the kickoff message cite "SPEC.md section 0.9" for the
    mandatory first turn; in SPEC v2.2 the mandatory first turn is
    **section 0.7** (bootstrap is 0.8). Interpreted as section 0.7.
  - A-001.5 cites "section 20" for the backlog; in SPEC v2.2 the
    triggered backlog is **section 18**. Interpreted as section 18.
  - Neither reinterpretation changes any obligation; both are flagged in
    the first-turn material-differences report for operator
    confirmation.
- **Status:** recorded

---

*No other decisions are recorded. The written A0 decision itself is
recorded as part of `BOOT-000` once the operator confirms the G0
decision pack; the kickoff message granted A0 for this first turn but
`BOOT-000` requires a signed/attributable decision ID.*

## D-002 — Written A0 confirmation ("Approved")

- **Decision ID:** D-002
- **Recorded:** 2026-08-31
- **Decider:** Alexios (operator), via the builder session channel
- **Decision text:** "Approved", in direct response to the first-turn
  report (commit `efa7689`), which proposed: (a) treating the kickoff +
  this confirmation as the written A0 decision BOOT-000 requires, and
  (b) proceeding with the proposed G0 task list.
- **Recorded scope:** A0 only (SPEC.md section 0.6): local edits,
  schemas, safe fixtures, tests, docs, local stack, baseline capture,
  official builder-SDK documentation. Nothing in this decision grants
  A1+, Atlas live-source access, runtime model calls, deployment or
  publication.
- **Explicitly NOT decided by D-002:** every G0 decision-pack item
  (pack `docs/decision-packs/2026-W36-G0.md`, items G0-Q1…G0-Q14).
  Per the operator handoff (section 5), pack questions are answered in
  one written pack, not chat fragments. FND-003–FND-007, the section 3
  risk acceptances and cost ceilings remain open operator decisions.
- **Known deficiencies recorded with this grant (do not silently cure):**
  - No numeric session/day cost ceilings supplied (kickoff placeholders
    [X]/[Y]). Interim control: the managed session's own harness
    ceilings; `make plan-next` refuses to mark cost-gated tasks ready
    while `config/budgets.yaml` ceilings are null. Formal ceilings are
    pack item G0-Q7.
  - Delivery channel unnamed (pack item G0-Q8).
  - Builder control plane is the managed Claude Code remote environment,
    not the handoff-section-2 sandbox (first-turn difference M4; pack
    item G0-Q11). Accepted here for A0 documentation/schema/fixture
    work only.
- **Expiry:** until the answered G0 pack replaces it or the operator
  revokes it.
- **Status:** recorded


## D-003 … D-016 — G0 decision pack 2026-W36 answered

- **Decision IDs:** D-003, D-004, D-005, D-006, D-007, D-008, D-009,
  D-010, D-011, D-012, D-013, D-014, D-015, D-016
- **Recorded:** 2026-08-31
- **Decider:** Alexios (operator), in one written pack per handoff
  section 5, committed as `c6dcd8028792e002e27fde39c6f60107f82da6fd`
- **Bound to:** `docs/decision-packs/2026-W36-G0-answers.yaml`
  SHA-256 `77bd3442352dd9fc31dc72c43ef9a9132b3413b96e03b0230453ddc80af65d82`
- **Summary (full text in the answers file, which is authoritative):**
  - **D-003 (G0-Q1):** boundary v1 approved as drafted.
  - **D-004 (G0-Q2):** pilot sources CourtListener/RECAP + FTC; GWU
    tracker + one law-firm tracker.
  - **D-005 (G0-Q3):** rights defaults approved: all internal_only,
    archive submission disabled, no excerpts cleared.
  - **D-006 (G0-Q4):** interim personal-data rule adopted.
  - **D-007 (G0-Q5):** nine-category taxonomy v1 approved (multi-label,
    other_detail required).
  - **D-008 (G0-Q6):** severity policy approved; model thresholds stay
    UNSET until the EVAL corpus exists.
  - **D-009 (G0-Q7):** builder runs on the operator's Claude
    subscription; subscription rate limits + session wall-clock are the
    ceilings; notional ledger caps 25/75 USD set in config/budgets.yaml
    for fail-closed accounting; on limit the builder stops and reports.
  - **D-010 (G0-Q8):** channel = Claude Code sessions; packs and stop
    reports committed to this repository and reviewed in-session.
  - **D-011 (G0-Q9):** section 3 risk acceptances (register rows 1–12)
    and ADR-0001 acknowledged as written with stated expiries.
  - **D-012 (G0-Q10):** NO workspace inputs exist outside this
    repository: no legacy dataset, no release-control repo, no backup
    target. Model provider: Anthropic Claude via operator subscription.
    Source allowlist as drafted in config/sources/.
  - **D-013 (G0-Q11):** managed Claude Code environment accepted for
    A0–G0 documentation/schema work; hand off to the
    handoff-section-2 sandbox BEFORE G1 implementation.
  - **D-014 (G0-Q12):** migration remains blocked_external; no
    re-baseline without a separate written decision; operator confirms
    no dataset exists outside this repository.
  - **D-015 (G0-Q13):** D-002 confirmed as the BOOT-000 decision.
  - **D-016 (G0-Q14):** harness confirmed: Claude Agent SDK,
    builder_profiles [claude].
- **Expiry:** boundary/rights/taxonomy/severity decisions stand until
  superseded by a versioned change under SPEC 10.1 change class 2
  (later-day cooling-period confirmation). Risk-acceptance expiries are
  the reinstatement preconditions in docs/risk-register.md.
- **Consequence for the baseline (D-012 + D-014):** the expected-316
  legacy set does not exist; `baseline_record_count` is recorded as
  **0 from actual inventory** per SPEC 0.3(3), the mismatch keeps every
  migration task blocked_external, and no expected-count re-baseline
  occurs without a future written decision.
- **Status:** recorded

## D-017 — Builder environment for implementation gates (amends D-013)

- **Decision ID:** D-017
- **Recorded:** 2026-08-31
- **Decider:** Alexios (operator), via the builder session channel
- **Decision text:** "Just do everything on GitHub, and Claude Code —
  go." The managed Claude Code cloud session environment (as documented
  in docs/as-built.md) plus GitHub-hosted CI is accepted as the builder
  environment for G1 and subsequent implementation gates, superseding
  the D-013 requirement to hand off to the handoff-section-2 sandbox
  before G1.
- **Recorded scope:** implementation work on schemas, code, tests,
  fixtures and CI within A0 authorization. This decision does NOT grant
  A1 or above. The handoff-section-2 sandbox requirement is not
  abolished: it moves to become a precondition of the first written A1
  decision — no live-source access, no runtime model calls on real
  documents, and no ingestion may run in the managed environment.
  Repository remains private; sources are never committed to git
  (SPEC 2.3, line-600 rule).
- **Status:** recorded

## Coordinator note under D-017 (not a decision)

G1 executes in the managed environment per D-017. Clean-checkout CI =
GitHub Actions on this repository; receipts derived from an actual CI
run (run ID + conclusion recorded) are treated as non-self-asserted.
The builder cannot read the Actions identity/token. G1 is planned as
multiple builder sessions (SPEC 14.1 estimates 8–15); each session
commits per task and updates build-status.

## D-018 … D-023 — G1 decision pack 2026-W37 answered

- **Decision IDs:** D-018, D-019, D-020, D-021, D-022, D-023
- **Recorded:** 2026-08-31
- **Decider:** Alexios (operator), one written pack, committed as
  `d89942a`
- **Bound to:** `docs/decision-packs/2026-W37-G1-answers.yaml`
  SHA-256 `07f8307ee0046a3a3e75f3d51de8d03aa293b0d742684008e31446b0450d37d0`
- **Summary (answers file is authoritative):**
  - **D-018 (G1-Q1):** capability report accepted as interim G1 harness
    evidence; full confinement qualification remains a hard A1
    precondition.
  - **D-019 (G1-Q2):** no separate VPS/VM sandbox. Builder must design
    and propose, in the next decision pack, a confinement qualification
    for HAR-001/HAR-003 running entirely on GitHub-hosted
    infrastructure, satisfying the handoff-section-2 intent (no
    personal credentials, deny-by-default egress during live fetching,
    ephemeral hosts, injected scoped secrets) — or state explicitly
    that it cannot be honestly satisfied there. A1 stays blocked until
    the qualification passes.
  - **D-020 (G1-Q3):** PLT-002 deviation accepted; expiry at
    confinement-stack provisioning per D-019.
  - **D-021 (G1-Q4):** A1 granted CONTINGENT — effective only when the
    D-019 qualification closes. Scope: read-only probes of the
    CourtListener API and ftc.gov listing/document pages only; ≤50
    documents/source; conservative rate caps; recorded receipts;
    30-day expiry from effectiveness; no runtime model calls on
    fetched documents.
  - **D-022 (G1-Q5):** kernel→PostgreSQL integration acknowledged as
    first G2 step.
  - **D-023 (G1-Q6):** CI evidence accepted as presented.
- **Status:** recorded. A1 is NOT yet effective; authorization remains
  A0 until the D-019 qualification passes and its pack is approved.

## D-024 … D-027 — G1b decision pack 2026-W38 answered; A1 preconditions met

- **Decision IDs:** D-024, D-025, D-026, D-027
- **Recorded:** 2026-09-01
- **Decider:** Alexios (operator), one written pack
- **Bound to:** `docs/decision-packs/2026-W38-G1b-answers.yaml`
  SHA-256 `1e08058b4c09e23ca109a8e173c6fbb3fea56378d7cf4d84bc62ea46e74b7b1a`
- **Summary (answers file authoritative):**
  - **D-024 (G1b-Q1):** ADR-0002 design + verdict + residuals R1–R3
    approved as the HAR-001/HAR-003 qualification approach.
  - **D-025 (G1b-Q2):** the four R1 controls are SET (not promised). To
    enable enforcement on the plan tier the operator made the
    repository **public** (secret scan first; no credentials/personal
    data tracked; sources never committed). Controls: (1) branch
    protection on main — 1 required review, force-push+deletion
    disabled; (2) require_code_owner_reviews on the committed CODEOWNERS
    paths; (3) protected `live-fetch` environment with the operator as
    required reviewer holding any source credential; (4) environment
    deployment_branch_policy = protected branches only.
  - **D-026 (G1b-Q3):** CourtListener/RECAP REST API terms permit
    read-only programmatic evaluation at ≤50 docs/source with
    conservative caps; FTC pages are US-gov works. Public repo must
    NEVER contain fetched documents (SPEC 2.3) — now a hard constraint.
  - **D-027 (G1b-Q4):** implement SRC-004-80 behind the inert template;
    return for a final explicit operator "activate" confirmation before
    ANY live fetch; the protected environment review is the enforcement
    point.
- **Authorization effect:** the D-021 contingent A1 grant is now
  effective (qualification design accepted, R1 controls set, confinement
  self-test green in CI). Session authorization moves A0 → **A1**.
  **Live fetch execution remains gated** by D-027 (operator "activate"
  confirmation + protected-environment review). No live fetch this turn.
- **New residual (recorded, not silently accepted):** the product repo
  is now public. Acceptable for code, but per SPEC 5.2/5.3.1 published
  record JSON and any controlled/excerpt material must go to a separate
  access-controlled release-control store, NEVER this repo; and a public
  clone cannot be recalled by a later suppression. Tracked as R-17.
- **Status:** recorded

## D-028 — Live-probe activation (D-027 enforcement)

- **Decision ID:** D-028
- **Recorded:** 2026-09-01
- **Decider:** Alexios (operator), explicit: "Activate (D-027): proceed
  with the live probe. Merge that PR on GitHub."
- **Effect:** the D-027 activation gate is satisfied. SRC-004-80 is
  authorized to execute a live probe within the D-021 scope ONLY:
  read-only CourtListener API + ftc.gov pages; ≤50 docs/source;
  conservative rate caps; recorded receipts; NO runtime model calls
  (A2 ungranted); external archive submission stays disabled (D-005).
- **Mechanism (unchanged, not bypassed):** the probe still runs only
  inside the protected `live-fetch` GitHub Environment, which injects
  the activation token after the operator approves that specific run.
  Merging the enabling PR is performed via the operator's own GitHub
  identity (get_me = SaifAlYounan, id 265073165) per the operator's
  instruction; the builder uses no admin force-bypass.
- **Public-repo constraint (R-17) reaffirmed:** the probe writes NO raw
  source bytes to the repository or to any workflow artifact — only
  hashes and metadata; raw bytes stay in the (ephemeral) evidence store.
- **Expiry:** the D-021 30-day A1 window begins at first live probe.
- **Status:** recorded

## Coordinator note under D-028 — enabling PR merged

PR #1 (rename live-fetch.yml.template -> live-fetch.yml + tools/run_probe.py)
merged to main as merge commit `83956939e18a5523363d9bee2b7a45553d36014b`,
performed via the operator's GitHub identity (get_me = SaifAlYounan,
id 265073165) per the operator's explicit instruction. No admin
force-bypass flag was passed to the merge. The live probe still executes
only after the operator approves the protected `live-fetch` environment
deployment (D-027 enforcement point); dispatch queues a run that waits
for that approval.

## D-029 — Overnight delegation to operator's assistant (bounded)

- **Decision ID:** D-029
- **Recorded:** 2026-09-01
- **Decider:** Alexios (operator), via the assistant session channel
- **Decision text:** "Start a watch that just approves everything ...
  Full greenlight and authority." Recorded with the assistant's stated
  carve-outs, which the operator was informed of before this took
  effect.
- **Delegated to the assistant while the operator is away:**
  (a) merging builder PRs the assistant has fully reviewed, provided
  they do not change egress hosts, rate caps, source/rights config
  semantics, or grant new capability; (b) approving live-fetch
  environment deployments strictly within the D-021 probe scope
  (registered pilot sources, <=50 docs/source, read-only); (c) messaging
  the builder session to keep work moving; (d) keeping a written log of
  every action for operator review.
- **Explicitly NOT delegated (queues for the operator):** new
  authorization levels (A2+), decision-pack answers, boundary or source
  expansions, credential provisioning, repository-visibility or
  protection changes, and anything the assistant's own permission gate
  refuses.
- **Expiry:** the operator's next return to the session; at most 24h
  from recording.
- **Status:** recorded

## D-030 — CourtListener API credential wiring (CL acquisition fix)

- **Decision ID:** D-030 (renumbered from a first draft as D-029, which
  collided with the delegation decision the operator landed in commit
  `8231be3`; this entry follows it.)
- **Recorded:** 2026-09-01
- **Decider:** Alexios (operator). Decision relayed to the builder via the
  Atlas transcript bridge session on 2026-09-01: "option 1 + 3.
  CL_API_TOKEN is now set as an encrypted secret on the protected
  live-fetch environment … a real CourtListener token." **This entry is
  landed by the operator's own merge of the PR that carries it; the merge
  is the ratification.** (A relayed peer message does not by itself grant
  escalation; the builder took only in-scope actions — proposing a code
  change via PR — and did not set the secret or alter any
  permission/config.)
- **Delegation boundary (D-029):** the operator's overnight-delegation
  decision D-029 lists **credential provisioning** among the items NOT
  delegated to the assistant. This PR is therefore reserved for the
  **operator** to merge — the delegated assistant must not merge it, and
  it does not fall under the assistant's "no new capability" merge
  authority. The credential was itself provisioned by the operator
  personally (not the assistant), consistent with that boundary.
- **Problem (SRC-FIND-03):** CourtListener v4 DATA endpoints
  (`/api/rest/v4/opinions/…`) return HTTP 401 to anonymous clients; the v4
  SEARCH endpoint serves anonymously. Live run 33471746597 acquired 0/10
  opinions for this reason. Full CL opinion-text acquisition therefore
  needs an authenticated CL API token.
- **What the operator provisioned:** a `CL_API_TOKEN` encrypted secret on
  the protected `live-fetch` GitHub Environment (per the relay, updated
  2026-09-01T15:07:58Z). The builder cannot read the secret's value and
  did not create it.
- **What the builder implements (this PR):** the probe sends
  `Authorization: Token <CL_API_TOKEN>` **only** to CourtListener hosts
  (`www.courtlistener.com`), and the token is **never** written to the
  probe summary, artifacts, or logs — only a boolean `authenticated` flag
  is recorded for diagnosis. The workflow passes the environment secret to
  the probe step as `CL_API_TOKEN`. No new egress host is opened
  (`www.courtlistener.com` was already allowlisted).
- **Scope unchanged:** still A1 read-only acquisition within D-021 caps
  (≤50 docs/source); NO runtime model calls (A2 ungranted); external
  archive submission stays disabled (D-005); R-17 no-raw-bytes reaffirmed.
  CL remains a MIRROR custodian — copy provenance stays 'unverified' until
  corroborated by the issuing court (SP-05).
- **Gate unchanged:** live runs still pause for the operator's `live-fetch`
  environment approval on each dispatch (D-027 enforcement); this PR does
  not bypass it.
- **Status:** proposed — ratified on operator merge of the enabling PR.
