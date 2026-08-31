"""DOM-001 catalogue-wide tests.

Every domain schema must (a) have a validating positive example (either
here or exercised by the kernel/plan tests listed in KERNEL_COVERED),
(b) reject an injected unknown property (unevaluatedProperties: false
everywhere), and (c) have resolvable $refs (validation would fail
otherwise).
"""
import json
import pathlib

import pytest

from atlas.schemas import DOMAIN, AtlasSchemaError, validate

EX = json.loads(pathlib.Path(
    __file__).with_name("fixtures").joinpath("domain-examples.json").read_text())

# schemas whose positive fixtures live in the kernel/e2e/release tests
KERNEL_COVERED = {
    "common.schema.json",  # $defs only
    "source-document.schema.json", "source-version.schema.json",
    "acquisition-receipt.schema.json", "text-artifact.schema.json",
    "anchor.schema.json", "assertion-proposal.schema.json",
    "assertion-acceptance-decision.schema.json", "assertion.schema.json",
    "validation-report.schema.json", "publication-policy-decision.schema.json",
    "record-identity.schema.json", "facts-revision.schema.json",
    "record-revision-manifest.schema.json", "suppression-overlay.schema.json",
    "release-input-snapshot.schema.json", "release-manifest.schema.json",
    "audit-event.schema.json", "record-summary-v1.schema.json",
    "monitor-target.schema.json", "monitoring-check.schema.json",
    "searched-scope.schema.json", "freshness-overlay.schema.json",
}


def test_every_schema_is_covered():
    names = {p.name for p in DOMAIN.glob("*.json")}
    uncovered = names - set(EX) - KERNEL_COVERED
    assert not uncovered, f"schemas without positive fixtures: {sorted(uncovered)}"
    missing = set(EX) - names
    assert not missing, f"examples for nonexistent schemas: {sorted(missing)}"


@pytest.mark.parametrize("name", sorted(EX))
def test_positive_example_validates(name):
    validate(name, EX[name])


@pytest.mark.parametrize("name", sorted(EX))
def test_unknown_property_rejected(name):
    bad = dict(EX[name])
    bad["totally_unknown_field"] = "x"
    with pytest.raises(AtlasSchemaError):
        validate(name, bad)


def test_conditional_requirements():
    # 'other' label requires other_detail
    a = dict(EX["classification-assignment.schema.json"], labels=["other"])
    with pytest.raises(AtlasSchemaError):
        validate("classification-assignment.schema.json", a)
    # confirmed_out_of_scope requires a stored boundary decision
    c = dict(EX["citation-check-result-v1.schema.json"],
             status="confirmed_out_of_scope")
    with pytest.raises(AtlasSchemaError):
        validate("citation-check-result-v1.schema.json", c)
    c.update({"boundary_decision_id": "bnd_abcdef123456",
              "boundary_version": "1.0.0",
              "decision_as_of": "2026-08-31T12:00:00Z",
              "normalized_citation_key": "us-ftc-c-0000"})
    validate("citation-check-result-v1.schema.json", c)
    # procedural event kind=other requires other_detail
    e = dict(EX["procedural-event.schema.json"], kind="other")
    with pytest.raises(AtlasSchemaError):
        validate("procedural-event.schema.json", e)
    # a non-Alexios reviewer fails
    r = dict(EX["review-decision.schema.json"], decided_by="assistant")
    with pytest.raises(AtlasSchemaError):
        validate("review-decision.schema.json", r)


def test_source_registry_files_validate():
    import yaml
    root = pathlib.Path(__file__).resolve().parent.parent
    for f in ["courtlistener_recap.yaml", "ftc_enforcement.yaml"]:
        doc = yaml.safe_load((root / "config" / "sources" / f).read_text())
        validate("source-registry-entry.schema.json", doc)
