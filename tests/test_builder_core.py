"""HAR-000-03/HAR-002/HAR-005 + SRC-003 + SEC-001-01 additions."""
import pathlib

import pytest

from atlas.archive import evaluate_archive_request
from builder.core.budget import BudgetExhausted, BudgetLedger
from builder.core.completion import CompletionRefused, close_task
from builder.core.policy import PolicyDenied, check_tool, compile_policy

ROOT = pathlib.Path(__file__).resolve().parent.parent
AT = "2026-08-31T12:00:00Z"
SV = {"source_version_id": "sver_abcdef123456"}


# ---- SRC-003 --------------------------------------------------------
def test_archive_disabled_by_default_and_fails_closed():
    r = evaluate_archive_request(source_version=SV,
                                 archive_axis_outcome="cleared_public",
                                 globally_enabled=False, at=AT)
    assert r["decision"] == "deny" and "disabled by default" in r["result"]
    r = evaluate_archive_request(source_version=SV, archive_axis_outcome=None,
                                 globally_enabled=True, at=AT)
    assert r["decision"] == "deny" and "fails closed" in r["result"]
    for blocked in ["pending", "internal_only", "prohibited", "withdrawn"]:
        r = evaluate_archive_request(source_version=SV,
                                     archive_axis_outcome=blocked,
                                     globally_enabled=True, at=AT)
        assert r["decision"] == "deny"
    r = evaluate_archive_request(source_version=SV,
                                 archive_axis_outcome="cleared_public",
                                 globally_enabled=True, at=AT)
    assert r["decision"] == "allow"
    # every attempt, including refusals, records policy version + result
    assert r["policy_version"] and r["result"]


# ---- HAR-002 --------------------------------------------------------
def test_role_policy_deny_by_default():
    policy = compile_policy()
    check_tool(policy, "planner", "read")
    with pytest.raises(PolicyDenied):   # omitted tool unavailable
        check_tool(policy, "planner", "write")
    with pytest.raises(PolicyDenied):   # explicitly disallowed
        check_tool(policy, "implementer", "git_push_main")
    with pytest.raises(PolicyDenied):   # unknown role denied
        check_tool(policy, "superuser", "read")
    with pytest.raises(PolicyDenied):   # coordinator cannot waive checks
        check_tool(policy, "coordinator", "waive_failed_check")
    assert len(policy["hash"]) == 64


def test_policy_change_changes_hash(tmp_path):
    src = (ROOT / "config" / "builder-roles.yaml").read_text()
    p1 = compile_policy()
    f = tmp_path / "roles.yaml"
    f.write_text(src.replace("policy_version: 1.0.0", "policy_version: 1.0.1"))
    p2 = compile_policy(f)
    assert p1["hash"] != p2["hash"]


# ---- HAR-005 budget -------------------------------------------------
def _ledger(tmp_path, session=10, day=30):
    b = tmp_path / "budgets.yaml"
    b.write_text(f"session_ceiling: {session}\nday_ceiling: {day}\n")
    return BudgetLedger(b, tmp_path / "ledger.jsonl")


def test_budget_reserve_reconcile_and_exhaustion(tmp_path):
    led = _ledger(tmp_path)
    led.reserve("r1", 6)
    with pytest.raises(BudgetExhausted):   # cannot cover reservation
        led.reserve("r2", 5)
    led.reconcile("r1", 2)                 # observed less than worst case
    led.reserve("r2", 5)                   # now fits
    assert led.committed() == 7


def test_null_ceilings_fail_closed(tmp_path):
    b = tmp_path / "budgets.yaml"
    b.write_text("session_ceiling: null\nday_ceiling: null\n")
    led = BudgetLedger(b, tmp_path / "ledger.jsonl")
    with pytest.raises(BudgetExhausted):
        led.reserve("r1", 1)


# ---- HAR-000-03/HAR-005 completion gate -----------------------------
@pytest.mark.parametrize("reason", ["interrupted", "api_failure", "max_turns",
                                    "budget_stopped", "crash"])
def test_failure_paths_cannot_complete(reason):
    with pytest.raises(CompletionRefused):
        close_task("REL-000", termination_reason=reason,
                   structured_output_valid=True)


def test_provider_success_without_valid_output_cannot_complete():
    with pytest.raises(CompletionRefused):
        close_task("REL-000", termination_reason="complete",
                   structured_output_valid=False)


def test_complete_without_receipt_refused():
    with pytest.raises(CompletionRefused, match="no passing evidence"):
        close_task("REL-000", termination_reason="complete",
                   structured_output_valid=True)


# ---- SEC-001-01 additions -------------------------------------------
def test_sec08_acceptance_replay_refused(tmp_path):
    from atlas.kernel import Kernel
    FIX = ROOT / "tests" / "fixtures" / "documents"
    k = Kernel(tmp_path, ["www.ftc.gov"])
    _, sver = k.ingest_fixture(FIX / "ftc_order_fixture.html",
                               declared_url="https://www.ftc.gov/f",
                               declared_mime="text/html", issuer="US FTC",
                               title="t", document_role="regulator_decision",
                               source_id="ftc_enforcement",
                               copy_provenance_state="issuer_direct",
                               retrieved_at=AT)
    art = k.canonicalize(sver["source_version_id"], AT)
    q = "Respondent shall pay a civil penalty of $5,000,000"
    anc = k.add_anchor(art["text_artifact_id"], q)
    prop = k.propose(source_version_id=sver["source_version_id"],
                     subject_ref={"entity_type": "procedural_event",
                                  "entity_id": "e"},
                     predicate="p", raw_value=q, modality="order",
                     value_origin="source_quote",
                     support=[{"anchor_id": anc["anchor_id"], "role": "supports",
                               "passage_role": "operative_part",
                               "attributed_speaker": "issuer"}],
                     observed_at=AT)
    k.verify(prop["proposal_id"])
    k.approve(prop["proposal_id"], reason="ok", decided_at=AT)
    with pytest.raises(RuntimeError, match="replayed acceptance"):
        k.approve(prop["proposal_id"], reason="again", decided_at=AT)


def test_sec06_hostile_strings_stay_inert_in_projection():
    from atlas.release import project_record_summary
    hostile = "=SUM(A1:A9)<script>alert(1)</script>"
    rec = project_record_summary(
        release_id="rel_abcdef123456",
        record={"record_id": "rec_abcdef123456",
                "record_revision_id": "rrv_abcdef123456"},
        assertions=[{"predicate": "party.name.statement", "raw_value": hostile,
                     "normalized_value": None, "procedural_modality": "allegation",
                     "semantic_review_state": "human_approved",
                     "source_version_id": "sver_abcdef123456"}],
        source_documents={"sdoc_abcdef123456": {"issuer": "x", "title": "y",
                          "source_document_id": "sdoc_abcdef123456"}},
        source_versions={"sver_abcdef123456": {
            "source_version_id": "sver_abcdef123456",
            "source_document_id": "sdoc_abcdef123456",
            "content_sha256": "ab" * 32}},
        boundary_version="1.0.0")
    # stays a JSON string value, byte-identical: no execution, no mangling
    assert rec["facts"][0]["raw_value"] == hostile


def test_sec07_model_style_output_with_extra_keys_rejected():
    from atlas.schemas import AtlasSchemaError, validate
    hostile = {"schema_version": "atlas-classification-proposal/v1",
               "proposal_id": "cpr_abcdef123456", "target_ref": {},
               "labels": ["privacy_data_protection"],
               "taxonomy_version": "1.0.0", "rubric_version": "1.0.0",
               "proposed_by": "model", "run_id": "r1",
               "exec_command": "rm -rf /", "fetch_url": "http://evil"}
    with pytest.raises(AtlasSchemaError):
        validate("classification-proposal.schema.json", hostile)
