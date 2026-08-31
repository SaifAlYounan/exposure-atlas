"""Pure deterministic verifier (VER-001 core).

No model calls, no network, no clock: every input is supplied. Returns
pass/fail/indeterminate/not_applicable per check — never a bare boolean.
Mechanical support NEVER sets semantic review state (SPEC 4.4).
"""
from .anchors import verify_anchor
from .canonical import obj_sha256
from .schemas import AtlasSchemaError, validate

VERIFIER_VERSION = "1.0.0"

# document role -> modalities it may establish (config/source-policy/v1.yaml;
# duplicated here as code constant, cross-checked by a test so the two
# cannot drift silently)
ROLE_MODALITIES = {
    "complaint_or_pleading": {"allegation", "party_position"},
    "judgment_or_order": {"finding", "holding", "order", "procedural_event"},
    "official_docket_entry": {"procedural_event"},
    "regulator_decision": {"finding", "order", "procedural_event"},
    "official_press_release": {"announcement"},
    "settlement_instrument": {"party_position", "admission", "order"},
    "mirror_copy": set(),
    "tracker_or_news": set(),
}
PUBLISHABLE_PROVENANCE = {"issuer_direct", "official_docket",
                          "signature_verified", "digest_crossmatched",
                          "human_corroborated"}


def verify_proposal(proposal: dict, *, source_document: dict,
                    source_version: dict, text_artifact: dict,
                    canonical_text: bytes, text_sha256: str,
                    anchors_by_id: dict, report_id: str) -> dict:
    checks = []

    def add(check, result, detail=""):
        c = {"check": check, "result": result}
        if detail:
            c["detail"] = detail
        checks.append(c)

    try:
        validate("assertion-proposal.schema.json", proposal)
        add("schema_valid", "pass")
    except AtlasSchemaError as e:
        add("schema_valid", "fail", str(e))

    if proposal.get("source_version_id") != source_version["source_version_id"]:
        add("source_version_binding", "fail", "proposal bound to different source version")
    else:
        add("source_version_binding", "pass")

    support = proposal.get("support", [])
    if proposal.get("value_origin") == "source_quote":
        if not support:
            add("anchor_resolution", "fail", "source_quote requires a direct anchor")
        else:
            fails = []
            for edge in support:
                anc = anchors_by_id.get(edge["anchor_id"])
                if anc is None:
                    fails.append(f"unknown anchor {edge['anchor_id']}")
                    continue
                fails += verify_anchor(canonical_text, text_sha256, text_artifact, anc)
                if edge["role"] == "supports" and anc["quote"] != proposal["raw_value"]:
                    fails.append("source_quote raw_value must equal anchored quote bytes")
            add("anchor_resolution", "fail" if fails else "pass", "; ".join(fails))
    elif proposal.get("value_origin") in ("normalized", "derived"):
        t = proposal.get("transform")
        if not t or not t.get("parent_assertion_ids"):
            add("transform_provenance", "fail",
                "normalized/derived requires rule, version and accepted parents")
        else:
            add("transform_provenance", "pass")
        add("anchor_resolution", "not_applicable")
    else:
        add("anchor_resolution", "indeterminate",
            "source_paraphrase requires anchored accepted parents plus semantic review")

    role = source_document["document_role"]
    allowed = ROLE_MODALITIES.get(role, set())
    if proposal.get("procedural_modality") in allowed:
        add("source_role_permits_modality", "pass")
    else:
        add("source_role_permits_modality", "fail",
            f"role {role} cannot establish {proposal.get('procedural_modality')}")

    if source_version["copy_provenance_state"] in PUBLISHABLE_PROVENANCE:
        add("copy_provenance", "pass")
    else:
        add("copy_provenance", "fail",
            f"copy provenance {source_version['copy_provenance_state']} cannot "
            "support a public factual assertion")

    nv = proposal.get("normalized_value")
    if isinstance(nv, dict) and "decimal" in nv:
        add("money_decimal", "pass" if isinstance(nv["decimal"], str) else "fail")
    else:
        add("money_decimal", "not_applicable")

    # semantic support is EXPLICITLY not decided here
    add("semantic_support", "indeterminate",
        "mechanical quote presence never proves entailment; human review required")

    blocking = {"schema_valid", "source_version_binding", "anchor_resolution",
                "source_role_permits_modality", "copy_provenance",
                "money_decimal", "transform_provenance"}
    results = {c["check"]: c["result"] for c in checks}
    overall = "pass"
    if any(results.get(b) == "fail" for b in blocking):
        overall = "fail"
    report = {"schema_version": "atlas-validation-report/v1",
              "report_id": report_id,
              "target_id": proposal.get("proposal_id", "unknown"),
              "verifier_version": VERIFIER_VERSION,
              "checks": checks, "overall": overall}
    validate("validation-report.schema.json", report)
    return report


def report_sha256(report: dict) -> str:
    return obj_sha256(report)
