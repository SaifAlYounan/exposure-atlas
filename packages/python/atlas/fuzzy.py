"""Fuzzy match proposals (ID-002).

Uses normalized party names, forum, dates and titles ONLY to *propose*
possible duplicates/relations. It never resolves identity and never merges:

- every result is an advisory ``IdentityMatchProposal`` (``match_kind:
  fuzzy``) that enters human review;
- proposing is read-only — an incorrect proposal cannot mutate any record
  identity (this module holds no resolver state and writes nothing);
- an accepted proposal is applied only as a typed, **reversible**
  ``RecordRelationship`` (via ``atlas.identity.make_relationship``), so merge
  / split / link decisions stay reversible.

Scores and numeric features are emitted as decimal strings (the canonical
serializer forbids floats). Pure and deterministic; no network, credentials
or model calls (A0). ``rule_version`` is persisted so a scoring change is
traceable; TRIAGE/model-scored variants are out of scope (A2).
"""
import datetime
import re

from .canonical import sha256_hex

RULE_VERSION = "fuzzy-rules/v1"
# Propose only at or above this score; below it, no proposal is emitted.
PROPOSE_THRESHOLD = "0.5000"

# Organisation-name noise stripped before comparison.
_SUFFIXES = {"inc", "incorporated", "llc", "llp", "lp", "plc", "corp",
             "corporation", "co", "company", "ltd", "limited", "the", "gmbh",
             "sa", "nv", "ag"}
_WORD = re.compile(r"[a-z0-9]+")


def normalize_name(name: str) -> str:
    toks = [t for t in _WORD.findall(name.lower()) if t not in _SUFFIXES]
    return " ".join(toks)


def _tokens(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    return len(a & b) / len(a | b)


def _dec(x: float) -> str:
    """Fixed 4-decimal string (never a float in the serialized object)."""
    return f"{x:.4f}"


def name_similarity(a: str, b: str) -> str:
    return _dec(_jaccard(_tokens(normalize_name(a)), _tokens(normalize_name(b))))


def title_similarity(a: str, b: str) -> str:
    return _dec(_jaccard(_tokens(a), _tokens(b)))


def date_gap_days(a: str, b: str) -> int:
    da = datetime.date.fromisoformat(a)
    db = datetime.date.fromisoformat(b)
    return abs((da - db).days)


def extract_features(candidate: dict, record: dict) -> dict:
    """Symmetric, float-free feature bundle for a candidate/record pair."""
    feats = {
        "name_jaccard": name_similarity(candidate.get("name", ""), record.get("name", "")),
        "title_jaccard": title_similarity(candidate.get("title", ""), record.get("title", "")),
        "forum_match": bool(candidate.get("forum") and candidate.get("forum") == record.get("forum")),
    }
    if candidate.get("date") and record.get("date"):
        feats["date_gap_days"] = date_gap_days(candidate["date"], record["date"])
    return feats


def score_features(features: dict) -> str:
    """Deterministic weighted score in [0,1] as a decimal string."""
    name = float(features.get("name_jaccard", "0"))
    title = float(features.get("title_jaccard", "0"))
    forum = 1.0 if features.get("forum_match") else 0.0
    gap = features.get("date_gap_days")
    # linear date closeness: 1.0 at same day, 0 at >= 366 days apart
    date_close = 0.0 if gap is None else max(0.0, 1.0 - min(gap, 366) / 366)
    score = 0.55 * name + 0.20 * title + 0.15 * forum + 0.10 * date_close
    return _dec(score)


def propose_match(candidate: dict, record: dict, rule_version: str = RULE_VERSION,
                  threshold: str = PROPOSE_THRESHOLD) -> dict | None:
    """Advisory fuzzy proposal for one candidate/record pair, or None below
    threshold. Never merges — the returned object must go to human review."""
    features = extract_features(candidate, record)
    score = score_features(features)
    if score < threshold:  # decimal strings compare correctly at fixed width
        return None
    proposal = {
        "schema_version": "atlas-identity-match/v1",
        "proposal_id": "imp_" + sha256_hex(
            f"{candidate['candidate_id']}\n{record['record_id']}\n{rule_version}".encode())[:12],
        "candidate_id": candidate["candidate_id"],
        "matched_record_id": record["record_id"],
        "match_kind": "fuzzy",
        "features": features,
        "rule_version": rule_version,
        "score": score,
    }
    return proposal


def propose_matches(candidate: dict, records: list[dict],
                    rule_version: str = RULE_VERSION,
                    threshold: str = PROPOSE_THRESHOLD) -> list[dict]:
    """All above-threshold fuzzy proposals for a candidate, best score first.
    Read-only: generating proposals never changes any record identity."""
    out = [p for r in records if (p := propose_match(candidate, r, rule_version, threshold))]
    return sorted(out, key=lambda p: (p["score"], p["matched_record_id"]), reverse=True)
