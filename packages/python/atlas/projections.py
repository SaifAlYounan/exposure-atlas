"""Public projection builders beyond the summary (DOM-006).

Allowlist-only. Facts and classification never flatten into one object.
"""
from .schemas import validate


def build_record_detail(*, release_id: str, record: dict,
                        approved_assertions: list[dict],
                        classification: dict | None,
                        boundary_version: str) -> dict:
    facts = []
    for a in approved_assertions:
        if a["semantic_review_state"] != "human_approved":
            raise ValueError("unapproved assertion reached projection")
        facts.append({"predicate": a["predicate"], "raw_value": a["raw_value"],
                      "normalized_value": a.get("normalized_value"),
                      "procedural_modality": a["procedural_modality"],
                      "value_origin": a["value_origin"]})
    cls = {"taxonomy_version": None, "assignments": [],
           "opinion_notice": "Classifications are Atlas analysis, not source facts."}
    if classification is not None:
        cls["taxonomy_version"] = classification["taxonomy_version"]
        cls["assignments"] = [
            {"labels": a["labels"], "review_state": a["review_state"]}
            for a in classification["assignments"]
            if a["review_state"] in ("human_approved", "abstained")]
    out = {"schema_version": "atlas-record-detail/v1",
           "projection_version": "V1", "release_id": release_id,
           "record_id": record["record_id"],
           "record_revision_id": record["record_revision_id"],
           "boundary_version": boundary_version,
           "facts": {"assertions": facts}, "classification": cls,
           "notices": {"no_match_is_not_absence": True,
                       "not_legal_advice": True}}
    validate("record-detail-v1.schema.json", out)
    return out


def build_citation_bundle(*, release_id: str, record_revision_id: str,
                          source_document: dict, source_version: dict,
                          anchor: dict | None, official_url: str | None,
                          verification_date: str,
                          warnings: list[str]) -> dict:
    provenance = source_version["copy_provenance_state"]
    custodian_status = {"issuer_direct": "issuer_direct",
                        "official_docket": "official_docket"}.get(
        provenance, "mirror_corroborated")
    out = {"schema_version": "atlas-citation-bundle/v1",
           "projection_version": "V1",
           "issuing_body": source_document["issuer"],
           "source_title": source_document["title"],
           "docket": source_document.get("docket"),
           "filing_or_decision_date": None,
           "pinpoint": (f"page {anchor['page_label']}" if anchor and
                        anchor.get("page_label") else None),
           "official_url": official_url,
           "custodian_status": custodian_status,
           "source_version_sha256": source_version["content_sha256"],
           "language": "en",
           "atlas_release_id": release_id,
           "atlas_record_revision_id": record_revision_id,
           "verification_date": verification_date,
           "warnings": warnings}
    validate("citation-bundle-v1.schema.json", out)
    return out


def citation_check(*, release_id: str, normalized_key: str,
                   matches: dict[str, str],
                   boundary_decisions: dict[str, dict],
                   pending_keys: set[str] = frozenset(),
                   audience_may_see_candidates: bool = False) -> dict:
    """matches: normalized_key -> record_id; boundary_decisions:
    normalized_key -> stored BoundaryDecision. Absence NEVER produces
    confirmed_out_of_scope; a confidential lead never leaks."""
    out = {"schema_version": "atlas-citation-check/v1",
           "projection_version": "V1", "release_id": release_id,
           "record_id": None, "no_match_is_not_absence": True}
    if normalized_key in matches:
        out.update(status="matched", record_id=matches[normalized_key])
    elif normalized_key in boundary_decisions:
        d = boundary_decisions[normalized_key]
        if d["outcome"] != "exclude":
            raise ValueError("confirmed_out_of_scope requires an exclude decision")
        out.update(status="confirmed_out_of_scope",
                   boundary_decision_id=d["decision_id"],
                   boundary_version=d["boundary_version"],
                   decision_as_of=d["decided_at"],
                   normalized_citation_key=normalized_key)
    elif normalized_key in pending_keys and audience_may_see_candidates:
        out.update(status="candidate_pending")
    else:
        out.update(status="not_found_in_atlas")
    validate("citation-check-result-v1.schema.json", out)
    return out
