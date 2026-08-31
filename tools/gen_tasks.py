#!/usr/bin/env python3
"""Generate plan/tasks.yaml from the SPEC.md section 8.5/9 catalogue
(BOOT-080 / PLAN-001).

Post-A-001 (decision D-001): HAR-004*, HAR-006* struck; dependencies on
struck IDs are rewritten to the selected-profile equivalent (HAR-005 for
HAR-006-03/-04 evidence roles) per A-001.2.

Decomposition rule (SPEC 8.3): epics are materialized as single nodes
carrying their section 9 acceptance; a node that cannot fit one bounded
builder session is split mechanically into -01..-05 children AT TASK
START by artifact/acceptance group without changing scope. Atom IDs the
section 8.5 edge catalogue names explicitly are materialized now.
G6 per-slice -60 atoms are created per approved slice (none exists).
The A-001.5 backlog row (OpenAI adapter/parity) is a `backlog` node.
"""
import pathlib
import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent

# id: (title, deps, gate, auth_min, executor, requires_op_decision,
#      decision_ids, status, blocked_reason)
T = {}


def add(tid, title, deps, gate, auth="A0", role="implementer", req_dec=False,
        dec_ids=(), status="pending", blocked="", inputs=(), notes=""):
    T[tid] = dict(title=title, deps=list(deps), gate=gate, auth=auth,
                  role=role, req_dec=req_dec, dec_ids=list(dec_ids),
                  status=status, blocked=blocked, inputs=list(inputs),
                  notes=notes)


# ---- G0 / bootstrap -------------------------------------------------
add("BOOT-000", "Record A0 decision, workspace manifest, selected SDK adapter",
    [], "G0", role="coordinator", req_dec=True, dec_ids=["D-002", "G0-Q7"],
    status="in_progress",
    notes="D-002 recorded; D-009 ceilings: operator subscription limits + notional ledger caps 25/75 USD")
add("BOOT-010", "Capture repository/deployment fingerprint", ["BOOT-000"],
    "G0", status="in_progress")
add("BOOT-020", "Count, canonical-export and hash the legacy dataset",
    ["BOOT-010"], "G0", status="in_progress",
    notes="baseline_record_count=0 recorded from inventory (docs/baseline.md); "
          "mismatch vs expected 316 keeps migration blocked (D-012/D-014)")
add("BOOT-030", "Create and verify restorable backup receipt",
    ["BOOT-010", "BOOT-020"], "G0", status="in_progress",
    notes="Git-remote backup receipt + non-destructive restore check "
          "(docs/baseline.md); dedicated target is OPS-003 scope (D-012)")
add("BOOT-040", "Task, decision and evidence-receipt schemas", ["BOOT-000"],
    "G0", status="in_progress")
add("BOOT-050", "Implement task-verify, gate-verify, plan-next", ["BOOT-040"],
    "G0", status="in_progress")
add("BOOT-080", "Generate full plan/tasks.yaml from section 9 catalogue",
    ["PLAN-001", "BOOT-050"], "G0", status="in_progress")

for i, extra in [("000", ""), ("001", ""), ("002", ""), ("003", ""),
                 ("005", "")]:
    pass  # HAR contract atoms added below explicitly

add("FND-000", "Create reversible baseline", ["BOOT-010", "BOOT-020", "BOOT-030"],
    "G0", status="in_progress",
    notes="Baseline = seed commit 4b1e287; restore check passed (docs/baseline.md)")
add("FND-001", "Repository and deployment inventory", ["BOOT-010"], "G0",
    status="in_progress")
add("FND-002", "Legacy record inventory / migration-ledger seed",
    ["FND-000", "FND-001"], "G0", status="in_progress",
    notes="Empty ledger reconciles to baseline_record_count 0 (D-012/D-014)")
add("FND-003", "Versioned boundary manifest", ["FND-001"], "G0",
    req_dec=True, dec_ids=["G0-Q1"], status="in_progress",
    notes="Approved by D-003")
add("FND-004", "Source and proposition policy matrix", ["FND-003"], "G0",
    req_dec=True, dec_ids=["G0-Q3"], status="in_progress",
    notes="Approved by D-005")
add("FND-005", "Terminology, severity and quality policy", ["FND-003"], "G0",
    req_dec=True, dec_ids=["G0-Q5", "G0-Q6"], status="in_progress",
    notes="Approved by D-007/D-008")
add("FND-006", "Threat model and rights policy", ["FND-001", "FND-004"], "G0",
    req_dec=True, dec_ids=["G0-Q3", "G0-Q4"], status="in_progress",
    notes="Approved by D-005/D-006")
add("FND-007", "Pilot selection (scored matrix)",
    ["FND-002", "FND-003", "FND-004", "FND-006"], "G0",
    req_dec=True, dec_ids=["G0-Q2"], status="in_progress",
    notes="Approved by D-004"
            "operator decision G0-Q2")

HAR01 = ["HAR-000-01", "HAR-001-01", "HAR-002-01", "HAR-003-01", "HAR-005-01"]
for hid, htitle in [
        ("HAR-000-01", "Supervisor contract (solo scale, A-001.3)"),
        ("HAR-001-01", "Sandbox and capability-broker contract"),
        ("HAR-002-01", "Role/tool policy configuration contract"),
        ("HAR-003-01", "Claude Agent SDK adapter contract"),
        ("HAR-005-01", "Evidence/transcripts/budgets/completion contract")]:
    add(hid, htitle, ["FND-001", "FND-006"], "G0", status="in_progress")

add("PLAN-002", "Infrastructure and cryptography ADR",
    ["FND-006", "FND-007"] + HAR01, "G0", req_dec=True,
    dec_ids=["G0-Q9"], status="in_progress",
    notes="Approved by D-011")
add("PLAN-001", "Materialize and validate dependency DAG",
    ["FND-007", "PLAN-002"], "G0", status="in_progress")

# ---- G1 -------------------------------------------------------------
add("PLT-001", "Project boundaries and root commands",
    ["PLAN-001", "PLAN-002", "HAR-000-01"], "G1")
add("PLT-002", "Local infrastructure (PostgreSQL, MinIO, worker, telemetry)",
    ["PLT-001", "PLAN-002"], "G1")
add("PLT-003", "Typed configuration and least-privilege secrets",
    ["PLT-001", "FND-006"], "G1")
add("HAR-000-03", "Supervisor minimal implementation",
    ["HAR-000-01", "PLT-001", "PLT-003"], "G1")
add("HAR-001", "External sandbox and capability broker (solo scale)",
    ["HAR-001-01", "HAR-000-03", "PLAN-002", "FND-006"], "G1")
add("HAR-002", "Compiled role/tool policy (config/ versioned)",
    ["HAR-002-01", "HAR-000-03", "HAR-001"], "G1")
add("HAR-003", "Claude Agent SDK adapter",
    ["HAR-003-01", "HAR-000-03", "HAR-001", "HAR-002"], "G1")
add("HAR-005", "Builder evidence, transcripts, budgets and completion",
    ["HAR-005-01", "HAR-003", "PLT-003"], "G1",
    notes="A-001.2: HAR-004 dependency struck; selected-profile only")
add("BOOT-060", "Qualify host sandbox and Claude adapter",
    ["HAR-000-03", "HAR-001", "HAR-003"], "G1")
add("BOOT-070", "Selected-adapter conformance vs full fixture set",
    ["BOOT-060", "HAR-003", "HAR-005"], "G1",
    notes="A-001.2 rewrite: HAR-004/HAR-006-03 deps replaced by HAR-005")
add("PLT-004", "CI baseline", ["PLT-001", "PLT-003", "BOOT-070"], "G1")
add("DOM-001", "JSON Schema package",
    ["PLT-001", "FND-003", "FND-004", "FND-005"], "G1")
add("DOM-002", "Database schema and repositories", ["DOM-001", "PLT-002"], "G1")
add("DOM-003", "Audit ledger and durable job table", ["DOM-002"], "G1")
add("DOM-004", "State machines and property tests", ["DOM-001", "DOM-002"], "G1")
add("DOM-005", "Record revision manifest", ["DOM-002", "DOM-004"], "G1")
add("DOM-006", "Public projection contracts", ["DOM-001", "DOM-005", "FND-005"], "G1")
add("POL-001", "Central policy-decision service",
    ["DOM-001", "DOM-002", "FND-004", "FND-005", "FND-006"], "G1")
add("MON-000", "Monitoring target and overlay primitives",
    ["DOM-001", "DOM-002", "FND-005"], "G1")
add("COR-000", "Signed suppression/revocation overlay",
    ["DOM-001", "DOM-002", "POL-001", "MON-000"], "G1")
add("SRC-001", "Adapter SDK and source registry",
    ["DOM-001", "DOM-002", "FND-004", "FND-006", "PLT-002"], "G1")
add("SRC-002", "Secure streaming fetch", ["SRC-001", "PLT-003", "FND-006"], "G1")
add("SRC-003", "Rights-gated archive interface",
    ["SRC-001", "POL-001", "FND-006"], "G1")
add("DOC-001", "Canonical PDF/HTML pipeline",
    ["SRC-002", "DOM-001", "DOM-002", "FND-006"], "G1")
add("DOC-002", "Durable anchor resolver", ["DOC-001", "DOM-001", "DOM-002"], "G1")
add("DOC-003", "Translation artifact or explicit pilot exclusion",
    ["DOC-001", "DOC-002", "FND-003", "FND-006"], "G1")
add("VER-001", "Pure deterministic verifier",
    ["DOC-002", "DOM-001", "POL-001", "FND-004", "FND-005"], "G1")
add("VER-002", "Manual assertion and approval path",
    ["VER-001", "DOM-003", "DOM-004", "DOM-005", "POL-001"], "G1")
add("REL-000", "Reproducible fixture release",
    ["VER-002", "DOM-006", "MON-000", "COR-000"], "G1")
add("API-000", "Minimal fixture read path", ["REL-000", "DOM-006"], "G1")
add("SEC-001-01", "Security test suite — core hostile fixtures",
    ["HAR-005", "REL-000", "SRC-002", "DOC-001", "DOM-006", "API-000"], "G1",
    notes="A-001.2 rewrite: HAR-006-04 dep -> HAR-005 + REL-000 determinism")

# ---- G2 -------------------------------------------------------------
add("EVAL-000", "Freeze evaluation governance",
    ["DOM-001", "FND-003", "FND-004", "FND-005", "FND-006", "HAR-005"], "G2",
    notes="A-001.2 rewrite: HAR-006-03 dep -> HAR-005")
add("SRC-004", "Implement approved pilot adapters (fixtures)",
    ["SRC-001", "SRC-002", "SRC-003", "FND-007", "EVAL-000"], "G2")
add("SRC-004-80", "Pilot adapter live probes and staging smoke",
    ["SRC-004"], "G2", auth="A1", status="blocked_authorization",
    blocked="Requires written A1 decision")
add("DISC-001", "Candidate ledger", ["DOM-002", "DOM-003", "SRC-001"], "G2")
add("DISC-002", "Versioned query library", ["FND-003", "FND-007", "DISC-001"], "G2")
add("ID-001", "Exact identity resolution", ["DOM-002", "DISC-001"], "G2")
add("ID-002", "Fuzzy match proposals", ["ID-001"], "G2")
add("TRIAGE-001", "Boundary rubric and checklist",
    ["FND-003", "FND-005", "EVAL-000", "DOC-002"], "G2")
add("AI-001", "Provider-neutral model gateway",
    ["HAR-005", "DOM-001", "PLT-003", "FND-006", "EVAL-000"], "G2",
    notes="Runtime model calls require A2 scope; build/fixture work is A0")
add("AI-002", "Prompt, rubric and taxonomy registries",
    ["DOM-001", "FND-003", "FND-005", "EVAL-000"], "G2")
add("AI-003", "Long-document evidence planner",
    ["DOC-001", "DOC-002", "AI-002"], "G2")
add("TRIAGE-002", "Independent proposal runners",
    ["TRIAGE-001", "AI-001", "AI-002"], "G2")
add("EXT-001", "Structured atomic extraction",
    ["AI-001", "AI-002", "AI-003", "VER-001"], "G2")
add("EXT-002", "Semantic support assessment", ["EXT-001", "AI-001", "AI-002"], "G2")
add("CLASS-001", "Classification ensemble",
    ["AI-001", "AI-002", "DOM-005", "FND-005"], "G2")
add("ROUTE-001", "Unified publication-policy routing",
    ["POL-001", "TRIAGE-002", "EXT-001", "EXT-002", "CLASS-001"], "G2")
add("EVAL-001", "Populate partitioned corpora",
    ["EVAL-000", "SRC-004", "ID-002", "TRIAGE-002", "EXT-002", "CLASS-001"], "G2")
add("EVAL-002", "Stage-specific metrics", ["EVAL-001"], "G2")
add("EVAL-003", "Regression dependency map",
    ["EVAL-000", "PLT-004", "AI-002", "VER-001"], "G2")
add("EVAL-004", "Adjudication and error policy",
    ["EVAL-001", "EVAL-002", "FND-005"], "G2", role="implementer",
    req_dec=True, dec_ids=["G0-Q6"])
add("REV-001", "Queue model and priorities",
    ["DOM-002", "DOM-003", "DOM-004", "POL-001"], "G2")
add("REV-002", "Review-task builder", ["REV-001", "ROUTE-001", "DOC-002"], "G2")
add("REV-003", "Authenticated reviewer actions",
    ["REV-002", "PLT-003", "COR-000"], "G2")
add("REV-004", "Weekly decision pack and transport",
    ["REV-002", "REV-003", "HAR-005"], "G2")
add("REV-005", "Workload calibration", ["REV-004", "EVAL-002"], "G2",
    role="operator", req_dec=True)
add("MIG-001", "Field mapping matrix",
    ["FND-002", "DOM-001", "FND-003", "FND-004", "FND-005"], "G2",
    status="blocked_external",
    blocked="No legacy dataset exists (D-012/D-014); unblocks only via a "
            "future written decision supplying one")
add("MIG-002", "Idempotent importer and ledger",
    ["MIG-001", "DOM-002", "DOM-003", "DOM-005"], "G2")
add("MIG-003", "Representative migration pilot",
    ["MIG-002", "SRC-004", "DOC-002", "VER-002", "REV-003", "EVAL-000"], "G2",
    auth="A2")

# ---- G3 -------------------------------------------------------------
add("SEC-002-01", "Signing with test keys; audit checkpoint verification",
    ["PLAN-002", "PLT-003", "DOM-003"], "G3")
add("REL-001A", "Freeze release input snapshot",
    ["DOM-005", "REV-003", "POL-001", "MON-000", "COR-000"], "G3")
add("REL-001", "Deterministic public projection",
    ["REL-001A", "DOM-006", "POL-001"], "G3")
add("REL-002", "Data PR and release workflow", ["REL-001", "PLT-004", "REV-003"], "G3")
add("REL-003", "Signed release manifest and reproducibility",
    ["REL-002", "SEC-002-01"], "G3")
add("API-001", "Read-only REST v1", ["REL-003", "API-000"], "G3")
add("MCP-001", "Read-only MCP adapter", ["API-001"], "G3")
add("COR-001", "Correction event model",
    ["DOM-001", "DOM-002", "DOM-003", "COR-000"], "G3")
add("COR-002", "Emergency suppression", ["COR-001", "COR-000", "API-000"], "G3")
add("FEED-001", "RSS and JSON change feeds", ["API-001", "COR-001", "COR-002"], "G3")
add("COR-003", "Reviewed correction and notification",
    ["COR-001", "COR-002", "REL-002", "FEED-001"], "G3")
add("MON-001", "Monitoring policy engine", ["MON-000", "FND-003", "FND-005"], "G3")
add("MON-002", "Durable scheduled checks", ["MON-001", "SRC-004", "DOM-003"], "G3")
add("MON-003", "Source/version drift classifier",
    ["MON-002", "DOC-001", "DOC-002", "VER-001"], "G3")
add("MON-004", "Status-change proposal path",
    ["MON-003", "EXT-001", "ROUTE-001", "REV-002"], "G3")
add("COV-001", "Tracker crosswalk and exclusion ledger",
    ["DISC-001", "ID-001", "FND-007"], "G3")
add("COV-002", "Coverage report", ["COV-001", "MON-002", "REL-001A"], "G3")
add("GOV-001", "Privacy, retention and takedown operations",
    ["FND-006", "DOM-002", "COR-000", "COR-002", "REL-001"], "G3")
add("EXPORT-001", "Rights-aware bulk export", ["REL-003", "COR-000", "GOV-001"], "G3")
add("WEB-001", "Public and metrics UI", ["API-001", "DOM-006", "COR-002"], "G3")
add("OPS-001", "Structured telemetry",
    ["PLT-002", "PLT-003", "SRC-004", "AI-001", "MON-002", "REL-002", "API-001"], "G3")
add("OPS-002", "Alert severity and routing", ["OPS-001", "COR-002"], "G3")
add("OPS-003", "Backup and deterministic restoration",
    ["PLAN-002", "DOM-002", "SRC-002", "REL-003", "COR-000"], "G3")
add("PERF-001-01", "Forecast and initial load limits",
    ["OPS-001", "MON-002", "API-001"], "G3")
add("SEC-001-03", "Security suite — full serving-surface coverage",
    ["SEC-001-01", "API-001", "MCP-001", "FEED-001", "EXPORT-001", "WEB-001",
     "MON-004", "COR-002", "GOV-001"], "G3")
add("OPS-004-03", "Automated failure tests and three operator drills",
    ["OPS-002", "OPS-003", "SEC-001-03", "COR-002", "REL-003", "MON-002"],
    "G3", inputs=["operator drill availability"])

# ---- G4 -------------------------------------------------------------
add("PLT-005-04", "Beta deployment configuration (A3/A4)",
    ["PLAN-002", "PLT-004", "SEC-001-03", "SEC-002-01", "OPS-003"], "G4",
    auth="A3")
add("SEC-002-04", "Hardware-backed operator signing and external checkpoint",
    ["SEC-002-01", "PLT-005-04"], "G4", auth="A3",
    inputs=["operator hardware-backed key"])
add("COM-002-04", "Beta reader keys, caps and rate limits",
    ["API-001", "PLT-005-04", "OPS-001", "GOV-001"], "G4", auth="A3")
add("COM-003-04", "Beta reader terms and labels",
    ["COV-002", "FND-005", "GOV-001"], "G4")
add("OPS-005-04", "Operational handoff for beta",
    ["OPS-001", "OPS-002", "OPS-003", "OPS-004-03", "COM-003-04"], "G4")

# ---- migration completion / handoff --------------------------------
add("MIG-004", "Controlled batch migration", ["MIG-003", "REV-005"],
    "handoff", auth="A2", req_dec=True,
    notes="Requires G2 operator decision; capacity-bounded batches")
add("MIG-005", "Final reconciliation of baseline set", ["MIG-004", "FND-002"],
    "handoff")

# ---- G5 -------------------------------------------------------------
add("COM-001", "Source and tracker licensing evidence",
    ["FND-006", "SRC-004", "GOV-001", "COV-002"], "G5", req_dec=True)
add("PLT-005-20", "Staging/production infrastructure as code",
    ["PLT-005-04"], "G5", auth="A4", inputs=["G4 observation evidence"],
    role="time_dependent")
add("SEC-002-20", "KMS/HSM signing", ["SEC-002-04", "REL-003"], "G5", auth="A4")
add("FEED-001-20", "Signed webhooks and per-customer delivery",
    ["FEED-001", "COM-002-04", "COR-003"], "G5", auth="A4")
add("EXPORT-001-20", "Tiered/resumable exports",
    ["EXPORT-001", "COM-001", "COM-002-04"], "G5", auth="A4")
add("PERF-001-20", "Paid-capacity load and soak",
    ["PERF-001-01"], "G5", auth="A4", role="time_dependent",
    inputs=["four monitoring cycles"])
add("COM-002-20", "Customer/API operational controls (paid)",
    ["COM-001", "PLT-005-20", "SEC-002-20", "API-001", "PERF-001-20"], "G5",
    auth="A4")
add("COM-003-20", "Reliance and service documentation (paid)",
    ["COM-001", "COM-002-20", "COV-002", "PERF-001-20", "OPS-005-04"], "G5",
    req_dec=True)
add("OPS-005-20", "Paid-scope operational readiness",
    ["OPS-005-04", "COM-003-20"], "G5", role="time_dependent",
    inputs=["external security report",
            "four-cycle and incident-free observation receipts"])

# ---- backlog (A-001.5) ---------------------------------------------
add("HAR-900", "BACKLOG: OpenAI Agents SDK adapter, conformance and parity "
    "(former HAR-004/HAR-006/5.5.3/11.9)", [], "backlog",
    status="blocked_external",
    blocked="Trigger per A-001.5: Claude harness outage beyond freeze "
            "window, operator-named pricing/terms change, or second builder")


# ---- G1 session-1 progress (managed env per D-017) ------------------
G1_S1 = {
    "PLT-001": "pyproject/uv layout, root make targets (subset); full command set grows with tasks",
    "PLT-004": "GitHub Actions clean-checkout CI: plan-validate, lint, tests, two-build determinism",
    "DOM-001": "19 kernel schemas + registry validation; remaining 5.4 catalogue in later sessions",
    "SRC-002": "content-addressed store, URL/IP/size/MIME guards, fixture adapter mode; live fetch is A1",
    "DOC-001": "HTML + native-PDF canonicalizer v1 with page map; OCR fallback later atom",
    "DOC-002": "byte anchors: exact equality, disambiguation, no empty spans",
    "VER-001": "pure verifier v1: schema/anchor/role-modality/provenance/money; semantic never auto",
    "VER-002": "manual slice passes end-to-end for one PDF + one HTML fixture (no AI)",
    "POL-001": "pure evaluator allow|deny|human_review, fail-closed; single evaluator for all callers",
    "COR-000": "deny-only overlay primitive, test-key marked; outranks release at read path",
    "REL-000": "two-build byte-identical release; tamper + canary fixtures fail builds",
    "API-000": "read path serves signed artifact bytes; suppression first; no_match_is_not_absence",
    "SEC-001-01": "SSRF/private-IP, oversize, MIME-mismatch, canary-leak, tamper fixtures passing",
}
G1_S3 = {
    "DOM-001": "full 5.4 catalogue: 62 strict schemas, positive fixture per schema, universal "
               "unknown-property rejection, conditional requirements (other_detail, "
               "confirmed_out_of_scope needs stored decision)",
    "DOM-005": "facts/record revision manifests immutable-by-construction; lifecycle derived from "
               "append-only events; publication requires release inclusion; classification-only "
               "change reuses facts revision",
    "DOM-006": "RecordDetailV1 (facts/classification never flatten; unreviewed dropped), "
               "CitationBundleV1, citation_check (absence never out-of-scope; pending never "
               "leaks to unauthorized audience), StatsV1 denominators",
    "SRC-001": "adapter protocol + registry schema validation + conformance kit (pagination, "
               "idempotent rediscovery, no accepted-state writes, unregistered host refused)",
    "REL-001A": "ReleaseInputSnapshot pure builder; release manifest binds snapshot+policy versions",
    "DOC-003": "pilot language exclusion: unsupported language routes to awaiting_capability; "
               "no translation path exists to publish unlabelled",
}
for _tid, _note in G1_S3.items():
    T[_tid]["status"] = "in_progress"
    T[_tid]["notes"] = (T[_tid]["notes"] + " | " if T[_tid]["notes"] else "") + "G1-S3: " + _note

G1_S2 = {
    "DOM-002": "PostgreSQL schema+repos: FK integrity, byte-hash dedupe, immutability triggers "
               "(update/delete refused; only supersede pointer mutable); ephemeral-cluster tests",
    "DOM-003": "atomic domain+audit+job single-transaction commit, crash test, DB hash-chained "
               "audit with tamper detection, durable job queue (leases/heartbeats/idempotency/"
               "retry/dead-letter/expired-lease takeover)",
    "DOM-004": "pure transition tables for candidate/revision/verification/job/monitoring; "
               "illegal transitions fail deterministically",
    "MON-000": "monitor-target/check/searched-scope/freshness-overlay schemas; temporal "
               "invariant (failed check never advances success); worst-state aggregation rule v1",
}
for _tid, _note in G1_S2.items():
    T[_tid]["status"] = "in_progress"
    T[_tid]["notes"] = (T[_tid]["notes"] + " | " if T[_tid]["notes"] else "") + "G1-S2: " + _note
for _tid, _note in G1_S1.items():
    T[_tid]["status"] = "in_progress"
    T[_tid]["notes"] = (T[_tid]["notes"] + " | " if T[_tid]["notes"] else "") + "G1-S1: " + _note


def main():
    tasks = []
    for tid, m in T.items():
        epic = tid if len(tid.split("-")) == 2 else "-".join(tid.split("-")[:2])
        # normalize epic pattern LETTERS-DDD
        parts = tid.split("-")
        epic = f"{parts[0]}-{parts[1][:3]}"
        task = {
            "schema_version": "atlas-task/v2.2",
            "id": tid,
            "epic": epic,
            "title": m["title"],
            "depends_on": m["deps"],
            "authorization_min": m["auth"],
            "parallelizable": True,
            "executor_role": m["role"],
            "auditor_role": "verifier_auditor",
            "decision_owner": "operator" if m["req_dec"] else None,
            "exclusive_resources": [],
            "conflicts_with": [],
            "worktree": f"task/{tid}",
            "gate": m["gate"],
            "estimated_builder_sessions": 1,
            "required_inputs": m["inputs"],
            "requires_operator_decision": m["req_dec"],
            "operator_decision_ids": m["dec_ids"],
            "builder_profiles": ["claude"],
            "network_profile": "none",
            "credential_profile": "none",
            "artifacts": [],
            "permitted_writes": [],
            "automated_commands": [],
            "acceptance_checks": [f"SPEC.md section 9 acceptance for {tid}"],
            "evidence_paths": ["plan/evidence.jsonl"],
            "rollback": "discard_task_worktree",
            "status": m["status"],
        }
        if m["blocked"]:
            task["blocked_reason"] = m["blocked"]
        if m["notes"]:
            task["notes"] = m["notes"]
        tasks.append(task)
    header = (
        "# GENERATED by tools/gen_tasks.py (BOOT-080/PLAN-001). Edit the\n"
        "# generator catalogue, not this file, except for status updates\n"
        "# made by the coordinator. Decomposition and struck-task rules\n"
        "# are documented in the generator docstring (A-001 / D-001).\n")
    out = ROOT / "plan" / "tasks.yaml"
    out.write_text(header + yaml.safe_dump(
        {"tasks": tasks}, sort_keys=False, width=100))
    print(f"wrote {out} with {len(tasks)} tasks")


if __name__ == "__main__":
    main()
