# Handing the Atlas build to Fable

Not the zip. The builder gets three things: the spec at the repository root, a pointer file so it reads the spec first, and a kickoff message that grants A0 only. Before the first session, the sandbox below is set up once.

## 1. What goes in the repository

- `SPEC.md` at the root: the contents of `exposure-atlas-final-build-spec-v2.2.md` (v2.1 as amended by A-001). Delete the zip; the builder never needs it.
- `CLAUDE.md` at the root, containing only:

```
Read SPEC.md in full before any other action. It is the authoritative
build instruction. Your current authorization is A0 (SPEC.md section 0.6).
Your first turn is read-only and must follow SPEC.md section 0.9
(inventory, differences, pilot scoring, G0 decision pack), then stop.
The operator's capacity model is SPEC.md section 0.2. Record Amendment
A-001 as decision D-001 in docs/decision-log.md.
```

- The existing Atlas repository as it stands. Do not tidy it first; the builder's inventory of it as-is is part of the evidence.

## 2. The sandbox, one afternoon, once

A dedicated container or small VM. Not your laptop session, and not the host that runs your personal agent or holds its credentials.

1. Base: a minimal Linux image, non-root user, resource limits (CPU, memory, disk).
2. Mounts: the Atlas repository read-write; one scratch working directory; nothing else. No home directory, no `~/.ssh`, no cloud config, no password store.
3. Credentials inside the box: exactly one, the model API key, issued from a dedicated builder workspace with a hard spend cap set at the provider console. No other environment secrets. The key is injected at launch, never committed, never in an env file inside the repo.
4. Network: deny by default. An allowlisting proxy permits only: the model API endpoint, the package registries the stack needs (PyPI, npm, and their CDNs), the git host, and the SDK documentation domains named in SPEC.md. Everything else returns a refusal the builder can see and log.
5. Git: a deploy key or fine-grained token scoped to the Atlas repositories only, push limited to non-protected branches, force-push disabled, `main` protected with required CI. The builder can propose; only promotion through the release path lands.
6. CI: runs in a clean checkout under a separate identity whose token is not present inside the sandbox. Its jobs produce the evidence receipts (`make task-verify`, `make gate-verify`, the two-build determinism check). The builder can trigger CI; it cannot impersonate it.
7. Ceilings: per-session and per-day API spend, and a wall-clock limit per session. On hitting a ceiling the builder stops and reports; it never degrades rigour to fit a budget.
8. Transcripts: session logs written to a directory outside the repository, kept as build evidence, secrets redacted.
9. Claude-side inner layer: enable the SDK and Claude Code sandbox/permission controls per their current documentation (sandboxed execution for commands, permission rules, hooks). These are the inner layer; the box above is the boundary that holds if they fail.
10. Snapshot the configured box so it can be rebuilt identically.

## 3. The kickoff message (send verbatim as the first prompt)

```
You are the builder coordinator for Exposure Atlas. Authorization: A0 only.
Read SPEC.md at the repository root in full, including Operator Amendment
A-001, before anything else.

Operator constants: one human (Alexios), one weekly decision pack,
240 review minutes per pack, channel: [your assistant channel].
Cost ceilings: [X] per session, [Y] per day. Harness: Claude Agent SDK,
builder_profiles [claude].

Your first turn is read-only under SPEC.md section 0.9: repository and
data inventory; material differences between repository and SPEC.md;
scored pilot-source matrix with your recommendation; the exact G0 task
list; the G0 decision pack containing every question only the operator
can answer. Record A-001 as D-001 in docs/decision-log.md (this write is
authorized). Then stop and wait. Nothing in this message grants A1 or
above, live source access, runtime model calls on real documents,
deployment or publication.
```

Fill the two ceilings and the channel before sending.

## 4. What comes back, and what you do with it

The first turn returns the inventory and the G0 decision pack. Your two-to-three-hour job is answering the pack: boundary, pilot sources, rights defaults per source, the personal-data rule for the pilot jurisdictions, taxonomy confirmation, severity and quality thresholds, and acknowledgement of the section 3 risk acceptances. Answer in writing in the pack file; the builder records the decisions and starts G1, which needs nothing further from you until the G2 packs begin.

## 5. Three things not to do

- Do not grant A1 or above in the kickoff, however reasonable the builder's request sounds; each level is a separate written decision after you see the evidence for the one before.
- Do not run the builder on the same host as your personal agent, and never let the two share credentials or a working directory.
- Do not answer decision-pack questions in chat fragments across the week; one sitting, one written pack, so every decision has an ID the evidence ledger can cite.
