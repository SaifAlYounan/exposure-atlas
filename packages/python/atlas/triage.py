"""Boundary rubric and checklist (TRIAGE-001).

Encodes the approved boundary (config/triage/boundary-rubric-v1.yaml) as a
structured checklist. Each criterion returns met/not_met/uncertain/
not_applicable; ``evaluate`` reconstructs the outcome **deterministically**
from the criterion results and the boundary version, so the final outcome is
always reproducible from the recorded checklist. Guarantees:

- a missing criterion can never silently become an include (completeness is
  checked first and routes to review);
- close exclusions (uncertain core criteria) route to human review;
- inaccessible-primary and no-instrument-yet cases route to awaiting_primary.

Deterministic and pure: no network, no credentials, no model calls (A0).
This is the manual/rule path; TRIAGE-002 (model proposal runners) is A2 and
is not implemented here.
"""
import pathlib

import yaml

from .canonical import sha256_hex
from .schemas import validate

ROOT = pathlib.Path(__file__).resolve().parents[3]
RUBRIC_PATH = ROOT / "config" / "triage" / "boundary-rubric-v1.yaml"

RESULT_VALUES = frozenset({"met", "not_met", "uncertain", "not_applicable"})
# proposed_outcome (boundary-proposal schema) vs the fuller pipeline route.
OUTCOMES = frozenset({"include", "exclude", "uncertain"})
ROUTES = frozenset({"include", "exclude", "review", "awaiting_primary"})


class RubricError(ValueError):
    pass


def load_rubric(path: pathlib.Path | None = None) -> dict:
    doc = yaml.safe_load((path or RUBRIC_PATH).read_text())
    validate("boundary-rubric.schema.json", doc)
    return doc


def _by_kind(rubric: dict, kind: str) -> list[str]:
    return [c["id"] for c in rubric["criteria"] if c["kind"] == kind]


def _one(rubric: dict, kind: str) -> str | None:
    ids = _by_kind(rubric, kind)
    return ids[0] if ids else None


def _res(outcome: str, route: str, reason: str, rubric: dict) -> dict:
    return {"outcome": outcome, "route": route, "reason": reason,
            "boundary_version": rubric["boundary_version"],
            "rubric_version": rubric["rubric_version"]}


def evaluate(results: dict, rubric: dict) -> dict:
    """Reconstruct the boundary outcome from criterion results.

    Returns {outcome, route, reason, boundary_version, rubric_version}.
    ``outcome`` is one of include/exclude/uncertain (boundary-proposal enum);
    ``route`` additionally distinguishes review and awaiting_primary.
    """
    crit_ids = [c["id"] for c in rubric["criteria"]]
    bad = {k: v for k, v in results.items() if v not in RESULT_VALUES}
    if bad:
        raise RubricError(f"invalid criterion result(s): {bad}")
    unknown = [k for k in results if k not in crit_ids]
    if unknown:
        raise RubricError(f"result(s) for unknown criteria: {sorted(unknown)}")

    # 1. Completeness: a missing criterion can NEVER silently include.
    missing = [cid for cid in crit_ids if cid not in results]
    if missing:
        return _res("uncertain", "review",
                    f"missing criteria (cannot include): {sorted(missing)}", rubric)

    # 2. Any exclusion met -> exclude.
    met_excl = [cid for cid in _by_kind(rubric, "exclusion") if results[cid] == "met"]
    if met_excl:
        return _res("exclude", "exclude", f"exclusion(s) met: {met_excl}", rubric)

    core = _by_kind(rubric, "core_inclusion")
    # 3. A core inclusion clearly not_met -> outside the substantive boundary.
    not_met = [cid for cid in core if results[cid] == "not_met"]
    if not_met:
        return _res("exclude", "exclude", f"core inclusion not met: {not_met}", rubric)
    # 4. A core inclusion uncertain/not_applicable -> close exclusion -> review.
    unresolved = [cid for cid in core if results[cid] in ("uncertain", "not_applicable")]
    if unresolved:
        return _res("uncertain", "review",
                    f"core inclusion unresolved: {unresolved}", rubric)

    # 5. All core inclusion met. Gating decides include vs awaiting_primary.
    instrument = _one(rubric, "instrument")
    accessibility = _one(rubric, "accessibility")
    signal = _one(rubric, "investigation_signal")
    if instrument is None or accessibility is None:
        raise RubricError("rubric must define one instrument and one accessibility criterion")

    if results[instrument] != "met":
        if signal and results.get(signal) == "met":
            return _res("uncertain", "awaiting_primary",
                        "announced investigation; no authoritative instrument yet", rubric)
        return _res("uncertain", "review",
                    "no authoritative instrument and no announced investigation", rubric)
    if results[accessibility] != "met":
        return _res("uncertain", "awaiting_primary",
                    "authoritative instrument not lawfully accessible (inaccessible-primary)", rubric)
    return _res("include", "include",
                "all core inclusion + instrument + accessibility met; no exclusions", rubric)


def build_proposal(candidate_id: str, results: dict, rubric: dict,
                   proposed_by: str = "manual", anchors: dict | None = None) -> dict:
    """Build a schema-valid BoundaryProposal from a completed checklist.

    ``proposed_by`` is 'manual' here (TRIAGE-001). The proposal records every
    criterion result so the outcome is reconstructable; it never records a
    bare include without the full checklist.
    """
    anchors = anchors or {}
    outcome = evaluate(results, rubric)["outcome"]
    ordered = [c["id"] for c in rubric["criteria"]]
    digest = sha256_hex(
        (f"{candidate_id}\n{rubric['boundary_version']}\n"
         + "\n".join(f"{cid}={results.get(cid, 'MISSING')}" for cid in ordered)).encode())
    proposal = {
        "schema_version": "atlas-boundary-proposal/v1",
        "proposal_id": "bpr_" + digest[:12],
        "candidate_id": candidate_id,
        "boundary_version": rubric["boundary_version"],
        "criteria": [
            {"criterion": cid, "result": results[cid], "anchor_ids": anchors.get(cid, [])}
            for cid in ordered if cid in results
        ],
        "proposed_outcome": outcome,
        "proposed_by": proposed_by,
    }
    validate("boundary-proposal.schema.json", proposal)
    return proposal
