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

