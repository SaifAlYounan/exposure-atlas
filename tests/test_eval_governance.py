"""EVAL-000 — frozen evaluation governance.

Covers SPEC section 9 acceptance for EVAL-000:
- runtime credentials cannot read held-out labels/answer keys;
- blinded items commit the operator's initial label before votes are
  revealed; a same-operator reconsideration is retained separately and is
  not dual adjudication;
- underpowered slices are review_only/unsupported, not pooled;
- the single-adjudicator limitation is disclosed; no model is a 2nd human;
- prompt/rubric authors cannot self-certify without the operator's frozen
  labels and gate decision.
All deterministic; no network, credentials or model calls.
"""
import pytest

from atlas import evalgov
from atlas.schemas import AtlasSchemaError, validate


def gov():
    return evalgov.load_governance()


def test_governance_config_validates_and_is_frozen():
    g = gov()
    assert g["schema_version"] == "atlas-eval-governance/v1"
    assert g["partition_assignment"]["one_time"] is True
    # all seven stages have a metric registration
    stages = {s["stage"] for s in g["stage_metrics"]}
    assert stages == set(g["stages"]) == {
        "discovery", "boundary", "extraction", "identity",
        "classification", "monitoring", "end_to_end"}


def test_runtime_credentials_cannot_read_holdout():
    g = gov()
    assert g["holdout_access"]["runtime_can_read_labels"] is False
    for role in ("runtime", "runtime_worker", "release_bot", "release", "builder"):
        assert evalgov.can_read_holdout(role, g) is False
    assert evalgov.can_read_holdout("operator", g) is True


def test_partition_assignment_is_one_time_and_deterministic():
    g = gov()
    keys = [f"ftc/matter-{i}" for i in range(400)]
    first = {k: evalgov.assign_partition(k, g) for k in keys}
    # idempotent: re-running never moves an item between partitions
    for k in keys:
        assert evalgov.assign_partition(k, g) == first[k]
    assigned = set(first.values())
    assert assigned <= set(g["partitions"])
    # every partition is reachable over a reasonable sample
    assert assigned == set(g["partitions"])


def test_partition_salt_changes_assignment():
    g = gov()
    g2 = dict(g, partition_assignment=dict(g["partition_assignment"], salt="a-different-salt-v2"))
    diff = sum(evalgov.assign_partition(f"m{i}", g) != evalgov.assign_partition(f"m{i}", g2)
               for i in range(200))
    assert diff > 0  # a different salt yields a different (still stable) mapping


def test_underpowered_slice_is_not_pooled():
    g = gov()
    assert evalgov.slice_disposition(30, "boundary", g) == "supported"
    assert evalgov.slice_disposition(29, "boundary", g) == g["underpowered_disposition"]
    assert evalgov.slice_disposition(0, "extraction", g) in ("review_only", "unsupported")
    with pytest.raises(KeyError):
        evalgov.slice_disposition(50, "not_a_stage", g)


def test_blinded_label_committed_before_votes_revealed():
    ok = {"blinded": True,
          "label_commit": {"committed_by": "Alexios",
                           "committed_at": "2026-09-02T05:10:00Z",
                           "initial_label": "publish"},
          "votes_revealed_at": "2026-09-02T06:00:00Z"}
    assert evalgov.blinded_ordering_ok(ok) is True
    # votes revealed BEFORE the label was committed -> violation
    bad = dict(ok, votes_revealed_at="2026-09-02T05:00:00Z")
    assert evalgov.blinded_ordering_ok(bad) is False
    # not yet revealed is fine; a blinded item with no commit is a violation
    assert evalgov.blinded_ordering_ok(dict(ok, votes_revealed_at=None)) is True
    assert evalgov.blinded_ordering_ok({"blinded": True}) is False
    # non-blinded items are unconstrained
    assert evalgov.blinded_ordering_ok({"blinded": False}) is True


def test_reconsideration_retained_separately_not_dual_adjudication():
    item = {"blinded": True,
            "label_commit": {"committed_by": "Alexios",
                             "committed_at": "2026-09-02T05:10:00Z",
                             "initial_label": "publish"},
            "votes_revealed_at": "2026-09-02T06:00:00Z",
            "reconsideration": {"reconsidered_by": "Alexios",
                               "reconsidered_at": "2026-09-03T09:00:00Z",
                               "label": "abstain", "retained_separately": True}}
    assert evalgov.reconsideration_is_separate(item) is True
    assert evalgov.is_dual_adjudication(item) is False
    assert evalgov.reconsideration_is_separate(
        dict(item, reconsideration=dict(item["reconsideration"], retained_separately=False))) is False


def test_authors_cannot_self_certify():
    # operator, with frozen labels AND gate decision -> may certify
    assert evalgov.can_certify_gate("builder", "operator", True, True) is True
    # a prompt/rubric author (builder or model) can never certify
    assert evalgov.can_certify_gate("builder", "builder", True, True) is False
    assert evalgov.can_certify_gate("model", "model", True, True) is False
    # operator missing either artifact -> cannot certify
    assert evalgov.can_certify_gate("builder", "operator", False, True) is False
    assert evalgov.can_certify_gate("builder", "operator", True, False) is False


def test_eval_item_schema_blinded_requires_label_commit():
    base = {"schema_version": "atlas-eval-item/v1",
            "item_id": "evi_0123456789ab", "stage": "boundary",
            "partition": "calibration", "governance_version": "1.0.0",
            "blinded": True, "expected": {"criteria": []}}
    # blinded without label_commit/votes_revealed_at is rejected
    with pytest.raises(AtlasSchemaError):
        validate("eval-item.schema.json", base)
    ok = dict(base,
              label_commit={"committed_by": "Alexios",
                           "committed_at": "2026-09-02T05:10:00Z",
                           "initial_label": "include"},
              votes_revealed_at=None)
    validate("eval-item.schema.json", ok)


def test_eval_item_end_to_end_requires_disposition():
    base = {"schema_version": "atlas-eval-item/v1",
            "item_id": "evi_0123456789ab", "stage": "end_to_end",
            "partition": "development", "governance_version": "1.0.0",
            "blinded": False, "expected": {"disposition": "not_a_disposition"}}
    with pytest.raises(AtlasSchemaError):
        validate("eval-item.schema.json", base)
    validate("eval-item.schema.json", dict(base, expected={"disposition": "publish"}))


def test_eval_item_id_is_stable():
    a = evalgov.eval_item_id("boundary", "ftc/matter-1")
    assert a == evalgov.eval_item_id("boundary", "ftc/matter-1")
    assert a != evalgov.eval_item_id("extraction", "ftc/matter-1")
    assert a.startswith("evi_") and len(a) == 16
