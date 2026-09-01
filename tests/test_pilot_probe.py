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


def test_run_probe_entrypoint_refuses_without_token(monkeypatch):
    import importlib.util
    import pathlib as _pl
    monkeypatch.delenv("ATLAS_LIVE_FETCH_ACTIVATION", raising=False)
    spec = importlib.util.spec_from_file_location(
        "run_probe", _pl.Path(__file__).resolve().parent.parent / "tools" / "run_probe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr("sys.argv", ["run_probe.py", "--source", "ftc_enforcement"])
    from atlas.probe import ProbeNotActivated
    import pytest as _pt
    with _pt.raises(ProbeNotActivated):
        mod.main()
    # DISCOVERY config only covers the two approved pilot sources
    assert set(mod.SOURCES) == {"courtlistener_recap", "ftc_enforcement"}


def test_run_probe_listing_url_and_cl_cluster_id(monkeypatch):
    import importlib.util
    import pathlib as _pl
    spec = importlib.util.spec_from_file_location(
        "run_probe2", _pl.Path(__file__).resolve().parent.parent / "tools" / "run_probe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # query-library-driven listing URLs carry the query
    ftc = mod._listing_url("ftc_enforcement", "artificial intelligence")
    assert ftc.startswith("https://www.ftc.gov/") and "artificial+intelligence" in ftc
    cl = mod._listing_url("courtlistener_recap", "artificial intelligence")
    assert "/api/rest/v4/search/" in cl and "type=o" in cl
    # CL lead_id derives the cluster id from the opinion URL (fixes cl-None)
    assert mod._cl_cluster_id(
        "https://www.courtlistener.com/opinion/1933074/artificial-intelligence-corp-v-casey/") == "1933074"
    assert mod._cl_cluster_id("https://www.courtlistener.com/x/") is None
    # sources restricted to the two approved pilots
    assert set(mod.SOURCES) == {"ftc_enforcement", "courtlistener_recap"}


def test_query_library_active_across_boundary_window():
    from atlas.discovery import QueryLibrary
    import pathlib as _pl
    lib = QueryLibrary(_pl.Path(__file__).resolve().parent.parent
                       / "config" / "queries" / "v1.yaml")
    # active for any date within the declared boundary window (2015->open),
    # including the smoke run dates
    for as_of in ("2026-08-31", "2026-09-01", "2027-01-01"):
        assert lib.active("courtlistener_recap", as_of)["query_id"] \
            == "q_courtlistener_ai_opinions"
        assert lib.active("ftc_enforcement", as_of)["query_id"] == "q_ftc_ai_matters"


def test_cl_auth_header_scoped_to_cl_hosts_only(monkeypatch):
    """D-030/SRC-FIND-03: the CL API token is attached ONLY to CourtListener
    hosts and ONLY when the secret is present; nothing else ever sees it."""
    import importlib.util
    import pathlib as _pl
    spec = importlib.util.spec_from_file_location(
        "run_probe4", _pl.Path(__file__).resolve().parent.parent / "tools" / "run_probe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    cl_api = "https://www.courtlistener.com/api/rest/v4/opinions/?cluster=1"
    ftc = "https://www.ftc.gov/legal-library/browse/cases-proceedings/x"
    # no token set -> no header anywhere (anonymous -> 401 by design)
    monkeypatch.delenv("CL_API_TOKEN", raising=False)
    assert mod._cl_auth_header(cl_api) == {}
    assert mod._cl_auth_header(ftc) == {}
    # token set -> header on CL host only, never on FTC (no cross-host leak)
    monkeypatch.setenv("CL_API_TOKEN", "SECRET-abc123")
    assert mod._cl_auth_header(cl_api) == {"Authorization": "Token SECRET-abc123"}
    assert mod._cl_auth_header(ftc) == {}


def test_run_probe_main_always_writes_summary(tmp_path, monkeypatch):
    import importlib.util
    import pathlib as _pl
    spec = importlib.util.spec_from_file_location(
        "run_probe3", _pl.Path(__file__).resolve().parent.parent / "tools" / "run_probe.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setenv("ATLAS_LIVE_FETCH_ACTIVATION", "t")
    monkeypatch.setattr(mod, "probe",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = tmp_path / "s.json"
    monkeypatch.setattr("sys.argv",
                        ["run_probe.py", "--source", "ftc_enforcement", "--out", str(out)])
    import pytest as _pt
    with _pt.raises(SystemExit):
        mod.main()
    import json as _json
    doc = _json.loads(out.read_text())
    assert doc["errors"] and "fatal" in doc["errors"][0]  # summary always emitted
