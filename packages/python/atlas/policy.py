"""Central publication-policy evaluator (POL-001 core).

Pure function; allow|deny|human_review with machine-readable reasons.
Missing or unknown information never silently becomes allow.
"""
from .schemas import validate

POLICY_VERSION = "1.0.0"
_CLEARED = {"cleared_public", "cleared_metadata_only", "cleared_licensee"}


def evaluate(*, validation_report: dict | None,
             semantic_review_state: str | None,
             effective_distribution_decision: str | None,
             suppression_denied: bool,
             operation: str, evaluated_at: str,
             boundary_version: str | None = None) -> dict:
    reasons: list[str] = []
    decision = "allow"

    def deny(reason):
        nonlocal decision
        decision = "deny"
        reasons.append(reason)

    def review(reason):
        nonlocal decision
        if decision != "deny":
            decision = "human_review"
        reasons.append(reason)

    if suppression_denied:
        deny("suppression_overlay_denies")
    if validation_report is None:
        deny("mechanical_verification_missing")
    elif validation_report.get("overall") == "fail":
        deny("mechanical_verification_failed")
    elif validation_report.get("overall") != "pass":
        review("mechanical_verification_indeterminate")

    if operation == "publish_public":
        if semantic_review_state is None:
            deny("semantic_review_state_missing")
        elif semantic_review_state != "human_approved":
            review("semantic_review_not_human_approved")
        if effective_distribution_decision is None:
            deny("rights_state_missing_fails_closed")
        elif effective_distribution_decision not in _CLEARED:
            deny(f"rights_not_cleared:{effective_distribution_decision}")
        if boundary_version is None:
            deny("boundary_version_missing")
    result = {"schema_version": "atlas-policy-decision/v1",
              "decision": decision,
              "reasons": reasons or ["all_checks_satisfied"],
              "policy_versions": {"publication_policy": POLICY_VERSION},
              "expiry": None,
              "evaluated_at": evaluated_at}
    validate("publication-policy-decision.schema.json", result)
    return result
