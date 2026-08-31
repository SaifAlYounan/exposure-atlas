"""Approved pilot source adapters (SRC-004): CourtListener/RECAP (court
feed/API, mirror custodian) and FTC enforcement (regulator, issuer).

Deterministic over recorded cassettes; NO live network in this module.
Live fetching is SRC-004-80, gated separately (D-027). Adapters produce
candidates and bytes only — they hold no capability to write accepted
domain state (SRC-001 invariant), enforced by run_conformance.
"""
import json
import pathlib
import re
from html.parser import HTMLParser

from .fetchguard import validate_url

PAGE_SIZE = 2


class _FtcListingParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href = None
        self._buf = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for k, v in attrs:
                if k == "href":
                    self._href = v
                    self._buf = []

    def handle_data(self, data):
        if self._href is not None:
            self._buf.append(data)

    def handle_endtag(self, tag):
        if tag == "a" and self._href is not None:
            self.links.append((self._href, "".join(self._buf).strip()))
            self._href = None


class _PilotAdapterBase:
    source_id = ""
    host_allowlist: list[str] = []

    def __init__(self, cassette_dir: pathlib.Path):
        self.cassette_dir = pathlib.Path(cassette_dir)

    def _leads(self) -> list[dict]:
        raise NotImplementedError

    def discover(self, cursor: int | None = None):
        leads = self._leads()
        start = cursor or 0
        page = leads[start:start + PAGE_SIZE]
        for lead in page:
            validate_url(lead["url"], self.host_allowlist)
        nxt = start + len(page) if start + len(page) < len(leads) else None
        return page, nxt

    def healthcheck(self) -> dict:
        return {"source_id": self.source_id, "state": "ok",
                "expected_volume": len(self._leads())}


class CourtListenerAdapter(_PilotAdapterBase):
    source_id = "courtlistener_recap"
    host_allowlist = ["www.courtlistener.com", "storage.courtlistener.com"]

    def _leads(self) -> list[dict]:
        doc = json.loads((self.cassette_dir / "courtlistener_listing.json").read_text())
        leads = []
        for r in doc["results"]:
            leads.append({
                "lead_id": f"cl-{r['id']}",
                "url": f"https://www.courtlistener.com{r['absolute_url']}",
                "case_name": r["case_name"],
                "docket_number": r.get("docket_number"),
                "date_filed": r.get("date_filed"),
                # authority: issuing court; CL is custodian/mirror — copy
                # provenance stays 'unverified' until corroborated (SP-05)
                "authority_role": "mirror_custodian"})
        return sorted(leads, key=lambda x: x["lead_id"])


class FtcAdapter(_PilotAdapterBase):
    source_id = "ftc_enforcement"
    host_allowlist = ["www.ftc.gov"]

    def _leads(self) -> list[dict]:
        html = (self.cassette_dir / "ftc_listing.html").read_bytes().decode("utf-8")
        p = _FtcListingParser()
        p.feed(html)
        leads = []
        dates = re.findall(r'class="date">([0-9-]+)<', html)
        for i, (href, title) in enumerate(p.links):
            path = href if href.startswith("http") else f"https://www.ftc.gov{href}"
            leads.append({
                "lead_id": f"ftc-{i:03d}",
                "url": path, "case_name": title,
                "date": dates[i] if i < len(dates) else None,
                "authority_role": "issuer_direct"})
        return sorted(leads, key=lambda x: x["lead_id"])


def build_pilot_adapter(source_id: str, cassette_dir: pathlib.Path):
    for cls in (CourtListenerAdapter, FtcAdapter):
        if cls.source_id == source_id:
            return cls(cassette_dir)
    raise ValueError(f"no pilot adapter for {source_id!r}")
