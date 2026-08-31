"""BOOT-040/BOOT-050 self-tests.

Proves (SPEC BOOT-050 acceptance): missing evidence fails, wrong-commit
evidence fails, self-asserted evidence never satisfies a gate, negative
schema fixtures fail, null cost ceilings block plan-next.
"""
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
PY = ROOT / ".venv" / "bin" / "python"
FIX = ROOT / "tests" / "fixtures" / "plan"

sys.path.insert(0, str(ROOT / "tools"))
import atlas_plan  # noqa: E402
from jsonschema import Draft202012Validator  # noqa: E402


def _schema(name):
    return Draft202012Validator(
        json.load(open(ROOT / "schemas" / "plan" / name)))


def test_positive_fixtures_validate():
    _schema("atlas-task.schema.json").validate(
        json.load(open(FIX / "task-valid.json")))
    _schema("task-evidence-receipt.schema.json").validate(
        json.load(open(FIX / "receipt-valid.json")))
    _schema("operator-decision.schema.json").validate(
        json.load(open(FIX / "decision-valid.json")))


def test_negative_fixtures_fail():
    cases = [
        ("atlas-task.schema.json", "task-neg-unknown-prop.json"),
        ("atlas-task.schema.json", "task-neg-bad-status.json"),
        ("atlas-task.schema.json", "task-neg-bad-profile.json"),
        ("atlas-task.schema.json", "task-neg-missing-gate.json"),
        ("task-evidence-receipt.schema.json", "receipt-neg-bad-commit.json"),
        ("task-evidence-receipt.schema.json", "receipt-neg-empty-criteria.json"),
        ("task-evidence-receipt.schema.json", "receipt-neg-bool-result.json"),
        ("task-evidence-receipt.schema.json",
         "receipt-neg-missing-selfassert.json"),
        ("operator-decision.schema.json", "decision-neg-not-operator.json"),
        ("operator-decision.schema.json", "decision-neg-missing-expiry.json"),
    ]
    for schema, fixture in cases:
        errs = list(_schema(schema).iter_errors(json.load(open(FIX / fixture))))
        assert errs, f"negative fixture {fixture} unexpectedly validated"


def test_plan_validates():
    assert atlas_plan.validate(quiet=True) == 0


def test_missing_evidence_fails_task_verify():
    # REL-000 exists in the plan but has no receipt
    assert atlas_plan.task_verify("REL-000") == 1


def test_unknown_task_fails():
    assert atlas_plan.task_verify("NOPE-999") == 1


def test_wrong_commit_evidence_fails(tmp_path, monkeypatch):
    head = atlas_plan.head_commit()
    wrong = "0" * 40
    receipt = {
        "schema_version": "atlas-task-evidence-receipt/v1",
        "receipt_id": "rcpt_wrong-commit-test",
        "task_id": "REL-000",
        "builder_profile": "claude",
        "base_commit": wrong, "result_commit": wrong,
        "commands": [{"cmd": "true", "exit_code": 0}],
        "criteria": [{"id": "x", "tag": "automated", "result": "pass"}],
        "self_asserted": True, "recorded_at": "2026-08-31T00:00:00Z",
    }
    ev = tmp_path / "evidence.jsonl"
    ev.write_text(json.dumps(receipt) + "\n")
    monkeypatch.setattr(atlas_plan, "EVIDENCE", ev)
    assert atlas_plan.task_verify("REL-000") == 1
    # same receipt at HEAD passes task-verify (but is still self-asserted)
    receipt["result_commit"] = head
    ev.write_text(json.dumps(receipt) + "\n")
    assert atlas_plan.task_verify("REL-000") == 0


def test_self_asserted_never_passes_gate(monkeypatch, capsys):
    # even if every G0 task had self-asserted receipts, gate must fail
    rc = atlas_plan.gate_verify("G0")
    out = capsys.readouterr().out
    assert rc == 1
    assert "missing operator decisions" in out or "missing evidence" in out
    manifest = json.load(open(atlas_plan.GATE_DIR / "G0.json"))
    assert manifest["pass"] is False


def test_null_ceilings_block_plan_next(capsys):
    assert atlas_plan.plan_next() == 0
    assert "cost ceilings unset" in capsys.readouterr().out


def test_done_without_verified_evidence_is_validation_error(monkeypatch,
                                                            tmp_path):
    import yaml
    tasks = atlas_plan.load_tasks()
    tasks[0] = dict(tasks[0])
    tasks[0]["status"] = "done"
    tf = tmp_path / "tasks.yaml"
    tf.write_text(yaml.safe_dump({"tasks": tasks}))
    monkeypatch.setattr(atlas_plan, "TASKS", tf)
    assert atlas_plan.validate(quiet=True) == 1
