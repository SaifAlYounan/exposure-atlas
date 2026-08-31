#!/usr/bin/env python3
"""SRC-004-80 runnable live-probe entrypoint (activated by D-028).

Runs ONLY inside the operator-approved `live-fetch` GitHub Environment,
which injects ATLAS_LIVE_FETCH_ACTIVATION after the operator approves the
specific run. Enforces the D-021 caps, validates the connected peer IP
(defence in depth behind harden-runner egress-block), runs each fetched
document through canonicalization, and emits a SAFE summary (hashes and
metadata only — never raw source bytes, per R-17 / SPEC 2.3). Writes
nothing to the repository.

Usage: run_probe.py --source <courtlistener_recap|ftc_enforcement>
                    [--max-docs N] [--out summary.json]
"""
import argparse
import json
import pathlib
import socket
import sys
import urllib.request
from urllib.parse import urlsplit

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent
                       / "packages" / "python"))

from atlas.documents import html_to_canonical, pdf_to_canonical  # noqa: E402
from atlas.fetchguard import (FetchPolicyError, bounded_bytes,  # noqa: E402
                              sniff_kind, validate_peer_ip, validate_url)
from atlas.probe import (MAX_DOCS_PER_SOURCE, ProbeNotActivated)  # noqa: E402
from atlas.canonical import sha256_hex  # noqa: E402

# Smoke-query library placeholder (production query versioning is DISC-002).
DISCOVERY = {
    "courtlistener_recap": {
        "hosts": ["www.courtlistener.com", "storage.courtlistener.com"],
        "listing": "https://www.courtlistener.com/api/rest/v4/search/"
                   "?q=artificial+intelligence&type=o&page_size=20",
        "kind": "courtlistener_api",
    },
    "ftc_enforcement": {
        "hosts": ["www.ftc.gov"],
        "listing": "https://www.ftc.gov/legal-library/browse/cases-proceedings"
                   "?search=artificial+intelligence&sort_by=field_date",
        "kind": "ftc_html",
    },
}
USER_AGENT = "ExposureAtlas-pilot-probe/0.1 (+A1 read-only evaluation; contact operator)"


def _resolve_peer_ip(url: str) -> str:
    host = urlsplit(url).hostname
    return socket.gethostbyname(host)


def _fetch(url: str, allowed_hosts: list[str], timeout: int = 30) -> tuple[bytes, dict]:
    validate_url(url, allowed_hosts)
    validate_peer_ip(_resolve_peer_ip(url))  # DNS-rebinding defence
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        final = resp.geturl()
        validate_url(final, allowed_hosts)  # re-check after redirects
        data = bounded_bytes(resp.read())
        return data, {"status": resp.status, "final_url": final,
                      "content_type": resp.headers.get("Content-Type", "")}


def _discover(cfg: dict, max_docs: int) -> list[dict]:
    import time
    last = None
    for attempt in range(3):  # search backends can be slow; bounded retry
        try:
            data, meta = _fetch(cfg["listing"], cfg["hosts"], timeout=60)
            break
        except (TimeoutError, OSError) as e:
            last = e
            if attempt < 2:
                time.sleep(3 * (attempt + 1))
    else:
        raise last
    leads = []
    if cfg["kind"] == "courtlistener_api":
        doc = json.loads(data.decode("utf-8"))
        for r in doc.get("results", [])[:max_docs]:
            u = r.get("absolute_url") or ""
            if u:
                leads.append({"lead_id": f"cl-{r.get('id')}",
                              "url": f"https://www.courtlistener.com{u}"})
    else:  # ftc_html — extract case links defensively
        import re
        html = data.decode("utf-8", "replace")
        for m in re.findall(r'href="(/legal-library/browse/cases-proceedings/[^"]+)"',
                            html)[:max_docs]:
            leads.append({"lead_id": f"ftc-{abs(hash(m)) % 10**8}",
                          "url": f"https://www.ftc.gov{m}"})
    return leads[:max_docs]


def probe(source_id: str, max_docs: int) -> dict:
    if source_id not in DISCOVERY:
        raise SystemExit(f"unknown source {source_id!r}")
    max_docs = min(max_docs, MAX_DOCS_PER_SOURCE)
    cfg = DISCOVERY[source_id]
    result = {"source_id": source_id, "max_docs": max_docs,
              "leads_discovered": 0, "documents": [], "errors": []}
    try:
        leads = _discover(cfg, max_docs)
    except Exception as e:  # source-scope failure degrades only this source
        result["errors"].append(f"discovery_failed: {type(e).__name__}: {e}")
        return result
    result["leads_discovered"] = len(leads)
    for lead in leads:
        rec = {"lead_id": lead["lead_id"], "url": lead["url"]}
        try:
            data, meta = _fetch(lead["url"], cfg["hosts"])
            rec["sha256"] = sha256_hex(data)
            rec["bytes"] = len(data)
            rec["http_status"] = meta["status"]
            kind = sniff_kind(data)
            rec["kind"] = kind
            if kind == "html":
                canon = html_to_canonical(data)
                rec["canonical_sha256"] = sha256_hex(canon)
                rec["canonical_len"] = len(canon)
            elif kind == "pdf":
                canon, _pm = pdf_to_canonical(data)
                rec["canonical_sha256"] = sha256_hex(canon)
                rec["canonical_len"] = len(canon)
            else:
                rec["note"] = "unknown kind; quarantined, not canonicalized"
        except (FetchPolicyError, Exception) as e:  # noqa: BLE001
            rec["error"] = f"{type(e).__name__}: {e}"
        result["documents"].append(rec)
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", required=True)
    ap.add_argument("--max-docs", type=int, default=10)
    ap.add_argument("--out", default="probe-summary.json")
    a = ap.parse_args()
    # Refuse unless the protected environment injected the activation token.
    import os
    if not os.environ.get("ATLAS_LIVE_FETCH_ACTIVATION"):
        raise ProbeNotActivated(
            "run_probe.py refuses to run without the live-fetch environment "
            "activation token (D-027).")
    summary = probe(a.source, a.max_docs)
    # SAFE artifact: hashes + metadata only, never raw bytes (R-17/SPEC 2.3)
    pathlib.Path(a.out).write_text(json.dumps(summary, indent=1) + "\n")
    ok = summary["leads_discovered"] > 0 and not summary["errors"]
    print(json.dumps(summary, indent=1))
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
