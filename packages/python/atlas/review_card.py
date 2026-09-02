"""Review-task builder — decision cards (REV-002).

Assembles one decision card that asks a single bounded question and carries
the evidence to answer it (SPEC §9 REV-002). Enforced invariants:

- every source-derived assertion links directly to its evidence (non-empty
  anchor support); every derived edit links to accepted parent assertions and
  a versioned transform;
- OCR and superseded-source warnings are always surfaced — there is no way to
  suppress them through this builder;
- classification edits require a taxonomy rationale, never source anchors;
- restricted content is never placed in a channel-safe summary (email / chat /
  unauthenticated link) — only an authenticated view carries it;
- model votes are short decision evidence — a chain-of-thought field is
  rejected and rationales are length-capped.

Pure and deterministic; no network, credentials or model calls (A0).
"""
from .canonical import sha256_hex
from .schemas import validate


class CardError(ValueError):
    pass


def _assertion_ok(a: dict) -> None:
    kind = a.get("kind")
    if kind == "source_derived":
        if not a.get("support"):
            raise CardError(
                f"source-derived assertion {a.get('assertion_ref')!r} has no anchor support")
    elif kind == "derived":
        d = a.get("derivation") or {}
        if not d.get("parent_assertion_ids") or not d.get("transform_version"):
            raise CardError(
                f"derived assertion {a.get('assertion_ref')!r} needs accepted parents + a transform_version")
    else:
        raise CardError(f"assertion {a.get('assertion_ref')!r} has unknown kind {kind!r}")


def _classification_ok(c: dict) -> None:
    if c.get("is_edit") and not c.get("taxonomy_rationale"):
        raise CardError("a classification edit requires a taxonomy_rationale (not source anchors)")
    if "support" in c or "anchor_ids" in c:
        raise CardError("classifications carry taxonomy rationale, never source anchors")


def _votes_ok(votes: list[dict]) -> None:
    for v in votes:
        if "chain_of_thought" in v or "reasoning_trace" in v:
            raise CardError("model votes must not carry chain-of-thought")
        if len(v.get("rationale", "")) > 600:
            raise CardError("model rationale must be short decision evidence (<=600 chars)")


def build_card(*, task_id: str, question: str, requested_decision: str,
               proposed_answer: str, issuer: dict, source_version_id: str,
               rights_state: str, security_state: str, restricted: bool,
               restrictive_default: str, expiry: str, options: list[dict],
               assertions: list[dict] | None = None,
               classifications: list[dict] | None = None,
               model_votes: list[dict] | None = None,
               verifier_results: list[dict] | None = None,
               duplicates: list[str] | None = None,
               boundary_ref: dict | None = None,
               diff_summary: str | None = None,
               canonical: dict | None = None,
               alternatives: list[str] | None = None,
               ocr_detected: bool = False,
               superseded_source: bool = False,
               extra_warnings: list[dict] | None = None) -> dict:
    """Build and validate a decision card, enforcing the REV-002 invariants.

    ``ocr_detected`` / ``superseded_source`` are surfaced as warnings that the
    caller cannot omit.
    """
    assertions = assertions or []
    classifications = classifications or []
    model_votes = model_votes or []
    for a in assertions:
        _assertion_ok(a)
    for c in classifications:
        _classification_ok(c)
    _votes_ok(model_votes)

    warnings = list(extra_warnings or [])
    if ocr_detected:
        warnings.append({"kind": "ocr", "detail": "OCR-derived text; verify against the source render."})
    if superseded_source:
        warnings.append({"kind": "superseded_source",
                         "detail": "A newer source version exists; this card is built on a superseded version."})

    card = {
        "schema_version": "atlas-review-card/v1",
        "card_id": "rvc_" + sha256_hex(f"{task_id}\n{question}\n{source_version_id}".encode())[:12],
        "task_id": task_id,
        "question": question,
        "requested_decision": requested_decision,
        "proposed_answer": proposed_answer,
        "issuer": issuer,
        "source_version_id": source_version_id,
        "rights_state": rights_state,
        "security_state": security_state,
        "restricted": restricted,
        "assertions": assertions,
        "options": options,
        "warnings": warnings,
        "restrictive_default": restrictive_default,
        "expiry": expiry,
    }
    for k, v in (("alternatives", alternatives), ("canonical", canonical),
                 ("classifications", classifications or None),
                 ("model_votes", model_votes or None),
                 ("verifier_results", verifier_results),
                 ("duplicates", duplicates), ("boundary_ref", boundary_ref),
                 ("diff_summary", diff_summary)):
        if v:
            card[k] = v
    validate("review-card.schema.json", card)
    return card


# Fields that may carry restricted content and must never reach a channel-safe
# summary (only the authenticated view shows them).
_RESTRICTED_FIELDS = ("canonical", "assertions", "model_votes", "classifications",
                      "diff_summary", "verifier_results", "proposed_answer",
                      "alternatives")


def channel_safe_summary(card: dict) -> dict:
    """A rights-safe summary for email/chat/link transport.

    When the card is restricted, it carries ONLY routing metadata and requires
    the authenticated view for any content. It never leaks canonical text,
    anchors, assertions, model votes, or the proposed answer.
    """
    summary = {
        "card_id": card["card_id"],
        "task_id": card["task_id"],
        "question": card["question"],
        "requested_decision": card["requested_decision"],
        "rights_state": card["rights_state"],
        "security_state": card["security_state"],
        "restrictive_default": card["restrictive_default"],
        "expiry": card["expiry"],
        "authenticated_view_required": True,
        # warning KINDS are safe to surface (never the content they refer to)
        "warning_kinds": sorted({w["kind"] for w in card.get("warnings", [])}),
    }
    if not card["restricted"]:
        # non-restricted cards may include the proposed answer + option labels
        summary["proposed_answer"] = card["proposed_answer"]
        summary["option_labels"] = [o["option"] for o in card.get("options", [])]
    return summary
