#!/usr/bin/env python3
"""SRC-004-80 runnable live-probe entrypoint (activated by D-028).

Runs ONLY inside the operator-approved `live-fetch` GitHub Environment,
which injects ATLAS_LIVE_FETCH_ACTIVATION. Discovery is driven by the
DISC-002 versioned query library; every lead is logged into the DISC-001
candidate ledger (idempotent). Acquisition is per-source:
  - ftc_enforcement: fetch the case page (HTML) and canonicalize.
  - courtlistener_recap: MIRROR custodian — resolve the opinion cluster
    via the CL v4 API and capture the opinion text field (plain_text /
    html*), never the 202-empty HTML view (SRC-FIND-01). The v4 DATA
    endpoints require an authenticated token (SRC-FIND-03); it is sent as
    `Authorization: Token …` ONLY to CL hosts, from the operator-provisioned
    CL_API_TOKEN secret (D-030), and never emitted. Copy provenance stays
    'unverified' until corroborated by the issuing court (SP-05).
Enforces D-021 caps; validates the connected peer IP; emits a SAFE
summary (hashes + metadata + candidate ids + discovery-run record —
never raw source bytes, R-17/SPEC 2.3). Writes nothing to the repository.
"""
import argparse
import json
import os
import pathlib
import re
import socket
import sys
import urllib.request
from urllib.parse import quote_plus, urlsplit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "packages" / "python"))

from atlas.canonical import sha256_hex  # noqa: E402
from atlas.discovery import (CandidateLedger, QueryLibrary,  # noqa: E402
                             make_discovery_run, utcnow)
from atlas.documents import (canonicalize_text, html_to_canonical,  # noqa: E402
                             pdf_to_canonical)
from atlas.fetchguard import (FetchPolicyError, bounded_bytes,  # noqa: E402
                              sniff_kind, validate_peer_ip, validate_url)
from atlas.probe import MAX_DOCS_PER_SOURCE, ProbeNotActivated  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
QLIB = ROOT / "config" / "queries" / "v1.yaml"
USER_AGENT = ("ExposureAtlas-pilot-probe/0.2 "
              "(+A1 read-only evaluation; contact operator)")

SOURCES = {
    "ftc_enforcement": {
        "hosts": ["www.ftc.gov"],
        "kind": "ftc_html",
    },
    "courtlistener_recap": {
        "hosts": ["www.courtlistener.com", "storage.courtlistener.com"],
        "kind": "courtlistener_api",
        "authority_role": "mirror_custodian",
    },
}
# CL opinion content fields, in preference order (text captured, not stored)
CL_CONTENT_FIELDS = ["plain_text", "html_with_citations", "html",
                     "html_lawbox", "html_columbia", "xml_harvard"]
# CourtListener v4 DATA endpoints require an authenticated API token
# (anonymous -> HTTP 401; see SRC-FIND-03). The token is injected ONLY on
# the protected live-fetch environment (operator-provisioned CL_API_TOKEN
# secret). It is sent as `Authorization: Token <token>` and ONLY to these
# hosts, and is NEVER written to the summary or any log (D-030).
CL_AUTH_HOSTS = {"www.courtlistener.com"}


def _cl_auth_header(url: str) -> dict:
    """CL API token header, only for CL hosts and only if the token is set."""
    if urlsplit(url).hostname not in CL_AUTH_HOSTS:
        return {}
    tok = os.environ.get("CL_API_TOKEN", "").strip()
    return {"Authorization": f"Token {tok}"} if tok else {}


def _resolve_peer_ip(url: str) -> str:
    return socket.gethostbyname(urlsplit(url).hostname)


def _fetch(url: str, hosts: list[str], timeout: int = 30,
           extra_headers: dict | None = None) -> tuple[bytes, dict]:
    validate_url(url, hosts)
    validate_peer_ip(_resolve_peer_ip(url))  # DNS-rebinding defence
    headers = {"User-Agent": USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        final = resp.geturl()
        validate_url(final, hosts)
        return bounded_bytes(resp.read()), {"status": resp.status,
                                            "final_url": final}


def _fetch_retry(url: str, hosts: list[str], timeout: int, attempts: int = 3,
                 extra_headers: dict | None = None):
    import time
    last = None
    for i in range(attempts):
        try:
            return _fetch(url, hosts, timeout=timeout,
                          extra_headers=extra_headers)
        except (TimeoutError, OSError) as e:
            last = e
            if i < attempts - 1:
                time.sleep(3 * (i + 1))
    raise last


def _listing_url(source_id: str, query: str) -> str:
    q = quote_plus(query)
    if source_id == "ftc_enforcement":
        return (f"https://www.ftc.gov/legal-library/browse/cases-proceedings"
                f"?search={q}&sort_by=field_date")
    if source_id == "courtlistener_recap":
        return (f"https://www.courtlistener.com/api/rest/v4/search/"
                f"?q={q}&type=o&page_size=20")
    raise ValueError(source_id)


def _cl_cluster_id(opinion_url: str) -> str | None:
    m = re.search(r"/opinion/(\d+)/", opinion_url)
    return m.group(1) if m else None


def _discover(source_id: str, query: str, hosts: list[str], max_docs: int):
    listing = _listing_url(source_id, query)
    data, _ = _fetch_retry(listing, hosts, timeout=60,
                           extra_headers=_cl_auth_header(listing))
    leads = []
    if source_id == "courtlistener_recap":
        doc = json.loads(data.decode("utf-8"))
        for r in doc.get("results", [])[:max_docs]:
            u = r.get("absolute_url") or ""
            if not u:
                continue
            url = f"https://www.courtlistener.com{u}"
            cid = _cl_cluster_id(url)
            leads.append({"lead_id": f"cl-{cid or 'nokey'}", "url": url,
                          "cluster_id": cid})
    else:  # ftc_html
        html = data.decode("utf-8", "replace")
        for m in re.findall(
                r'href="(/legal-library/browse/cases-proceedings/[^"]+)"',
                html)[:max_docs]:
            leads.append({"lead_id": f"ftc-{abs(hash(m)) % 10**8}",
                          "url": f"https://www.ftc.gov{m}", "cluster_id": None})
    return leads[:max_docs]


def _acquire(source_id: str, lead: dict, hosts: list[str]) -> dict:
    """Return metadata-only acquisition record (no raw text)."""
    rec = {"lead_id": lead["lead_id"], "url": lead["url"]}
    if source_id == "courtlistener_recap":
        # MIRROR path: resolve opinion text via the CL API, not the HTML view.
        cid = lead.get("cluster_id")
        if not cid:
            rec["error"] = "no cluster id parsed from opinion url"
            return rec
        api = (f"https://www.courtlistener.com/api/rest/v4/opinions/"
               f"?cluster={cid}&page_size=1")
        auth = _cl_auth_header(api)
        rec["authenticated"] = bool(auth)  # metadata only; never the token
        data, meta = _fetch(api, hosts, timeout=60, extra_headers=auth)
        rec["http_status"] = meta["status"]
        doc = json.loads(data.decode("utf-8"))
        results = doc.get("results", [])
        if not results:
            rec["error"] = "no opinion in cluster"
            rec["result_keys"] = sorted(doc.keys())  # safe: key names only
            return rec
        op = results[0]
        field = next((f for f in CL_CONTENT_FIELDS if op.get(f)), None)
        if field is None:
            rec["error"] = "no populated content field"
            rec["available_keys"] = sorted(op.keys())  # safe: key names only
            return rec
        text = op[field]
        rec["content_field"] = field
        rec["copy_provenance_state"] = "unverified"  # mirror; SP-05
        canon = (html_to_canonical(text.encode("utf-8")) if field.startswith("html")
                 else canonicalize_text(text))
        rec["canonical_sha256"] = sha256_hex(canon)
        rec["canonical_len"] = len(canon)
        return rec
    # ftc_html: fetch the case page directly
    data, meta = _fetch(lead["url"], hosts, timeout=30)
    rec["sha256"] = sha256_hex(data)
    rec["bytes"] = len(data)
    rec["http_status"] = meta["status"]
    kind = sniff_kind(data)
    rec["kind"] = kind
    if kind == "html":
        canon = html_to_canonical(data)
    elif kind == "pdf":
        canon, _pm = pdf_to_canonical(data)
    else:
        rec["note"] = "unknown kind; quarantined, not canonicalized"
        return rec
    rec["canonical_sha256"] = sha256_hex(canon)
    rec["canonical_len"] = len(canon)
    return rec


def probe(source_id: str, max_docs: int) -> dict:
    if source_id not in SOURCES:
        raise SystemExit(f"unknown source {source_id!r}")
    max_docs = min(max_docs, MAX_DOCS_PER_SOURCE)
    cfg = SOURCES[source_id]
    qlib = QueryLibrary(QLIB)
    at = utcnow()
    query = qlib.active(source_id, at[:10])
    ledger = CandidateLedger()
    result = {"source_id": source_id, "max_docs": max_docs,
              "query_id": query["query_id"], "query_version": query["version"],
              "leads_discovered": 0, "documents": [], "errors": []}
    try:
        leads = _discover(source_id, query["query"], cfg["hosts"], max_docs)
    except Exception as e:  # source-scope failure degrades only this source
        result["errors"].append(f"discovery_failed: {type(e).__name__}: {e}")
        result["discovery_run"] = make_discovery_run(
            run_id=os.environ.get("GITHUB_RUN_ID", "local"), source_id=source_id,
            query=query, leads_seen=0, new_candidates=0,
            updated_observations=0, at=at, failures=result["errors"])
        return result
    result["leads_discovered"] = len(leads)
    new, updated = 0, 0
    for lead in leads:
        cand, is_new = ledger.intake(
            source_id=source_id, lead_url=lead["url"],
            query_version=query["version"],
            run_id=os.environ.get("GITHUB_RUN_ID", "local"),
            boundary_version="1.0.0", at=at)
        new += int(is_new)
        updated += int(not is_new)
        rec = {"candidate_id": cand["candidate_id"]}
        try:
            rec.update(_acquire(source_id, lead, cfg["hosts"]))
        except (FetchPolicyError, Exception) as e:  # noqa: BLE001
            rec.update(lead_id=lead["lead_id"], url=lead["url"],
                       error=f"{type(e).__name__}: {e}")
        result["documents"].append(rec)
    result["discovery_run"] = make_discovery_run(
        run_id=os.environ.get("GITHUB_RUN_ID", "local"), source_id=source_id,
        query=query, leads_seen=len(leads), new_candidates=new,
        updated_observations=updated, at=at)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--max-docs", type=int, default=10)
    ap.add_argument("--out", default="probe-summary.json")
    a = ap.parse_args()
    if not os.environ.get("ATLAS_LIVE_FETCH_ACTIVATION"):
        raise ProbeNotActivated(
            "run_probe.py refuses to run without the live-fetch environment "
            "activation token (D-027).")
    try:
        summary = probe(a.source, a.max_docs)
    except Exception as e:  # noqa: BLE001 - always emit a diagnosable summary
        summary = {"source_id": a.source, "leads_discovered": 0,
                   "documents": [],
                   "errors": [f"fatal: {type(e).__name__}: {e}"]}
    pathlib.Path(a.out).write_text(json.dumps(summary, indent=1) + "\n")
    canon = sum(1 for d in summary["documents"] if d.get("canonical_sha256"))
    print(json.dumps(summary, indent=1))
    ok = summary["leads_discovered"] > 0 and canon > 0 and not summary["errors"]
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
