"""DOM-001 schema tests: negatives fail with the strict validator."""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
from atlas.schemas import AtlasSchemaError, validate

AT = "2026-08-31T12:00:00Z"
GOOD_MONEY = {"decimal": "5000000.00", "currency": "USD", "amount_type": "ordered"}


def _proposal(**over):
    p = {"schema_version": "atlas-assertion-proposal/v1",
         "proposal_id": "prop_abcdef123456",
         "source_version_id": "sver_abcdef123456",
         "subject_ref": {"entity_type": "procedural_event",
                         "entity_id": "event_1"},
         "predicate": "remedy.amount", "raw_value": "$5,000,000",
         "value_status": "stated", "procedural_modality": "order",
         "value_origin": "source_quote",
         "support": [{"anchor_id": "anc_abcdef123456", "role": "supports",
                      "passage_role": "operative_part",
                      "attributed_speaker": "issuing_court"}],
         "observed_at": AT, "proposed_by": "manual",
         "normalized_value": GOOD_MONEY, "transform": None,
         "legal_time": None}
    p.update(over)
    return p


def test_valid_proposal_passes():
    validate("assertion-proposal.schema.json", _proposal())


def test_unknown_property_fails():
    with pytest.raises(AtlasSchemaError):
        validate("assertion-proposal.schema.json", _proposal(verified=True))


def test_float_money_fails():
    bad = dict(GOOD_MONEY, decimal=5000000.0)
    with pytest.raises(AtlasSchemaError):
        validate("assertion-proposal.schema.json", _proposal(normalized_value=bad))


def test_bad_modality_fails():
    with pytest.raises(AtlasSchemaError):
        validate("assertion-proposal.schema.json",
                 _proposal(procedural_modality="verdictish"))


def test_other_amount_type_requires_nothing_extra_but_unknown_enum_fails():
    with pytest.raises(AtlasSchemaError):
        validate("assertion-proposal.schema.json",
                 _proposal(normalized_value=dict(GOOD_MONEY, amount_type="fine")))


def test_bad_timestamp_fails():
    with pytest.raises(AtlasSchemaError):
        validate("assertion-proposal.schema.json", _proposal(observed_at="yesterday"))


def test_acceptance_requires_operator():
    dec = {"schema_version": "atlas-assertion-acceptance/v1",
           "decision_id": "dec_abcdef123456", "proposal_id": "prop_abcdef123456",
           "decided_by": "Alexios", "role": "operator_reviewer",
           "decision": "accept", "reason": "verified against operative text",
           "decided_at": AT,
           "validation_report_sha256": "0" * 64}
    validate("assertion-acceptance-decision.schema.json", dec)
    with pytest.raises(AtlasSchemaError):
        validate("assertion-acceptance-decision.schema.json",
                 dict(dec, decided_by="assistant"))
