"""Candidate ledger (DISC-001) and versioned query library (DISC-002).

DISC-001: every discovery lead is persisted with source/query version,
run, retrieval state, a deterministic fingerprint and disposition.
Rediscovering the same lead appends an OBSERVATION rather than
duplicating the candidate. Excluded candidates are preserved so a
boundary change can replay them. Every exclusion records a controlled
reason and boundary version. A partial adapter outage makes the run's
coverage state degraded, never successful.

DISC-002: queries are versioned, effective-dated and traceable; each run
records the exact query version; a query change is flagged for backfill;
result counts below the query's expected band are flagged.
"""
import datetime
import pathlib
from urllib.parse import urlsplit, urlunsplit

import yaml

from .canonical import sha256_hex
from .schemas import validate

EXCLUSION_REASONS = {"out_of_boundary", "duplicate_lead", "secondary_only",
                     "inaccessible", "superseded_query", "operator_excluded"}


def normalize_url(url: str) -> str:
    p = urlsplit(url.strip())
    scheme = (p.scheme or "https").lower()
    netloc = p.netloc.lower()
    path = p.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, "", ""))  # drop query+fragment


def candidate_id(source_id: str, lead_url: str) -> str:
    fp = sha256_hex(f"{source_id}\n{normalize_url(lead_url)}".encode())
    return "cnd_" + fp[:16]


class CandidateLedger:
    """In-memory ledger; the DOM-002 tables persist it when an engine is
    wired (later atom). Idempotent by candidate fingerprint."""

    def __init__(self):
        self.candidates: dict[str, dict] = {}
        self.observations: dict[str, list[dict]] = {}

    def intake(self, *, source_id: str, lead_url: str, query_version: str,
               run_id: str, boundary_version: str, at: str) -> tuple[dict, bool]:
        cid = candidate_id(source_id, lead_url)
        is_new = cid not in self.candidates
        obs = {"run_id": run_id, "query_version": query_version, "at": at,
               "lead_url": lead_url}
        self.observations.setdefault(cid, []).append(obs)
        if is_new:
            cand = {"schema_version": "atlas-candidate/v1", "candidate_id": cid,
                    "source_id": source_id, "lead_url": normalize_url(lead_url),
                    "query_version": query_version, "discovered_at": at,
                    "work_state": "open", "disposition": "unresolved",
                    "boundary_version": boundary_version}
            validate("candidate.schema.json", cand)
            self.candidates[cid] = cand
        return self.candidates[cid], is_new

    def exclude(self, candidate_id_: str, *, reason: str, boundary_version: str):
        if reason not in EXCLUSION_REASONS:
            raise ValueError(f"uncontrolled exclusion reason {reason!r}")
        cand = self.candidates[candidate_id_]
        cand["disposition"] = "excluded"
        cand["exclusion_reason"] = reason
        cand["boundary_version"] = boundary_version
        validate("candidate.schema.json", cand)

    def replay_excluded(self, *, new_boundary_version: str) -> list[dict]:
        """On a boundary change, excluded candidates are re-openable so the
        new boundary can re-evaluate them (SPEC DISC-001)."""
        out = []
        for c in self.candidates.values():
            if (c["disposition"] == "excluded"
                    and c.get("boundary_version") != new_boundary_version):
                out.append(c)
        return out

    def observation_count(self, candidate_id_: str) -> int:
        return len(self.observations.get(candidate_id_, []))


class QueryLibrary:
    def __init__(self, path: pathlib.Path):
        self.doc = yaml.safe_load(pathlib.Path(path).read_text())
        self.library_version = self.doc["library_version"]
        for q in self.doc["queries"]:
            validate("query-definition.schema.json",
                     {"schema_version": "atlas-query-definition/v1", **q})

    def active(self, source_id: str, as_of: str) -> dict:
        cands = [q for q in self.doc["queries"]
                 if q["source_id"] == source_id
                 and q["effective_from"] <= as_of
                 and (q["effective_to"] is None or as_of <= q["effective_to"])]
        if not cands:
            raise KeyError(f"no active query for {source_id} as of {as_of}")
        # latest effective_from wins
        return max(cands, key=lambda q: (q["effective_from"], q["version"]))

    def needs_backfill(self, prev_version: str | None, source_id: str,
                       as_of: str) -> bool:
        """A query change triggers a backfill/reconciliation decision."""
        return prev_version is not None and \
            prev_version != self.active(source_id, as_of)["version"]


def make_discovery_run(*, run_id: str, source_id: str, query: dict,
                       leads_seen: int, new_candidates: int,
                       updated_observations: int, at: str,
                       failures: list[str] | None = None,
                       adapter_degraded: bool = False) -> dict:
    failures = failures or []
    coverage = "failed" if (failures and leads_seen == 0) else \
        "partial" if (failures or adapter_degraded) else "complete"
    run = {"schema_version": "atlas-discovery-run/v1", "run_id": run_id,
           "source_id": source_id, "query_id": query["query_id"],
           "query_version": query["version"],
           "window_from": None, "window_to": None, "started_at": at,
           "coverage_state": coverage, "leads_seen": leads_seen,
           "new_candidates": new_candidates,
           "updated_observations": updated_observations,
           "failures": failures,
           "below_expected_band":
               leads_seen < query.get("expected_min_results", 0)}
    validate("discovery-run.schema.json", run)
    return run


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
