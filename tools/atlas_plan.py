#!/usr/bin/env python3
"""Atlas plan tooling (BOOT-050).

Subcommands:
  validate               -> schema + DAG validation of plan/tasks.yaml
  next                   -> list ready tasks per SPEC.md section 8.3 rules
  task-verify TASK       -> verify evidence receipt(s) for a task at HEAD
  gate-verify GATE       -> emit machine-readable gate manifest; exit 1 on fail
  build-status           -> regenerate docs/build-status.md from the ledger

Fail-closed rules implemented here:
  - missing/wrong-commit evidence fails task-verify;
  - self-asserted receipts never satisfy gate-verify;
  - null cost ceilings block plan-next for every task (G0-Q7 open);
  - requires_operator_decision without a recorded decision blocks readiness;
  - only this host tooling reports done-eligibility; a task file status of
    "done" without verified evidence is itself a validation error.
"""
import argparse
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys

import yaml
from jsonschema import Draft202012Validator

ROOT = pathlib.Path(__file__).resolve().parent.parent
TASKS = ROOT / "plan" / "tasks.yaml"
EVIDENCE = ROOT / "plan" / "evidence.jsonl"
SCHEMA_DIR = ROOT / "schemas" / "plan"
GATE_DIR = ROOT / "plan" / "gate-manifests"
AUTHZ = ROOT / "config" / "authorization.yaml"
BUDGETS = ROOT / "config" / "budgets.yaml"

AUTH_ORDER = ["A0", "A1", "A2", "A3", "A4", "A5", "A6"]

# Gate task membership is derived from each task's `gate` field.
# A gate additionally requires operator decisions listed here.
GATE_OPERATOR_DECISIONS = {
    "G0": ["G0-Q1", "G0-Q2", "G0-Q3", "G0-Q4", "G0-Q5", "G0-Q6", "G0-Q7",
           "G0-Q8", "G0-Q9", "G0-Q10", "G0-Q11", "G0-Q12", "G0-Q13", "G0-Q14"],
}


def _load_schema(name):
    with open(SCHEMA_DIR / name) as f:
        return Draft202012Validator(json.load(f))


def load_tasks():
    with open(TASKS) as f:
        doc = yaml.safe_load(f)
    return doc["tasks"]


def load_receipts():
    out = []
    if EVIDENCE.exists():
        for line in EVIDENCE.read_text().splitlines():
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def load_decisions():
    """Recorded operator decisions.

    D-xxx entries come from docs/decision-log.md headings; answered G0
    pack items (G0-Qn) come from the pack answer file when the operator
    fills it in (docs/decision-packs/*-answers.yaml).
    """
    ids = set()
    log = ROOT / "docs" / "decision-log.md"
    if log.exists():
        for line in log.read_text().splitlines():
            if line.startswith("## D-"):
                ids.add(line.split()[1])
    for f in (ROOT / "docs" / "decision-packs").glob("*-answers.yaml"):
        doc = yaml.safe_load(f.read_text()) or {}
        for item in doc.get("answers", []):
            if item.get("decision_id") and item.get("answer"):
                ids.add(item["item"])
                ids.add(item["decision_id"])
    return ids


def head_commit():
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT).decode().strip()


def validate(argv=None, quiet=False):
    validator = _load_schema("atlas-task.schema.json")
    tasks = load_tasks()
    errors = []
    ids = set()
    for t in tasks:
        for e in validator.iter_errors(t):
            errors.append(f"{t.get('id','<no id>')}: {e.message}")
        tid = t.get("id")
        if tid in ids:
            errors.append(f"duplicate id {tid}")
        ids.add(tid)
    by_id = {t["id"]: t for t in tasks}
    for t in tasks:
        for d in t.get("depends_on", []):
            if d not in ids:
                errors.append(f"{t['id']}: unknown dependency {d}")
    # acyclicity (Kahn)
    indeg = {t["id"]: 0 for t in tasks}
    for t in tasks:
        for d in t.get("depends_on", []):
            if d in indeg:
                indeg[t["id"]] += 1
    queue = [i for i, n in indeg.items() if n == 0]
    seen = 0
    dependents = {}
    for t in tasks:
        for d in t.get("depends_on", []):
            dependents.setdefault(d, []).append(t["id"])
    while queue:
        n = queue.pop()
        seen += 1
        for m in dependents.get(n, []):
            indeg[m] -= 1
            if indeg[m] == 0:
                queue.append(m)
    if seen != len(tasks):
        errors.append("dependency graph contains a cycle")
    # a task marked done must have verified (non-self-asserted) evidence
    receipts = load_receipts()
    for t in tasks:
        if t["status"] == "done":
            ok = [r for r in receipts
                  if r["task_id"] == t["id"] and not r["self_asserted"]
                  and all(c["result"] in ("pass", "not_applicable")
                          for c in r["criteria"])]
            if not ok:
                errors.append(
                    f"{t['id']}: status done without verified evidence receipt")
    if errors:
        for e in errors:
            print(f"FAIL {e}")
        return 1
    if not quiet:
        print(f"OK {len(tasks)} tasks; DAG acyclic; all references resolve")
    return 0


def _receipt_ok(r, task_id, commit=None):
    if r["task_id"] != task_id:
        return False
    if commit and not (commit.startswith(r["result_commit"])
                       or r["result_commit"].startswith(commit)):
        return False
    return all(c["result"] in ("pass", "not_applicable") for c in r["criteria"])


def task_verify(task_id):
    validator = _load_schema("task-evidence-receipt.schema.json")
    tasks = {t["id"]: t for t in load_tasks()}
    if task_id not in tasks:
        print(f"FAIL unknown task {task_id}")
        return 1
    head = head_commit()
    receipts = load_receipts()
    candidates = [r for r in receipts if r["task_id"] == task_id]
    if not candidates:
        print(f"FAIL {task_id}: no evidence receipt in {EVIDENCE}")
        return 1
    for r in candidates:
        errs = list(validator.iter_errors(r))
        if errs:
            print(f"FAIL {task_id}: receipt {r.get('receipt_id')} invalid: "
                  f"{errs[0].message}")
            return 1
    good = [r for r in candidates if _receipt_ok(r, task_id, head)]
    if not good:
        commits = sorted({r["result_commit"][:12] for r in candidates})
        print(f"FAIL {task_id}: no passing receipt bound to HEAD "
              f"{head[:12]} (receipts bind: {', '.join(commits)})")
        return 1
    kinds = "self-asserted" if all(r["self_asserted"] for r in good) \
        else "verified"
    print(f"PASS {task_id}: {len(good)} receipt(s) at HEAD ({kinds}). "
          f"Self-asserted receipts do NOT satisfy gates.")
    return 0


def gate_verify(gate):
    tasks = load_tasks()
    receipts = load_receipts()
    decisions = load_decisions()
    head = head_commit()
    rows, missing_ev = [], []
    gate_tasks = [t for t in tasks if t["gate"] == gate]
    if not gate_tasks:
        print(f"FAIL no tasks declare gate {gate}")
        return 1
    for t in gate_tasks:
        rs = [r for r in receipts if _receipt_ok(r, t["id"])]
        verified = [r for r in rs if not r["self_asserted"]]
        if verified:
            state = "verified"
        elif rs:
            state = "self_asserted_only"
            missing_ev.append(
                f"{t['id']}: only self-asserted evidence (clean-checkout CI "
                f"receipt required)")
        else:
            state = "missing"
            missing_ev.append(f"{t['id']}: no evidence receipt")
        rows.append({"id": t["id"], "status": t["status"],
                     "evidence_state": state,
                     "receipt_ids": [r["receipt_id"] for r in rs]})
    missing_dec = [d for d in GATE_OPERATOR_DECISIONS.get(gate, [])
                   if d not in decisions]
    ok = not missing_ev and not missing_dec
    manifest = {
        "schema_version": "atlas-gate-manifest/v1",
        "gate": gate,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds"),
        "commit": head,
        "pass": ok,
        "tasks": rows,
        "missing_evidence": missing_ev,
        "missing_operator_decisions": missing_dec,
    }
    gv = _load_schema("gate-evidence-manifest.schema.json")
    gv.validate(manifest)
    GATE_DIR.mkdir(parents=True, exist_ok=True)
    out = GATE_DIR / f"{gate}.json"
    out.write_text(json.dumps(manifest, indent=1) + "\n")
    print(f"{'PASS' if ok else 'FAIL'} gate {gate}: manifest {out}")
    if missing_dec:
        print(f"  missing operator decisions: {', '.join(missing_dec)}")
    if missing_ev:
        for m in missing_ev[:15]:
            print(f"  missing evidence: {m}")
        if len(missing_ev) > 15:
            print(f"  ... and {len(missing_ev)-15} more")
    return 0 if ok else 1


def plan_next():
    tasks = load_tasks()
    by_id = {t["id"]: t for t in tasks}
    decisions = load_decisions()
    budgets = yaml.safe_load(BUDGETS.read_text())
    authz = yaml.safe_load(AUTHZ.read_text())
    cur = authz["current_level"]
    if budgets.get("session_ceiling") is None or budgets.get("day_ceiling") is None:
        print("NONE READY: cost ceilings unset in config/budgets.yaml "
              "(operator decision G0-Q7). plan-next fails closed per "
              "SPEC.md 8.3 rule 5.")
        return 0
    ready = []
    for t in tasks:
        if t["status"] not in ("pending", "ready"):
            continue
        if any(by_id.get(d, {}).get("status") != "done"
               for d in t["depends_on"]):
            continue
        if AUTH_ORDER.index(t["authorization_min"]) > AUTH_ORDER.index(cur):
            continue
        if t["requires_operator_decision"] and not all(
                d in decisions for d in t["operator_decision_ids"]):
            continue
        ready.append(t["id"])
    print("READY: " + (", ".join(ready) if ready else "(none)"))
    return 0


def build_status():
    tasks = load_tasks()
    receipts = load_receipts()
    decisions = sorted(d for d in load_decisions() if d.startswith("D-"))
    head = head_commit()
    counts = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    lines = [
        "# Build status (generated — do not hand-edit)",
        "",
        f"Generated by `make build-status` at commit `{head[:12]}` on "
        f"{datetime.date.today().isoformat()}. Narrative status must not "
        "drift from this ledger (SPEC.md 8.3).",
        "",
        f"- Authorization: **{yaml.safe_load(AUTHZ.read_text())['current_level']}**",
        f"- Recorded operator decisions: {', '.join(decisions) or 'none'}",
        f"- Tasks: {len(tasks)} | " + " | ".join(
            f"{k}: {v}" for k, v in sorted(counts.items())),
        f"- Evidence receipts: {len(receipts)} "
        f"({sum(1 for r in receipts if r['self_asserted'])} self-asserted; "
        "self-asserted receipts never satisfy a gate)",
        "",
        "| Task | Gate | Status | Evidence | Blocked reason |",
        "|---|---|---|---|---|",
    ]
    for t in tasks:
        rs = [r for r in receipts if r["task_id"] == t["id"]]
        ev = ("verified" if any(not r["self_asserted"] for r in rs)
              else "self-asserted" if rs else "—")
        lines.append(
            f"| {t['id']} | {t['gate']} | {t['status']} | {ev} | "
            f"{t.get('blocked_reason', '')} |")
    lines.append("")
    lines.append("Evidence state legend per SPEC.md 0.3(15): nothing above "
                 "`implemented`/`fixture_tested` exists yet; no live-source, "
                 "operator-adjudicated, externally-reviewed or time-observed "
                 "claims are made.")
    (ROOT / "docs" / "build-status.md").write_text("\n".join(lines) + "\n")
    print(f"wrote docs/build-status.md ({len(tasks)} tasks)")
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["validate", "next", "task-verify",
                                   "gate-verify", "build-status"])
    p.add_argument("arg", nargs="?")
    a = p.parse_args()
    if a.cmd == "validate":
        sys.exit(validate())
    if a.cmd == "next":
        sys.exit(plan_next())
    if a.cmd == "task-verify":
        if not a.arg:
            sys.exit("task-verify requires TASK=<id>")
        sys.exit(task_verify(a.arg))
    if a.cmd == "gate-verify":
        if not a.arg:
            sys.exit("gate-verify requires GATE=<id>")
        sys.exit(gate_verify(a.arg))
    if a.cmd == "build-status":
        sys.exit(build_status())


if __name__ == "__main__":
    main()
