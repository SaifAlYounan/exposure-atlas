"""Rights-gated external archive interface (SRC-003).

External archive submission is DISABLED BY DEFAULT and every attempt —
including refusals — records policy version, decision and result. The
Atlas evidence vault (store.py) is the mandatory preservation path; this
gate only governs the OPTIONAL external submission. No network adapter
exists under A0.
"""
ARCHIVE_POLICY_VERSION = "1.0.0"
_BLOCKING_OUTCOMES = {"pending", "internal_only", "prohibited", "withdrawn",
                      "cleared_metadata_only", "cleared_licensee"}


def evaluate_archive_request(*, source_version: dict,
                             archive_axis_outcome: str | None,
                             globally_enabled: bool, at: str) -> dict:
    """Pure gate. Returns an append-only attempt record; the caller may
    submit externally ONLY when decision == 'allow' (impossible while
    globally_enabled is False, the D-005 default)."""
    record = {"policy_version": ARCHIVE_POLICY_VERSION,
              "source_version_id": source_version["source_version_id"],
              "evaluated_at": at, "axis_outcome": archive_axis_outcome,
              "result": None, "decision": None}
    if not globally_enabled:
        record.update(decision="deny",
                      result="refused: external archive submission disabled "
                             "by default (D-005)")
    elif archive_axis_outcome is None:
        record.update(decision="deny",
                      result="refused: archive-submission rights axis missing; "
                             "fails closed")
    elif archive_axis_outcome in _BLOCKING_OUTCOMES:
        record.update(decision="deny",
                      result=f"refused: rights axis {archive_axis_outcome}")
    elif archive_axis_outcome == "cleared_public":
        record.update(decision="allow", result="eligible for submission")
    else:
        record.update(decision="deny",
                      result=f"refused: unknown axis outcome "
                             f"{archive_axis_outcome!r} fails closed")
    return record
