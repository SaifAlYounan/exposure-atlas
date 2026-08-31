# ADR-0002: GitHub-hosted confinement qualification for HAR-001/HAR-003

Status: **proposed** (decision D-019). Approved only through the
2026-W38 decision pack. Nothing here grants A1; A1 (D-021) is effective
only once the qualification defined here PASSES and the pack approves it.

## Constraint (D-017, D-019)
No separate VPS/VM. Everything runs on GitHub + Claude Code. This ADR
asks: can the handoff-section-2 confinement *intent* be honestly
satisfied on GitHub-hosted infrastructure, and if not, exactly which
part cannot?

## The handoff-section-2 intent, mapped to GitHub-hosted mechanisms

| Intent | GitHub-hosted mechanism | Honest verdict |
| --- | --- | --- |
| Ephemeral host, destroyed after use | GitHub-hosted Actions runners are a fresh VM per job, discarded at job end | **Fully met** — stronger than the managed session |
| No personal/ambient credential stores | Hosted runners mount no user `~/.ssh`, cloud, or package-manager creds; only `GITHUB_TOKEN` + explicitly configured secrets exist | **Fully met** |
| Deny-by-default egress during live fetching | `step-security/harden-runner` in `block` mode with an allowlist of exactly the pilot source hosts + evidence-vault upload endpoint; blocks 169.254.169.254 and everything else at the netfilter layer | **Met at the OS layer**, layered with the in-code `fetchguard` peer-IP/redirect validation (defence in depth) |
| Injected scoped secrets only to the process that needs them | GitHub **Environment** protection: the live-fetch job targets a protected environment whose secrets are injected only for that job, gated by a required-reviewer rule | **Met, but depends on an operator-only configuration** (see residual R1) |
| Repository-only write scope, protected branches, no force-push | Branch protection on `main`; the builder pushes only its feature branch | **Met** (already in force) |
| Clean-checkout CI under an identity the builder cannot read | GitHub Actions `GITHUB_TOKEN` is job-scoped and unreadable by repo code across jobs | **Met** (already in force) |
| Host policy the active agent cannot modify or disable | **This is the crux.** The builder has write access to the repo, including `.github/workflows/`. On its own branch it *can* edit the confinement workflow. | **Partially met — see residual R1** |

## Residuals (stated explicitly, not diluted — D-019)

**R1 — the agent authored its own confinement workflow.**
HAR-001 acceptance includes "the active agent cannot modify or disable
host policy." A builder with repo write access can edit
`.github/workflows/confinement-fetch.yml` on its branch. This is only
honestly closed by controls **outside the builder's unilateral reach**,
which ONLY THE OPERATOR can set:

1. **Branch protection on `main`** requiring pull-request review, so no
   change to the confinement workflow reaches the ref that runs
   privileged live fetches without operator approval.
2. **CODEOWNERS** making `.github/workflows/**` and `config/sources/**`
   operator-owned, so a PR touching them requires the operator's review
   specifically.
3. **A protected GitHub Environment** (e.g. `live-fetch`) with the
   operator as required reviewer and holding any source credential, so
   the live-fetch job cannot run — even from `main` — without a
   per-run operator approval, and secrets never reach a builder-branch
   job.
4. The live-fetch workflow triggers **only on `main`** (or
   `workflow_dispatch` gated by the protected environment), never on
   `claude/**` branches.

With 1–4 in place, the root of trust for live fetching is the
operator's branch-protection + environment configuration, which the
builder cannot alter from inside a job. **Without them, HAR-001 is NOT
honestly satisfied** and A1 must stay blocked. The builder cannot set
these itself (setting branch protection requires admin the builder does
not and must not hold); they are operator preconditions, enumerated as
pack item G1b-Q2.

**R2 — SDK-internal tool restriction (HAR-003).**
Proving that a restricted Claude Agent SDK subagent genuinely cannot
call an omitted tool requires running the SDK under the policy and
observing the denial. This is scriptable in an Actions job that spawns a
restricted subagent and asserts the denial; it does not need a VM. The
host-supplied substitutions (completion gate, budget ledger, role-policy
compilation, evidence receipts) are already qualified by the existing
suite. The SDK-internal denial fixtures are added by
`builder/conformance/sdk_denial_fixtures/` and run in the confinement
workflow. Verdict: **feasible on GitHub-hosted infra.**

**R3 — DNS rebinding at the OS layer.**
harden-runner allowlists by domain and re-resolves; the in-code
`fetchguard.validate_peer_ip` must still run on the actually-connected
socket at every redirect hop. Both layers are required; neither alone is
claimed sufficient. Verdict: **met by the two layers together.**

## Overall verdict
HAR-001 and HAR-003 **can be honestly qualified on GitHub-hosted
infrastructure**, conditional on the operator setting the four R1
controls (branch protection, CODEOWNERS, protected `live-fetch`
environment, main-only trigger). The builder implements the workflow,
fixtures and in-code layers; the operator supplies the root-of-trust
configuration the builder must not hold. If the operator declines any
of R1.1–R1.4, the honest consequence is that A1 live fetching cannot be
authorized on this infrastructure, and the builder will say so rather
than proceed.
