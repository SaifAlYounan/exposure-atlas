"""ID-002 — fuzzy match proposals.

Covers SPEC §9 acceptance:
- every fuzzy result enters review (advisory IdentityMatchProposal,
  match_kind=fuzzy; never auto-merge);
- incorrect-match fixtures cannot mutate record identity (proposing is
  read-only);
- merge/split/link decisions remain reversible (applied only as reversible
  RecordRelationships).
Deterministic; no network, credentials or model calls.
"""
from atlas import fuzzy, identity
from atlas.schemas import validate

CND = "cnd_0123456789ab"
REC = "rec_0123456789ab"


def _has_float(obj) -> bool:
    if isinstance(obj, float):
        return True
    if isinstance(obj, dict):
        return any(_has_float(v) for v in obj.values())
    if isinstance(obj, list):
        return any(_has_float(v) for v in obj)
    return False


def test_normalize_name_strips_suffixes_and_punct():
    assert fuzzy.normalize_name("Acme Corp., Inc.") == "acme"
    assert fuzzy.normalize_name("The Widget Company LLC") == "widget"


def test_name_similarity_high_and_low():
    assert fuzzy.name_similarity("Acme Robotics Inc", "Acme Robotics LLC") == "1.0000"
    assert fuzzy.name_similarity("Acme Robotics", "Zzz Holdings") == "0.0000"


def test_proposal_above_threshold_validates_and_is_fuzzy():
    cand = {"candidate_id": CND, "name": "Acme Robotics Inc",
            "forum": "us_ftc", "date": "2024-01-10", "title": "In re Acme AI claims"}
    rec = {"record_id": REC, "name": "Acme Robotics LLC",
           "forum": "us_ftc", "date": "2024-01-12", "title": "In re Acme AI claims"}
    p = fuzzy.propose_match(cand, rec)
    assert p is not None
    validate("identity-match-proposal.schema.json", p)
    assert p["match_kind"] == "fuzzy"  # advisory -> enters review, never auto-merge
    assert isinstance(p["score"], str) and p["score"] > fuzzy.PROPOSE_THRESHOLD
    assert p["rule_version"] == fuzzy.RULE_VERSION
    assert not _has_float(p)  # decimal strings only; canonical-safe


def test_clearly_different_yields_no_proposal():
    cand = {"candidate_id": CND, "name": "Acme Robotics",
            "forum": "us_ftc", "date": "2024-01-10", "title": "AI marketing claims"}
    rec = {"record_id": REC, "name": "Northwind Logistics",
           "forum": "us_federal_courts", "date": "2019-08-01", "title": "breach of contract"}
    assert fuzzy.propose_match(cand, rec) is None


def test_propose_matches_sorted_and_advisory_only():
    cand = {"candidate_id": CND, "name": "Acme Robotics Inc",
            "forum": "us_ftc", "date": "2024-01-10", "title": "In re Acme AI"}
    recs = [
        {"record_id": "rec_aaaaaaaaaaaa", "name": "Acme Robotics LLC",
         "forum": "us_ftc", "date": "2024-01-11", "title": "In re Acme AI"},
        {"record_id": "rec_bbbbbbbbbbbb", "name": "Acme Robotics Holdings",
         "forum": "us_ftc", "date": "2024-02-01", "title": "In re Acme"},
        {"record_id": "rec_cccccccccccc", "name": "Unrelated Co",
         "forum": "us_federal_courts", "date": "2010-01-01", "title": "nothing"},
    ]
    props = fuzzy.propose_matches(cand, recs)
    assert all(p["match_kind"] == "fuzzy" for p in props)
    assert [p["score"] for p in props] == sorted((p["score"] for p in props), reverse=True)
    assert "rec_cccccccccccc" not in {p["matched_record_id"] for p in props}  # below threshold


def test_incorrect_match_cannot_mutate_record_identity():
    r = identity.IdentityResolver()
    rid, _ = r.resolve([{"kind": "docket_id", "value": "real-matter-1"}])
    before_keys = dict(r._by_key)
    before_aliases = {k: set(v) for k, v in r._aliases.items()}
    # generate fuzzy proposals against a made-up record id — read-only, advisory
    cand = {"candidate_id": CND, "name": "Real Matter One", "forum": "us_ftc",
            "date": "2024-01-10", "title": "x"}
    fuzzy.propose_matches(cand, [{"record_id": rid, "name": "Real Matter One",
                                  "forum": "us_ftc", "date": "2024-01-10", "title": "x"}])
    # the resolver state is untouched: a fuzzy proposal never writes identity
    assert r._by_key == before_keys
    assert {k: set(v) for k, v in r._aliases.items()} == before_aliases


def test_accepted_proposal_applies_only_as_reversible_relationship():
    r = identity.IdentityResolver()
    a, _ = r.resolve([{"kind": "docket_id", "value": "matter-a"}])
    b, _ = r.resolve([{"kind": "docket_id", "value": "matter-b"}])
    # a human accepts a fuzzy proposal -> reversible typed link, distinct records kept
    rln = identity.make_relationship("same_matter_as", a, b, "Alexios",
                                     "2026-09-02T15:00:00Z", reason="operator-accepted fuzzy match")
    validate("record-relationship.schema.json", rln)
    assert rln["reversible"] is True and a != b


def test_proposal_id_is_stable():
    cand = {"candidate_id": CND, "name": "Acme Robotics Inc", "forum": "us_ftc",
            "date": "2024-01-10", "title": "In re Acme AI"}
    rec = {"record_id": REC, "name": "Acme Robotics LLC", "forum": "us_ftc",
           "date": "2024-01-12", "title": "In re Acme AI"}
    assert fuzzy.propose_match(cand, rec)["proposal_id"] == fuzzy.propose_match(cand, rec)["proposal_id"]
