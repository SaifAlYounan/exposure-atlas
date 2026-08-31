"""SRC-004 (pilot adapters over cassettes) and SRC-004-80 (probe
entrypoint) — all deterministic, NO live network."""
import pathlib

import pytest

from atlas.adapters import run_conformance
from atlas.pilot_adapters import (CourtListenerAdapter, FtcAdapter,
                                  build_pilot_adapter)
from atlas.probe import (MAX_DOCS_PER_SOURCE, ProbeCapExceeded,
                         ProbeNotActivated, plan_probe, run_live_probe)

ROOT = pathlib.Path(__file__).resolve().parent.parent
CAS = ROOT / "tests" / "fixtures" / "cassettes"


def _cl():
    return CourtListenerAdapter(CAS)


def _ftc():
    return FtcAdapter(CAS)


def test_courtlistener_adapter_parses_and_conforms():
    a = _cl()
    leads, cursor = a.discover()
    assert leads and all(ld["url"].startswith("https://www.courtlistener.com")
                         for ld in leads)
    assert all(ld["authority_role"] == "mirror_custodian" for ld in leads)
    assert run_conformance(a) == []


def test_ftc_adapter_parses_and_conforms():
    a = _ftc()
    leads, _ = a.discover()
    assert leads and all(ld["url"].startswith("https://www.ftc.gov") for ld in leads)
    assert all(ld["authority_role"] == "issuer_direct" for ld in leads)
    assert run_conformance(a) == []


def test_builder_and_unregistered_host_refused():
    assert build_pilot_adapter("ftc_enforcement", CAS).source_id == "ftc_enforcement"
    with pytest.raises(ValueError):
        build_pilot_adapter("nope", CAS)


def test_plan_probe_is_network_free_and_capped():
    plan = plan_probe(_cl())
    assert [ld["lead_id"] for ld in plan] == ["cl-9000001", "cl-9000002"]

    class _Big:
        source_id = "big"
        host_allowlist = ["www.ftc.gov"]

        def discover(self, cursor=None):
            start = cursor or 0
            leads = [{"lead_id": f"x{i}", "url": "https://www.ftc.gov/x"}
                     for i in range(60)]
            page = leads[start:start + 10]
            nxt = start + 10 if start + 10 < len(leads) else None
            return page, nxt

    with pytest.raises(ProbeCapExceeded):
        plan_probe(_Big(), max_docs=MAX_DOCS_PER_SOURCE)


def test_live_probe_refuses_without_activation(monkeypatch):
    monkeypatch.delenv("ATLAS_LIVE_FETCH_ACTIVATION", raising=False)
    with pytest.raises(ProbeNotActivated):
        run_live_probe(_cl(), fetcher=lambda *a, **k: (b"", {}),
                       peer_ip_resolver=lambda u: "93.184.216.34")


def test_live_probe_dry_run_with_activation_uses_injected_fetcher(monkeypatch):
    # even 'activated', the fetcher/resolver are INJECTED — this test uses
    # in-memory stand-ins, so still no real network; proves caps + peer-IP
    # validation + receipts without accepted-state writes
    monkeypatch.setenv("ATLAS_LIVE_FETCH_ACTIVATION", "test-token")
    calls = []

    def fetcher(url, max_redirects):
        calls.append(url)
        return b"%PDF-1.7 synthetic", {"status": 200}

    receipts = run_live_probe(_ftc(), fetcher=fetcher,
                              peer_ip_resolver=lambda u: "93.184.216.34")
    assert len(receipts) == len(calls) >= 1
    assert all(r["peer_ip"] == "93.184.216.34" for r in receipts)


def test_live_probe_blocks_rebinding_peer_ip(monkeypatch):
    monkeypatch.setenv("ATLAS_LIVE_FETCH_ACTIVATION", "test-token")
    from atlas.fetchguard import FetchPolicyError
    with pytest.raises(FetchPolicyError):
        run_live_probe(_ftc(), fetcher=lambda *a, **k: (b"x", {}),
                       peer_ip_resolver=lambda u: "169.254.169.254")
