"""DISC-001 candidate ledger + DISC-002 query library tests."""
import pathlib

import pytest

from atlas.discovery import (CandidateLedger, QueryLibrary, candidate_id,
                             make_discovery_run, normalize_url)

ROOT = pathlib.Path(__file__).resolve().parent.parent
AT = "2026-09-01T00:00:00Z"
QLIB = ROOT / "config" / "queries" / "v1.yaml"


def test_fingerprint_idempotent_and_url_normalized():
    a = candidate_id("ftc_enforcement", "https://www.ftc.gov/x/")
    b = candidate_id("ftc_enforcement", "https://www.ftc.gov/x?utm=1#frag")
    assert a == b and a.startswith("cnd_")
    assert normalize_url("https://WWW.FTC.GOV/x/") == "https://www.ftc.gov/x"


def test_rediscovery_updates_observation_not_duplicate():
    led = CandidateLedger()
    c1, new1 = led.intake(source_id="ftc_enforcement",
                          lead_url="https://www.ftc.gov/a",
                          query_version="1.0.0", run_id="r1",
                          boundary_version="1.0.0", at=AT)
    c2, new2 = led.intake(source_id="ftc_enforcement",
                          lead_url="https://www.ftc.gov/a?x=1",
                          query_version="1.0.0", run_id="r2",
                          boundary_version="1.0.0", at=AT)
    assert new1 is True and new2 is False
    assert c1["candidate_id"] == c2["candidate_id"]
    assert len(led.candidates) == 1
    assert led.observation_count(c1["candidate_id"]) == 2


def test_exclusion_is_controlled_and_replayable():
    led = CandidateLedger()
    c, _ = led.intake(source_id="ftc_enforcement",
                      lead_url="https://www.ftc.gov/b", query_version="1.0.0",
                      run_id="r1", boundary_version="1.0.0", at=AT)
    with pytest.raises(ValueError):
        led.exclude(c["candidate_id"], reason="because", boundary_version="1.0.0")
    led.exclude(c["candidate_id"], reason="out_of_boundary",
                boundary_version="1.0.0")
    assert led.candidates[c["candidate_id"]]["disposition"] == "excluded"
    # boundary change makes it replayable
    assert led.replay_excluded(new_boundary_version="2.0.0")
    assert not led.replay_excluded(new_boundary_version="1.0.0")


def test_partial_outage_degrades_coverage():
    lib = QueryLibrary(QLIB)
    q = lib.active("ftc_enforcement", "2026-09-01")
    ok = make_discovery_run(run_id="r1", source_id="ftc_enforcement", query=q,
                            leads_seen=8, new_candidates=8,
                            updated_observations=0, at=AT)
    assert ok["coverage_state"] == "complete"
    degraded = make_discovery_run(run_id="r2", source_id="ftc_enforcement",
                                  query=q, leads_seen=3, new_candidates=3,
                                  updated_observations=0, at=AT,
                                  failures=["page 2 timeout"])
    assert degraded["coverage_state"] == "partial"
    failed = make_discovery_run(run_id="r3", source_id="ftc_enforcement",
                                query=q, leads_seen=0, new_candidates=0,
                                updated_observations=0, at=AT,
                                failures=["adapter down"])
    assert failed["coverage_state"] == "failed"


def test_below_expected_band_flagged():
    lib = QueryLibrary(QLIB)
    q = lib.active("ftc_enforcement", "2026-09-01")  # expected_min_results 5
    run = make_discovery_run(run_id="r1", source_id="ftc_enforcement", query=q,
                             leads_seen=2, new_candidates=2,
                             updated_observations=0, at=AT)
    assert run["below_expected_band"] is True


def test_query_library_active_and_backfill():
    lib = QueryLibrary(QLIB)
    q = lib.active("courtlistener_recap", "2026-09-01")
    assert q["query_id"] == "q_courtlistener_ai_opinions"
    assert lib.needs_backfill("0.9.0", "courtlistener_recap", "2026-09-01") is True
    assert lib.needs_backfill("1.0.0", "courtlistener_recap", "2026-09-01") is False
    assert lib.needs_backfill(None, "courtlistener_recap", "2026-09-01") is False
    with pytest.raises(KeyError):
        lib.active("unknown_source", "2026-09-01")


def test_candidate_traceable_to_query_and_run():
    led = CandidateLedger()
    c, _ = led.intake(source_id="courtlistener_recap",
                      lead_url="https://www.courtlistener.com/opinion/1/x",
                      query_version="1.0.0", run_id="run-42",
                      boundary_version="1.0.0", at=AT)
    obs = led.observations[c["candidate_id"]][0]
    assert obs["run_id"] == "run-42" and obs["query_version"] == "1.0.0"
    assert c["query_version"] == "1.0.0"
