#!/usr/bin/env python3
"""Generate the honest Claude-profile harness capability report
(BOOT-060/BOOT-070 under A-001.3 + D-017).

Fixtures provable in the managed environment carry pass results tied to
the executable test that proves them. Confinement fixtures that require
the operator-provisioned sandbox are NOT claimed: they are recorded as
not_applicable with an explicit substitution row, and full confinement
qualification is a precondition of the first A1 decision (D-017).
"""
import datetime
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent

PROVEN = [
    ("structured_output_canonical_validation",
     "tests/test_schema_catalogue.py: provider/manual output revalidated "
     "against canonical 2020-12; unknown keys and lossy output fail"),
    ("completion_gate_authoritative",
     "tests/test_plan_tools.py + tests/test_builder_core.py: provider "
     "success, interruption, max-turn and invalid-output cannot mark done; "
     "done requires receipt bound to exact commit"),
    ("failure_completion_paths",
     "tests/test_builder_core.py: interrupted/failed/budget terminations "
     "refuse completion"),
    ("budget_exhaustion_blocks_cleanly",
     "tests/test_builder_core.py: reservation beyond ceiling raises "
     "BudgetExhausted -> blocked_budget; verification never weakened"),
    ("transcript_cost_normalization",
     "schemas/plan/task-evidence-receipt + builder-run-manifest schemas; "
     "ledger entries validate; raw events stay outside the worktree"),
    ("deterministic_release_receipts",
     "REL-000 two-build byte-identical test, enforced per-push in CI"),
    ("role_tool_policy_deny_by_default",
     "tests/test_builder_core.py: omitted tool unavailable; unknown role "
     "denied; policy change changes compiled hash"),
    ("evidence_binds_exact_commit",
     "tests/test_plan_tools.py: wrong-commit receipt fails task-verify"),
]
DEFERRED = [
    ("filesystem_confinement_symlink_traversal_subprocess",
     "requires operator-provisioned sandbox (handoff section 2)"),
    ("network_deny_by_default_connected_peer_validation",
     "requires sandbox egress proxy; fetchguard logic is unit-proven but "
     "host enforcement is not"),
    ("credential_isolation_env_git_cloud_package",
     "requires scrubbed sandbox; managed session credentials are "
     "harness-held and unaudited by the builder"),
    ("specialist_tool_omission_enforced_by_host",
     "config/builder-roles.yaml is compiled and code-enforced; SDK-level "
     "subagent restriction qualification requires the sandbox launcher"),
]


def main():
    r = subprocess.run([str(ROOT / ".venv/bin/python"), "-m", "pytest",
                        "tests/", "-q", "--tb=no"], cwd=ROOT,
                       capture_output=True, text=True)
    suite_green = r.returncode == 0
    fixtures = [{"fixture": name, "result": "pass" if suite_green else "fail",
                 "detail": detail} for name, detail in PROVEN]
    fixtures += [{"fixture": name, "result": "not_applicable",
                  "detail": "NOT CLAIMED in managed environment: " + detail +
                  "; precondition of first A1 decision per D-017"}
                 for name, detail in DEFERRED]
    report = {
        "schema_version": "atlas-harness-capability/v1",
        "provider": "claude",
        "sdk_version": "claude-code-managed-session (exact SDK pin recorded "
                       "at sandbox qualification; D-017)",
        "qualified_at": datetime.datetime.now(datetime.timezone.utc)
        .isoformat(timespec="seconds"),
        "fixtures": fixtures,
        "substitutions": [
            {"capability": "filesystem/network/credential confinement",
             "supplied_by": "operator-provisioned sandbox (handoff section 2), "
                            "precondition of A1",
             "adr": "ADR-0001 + decision D-017"},
            {"capability": "clean-checkout CI identity isolation",
             "supplied_by": "GitHub Actions (identity unreadable by builder)",
             "adr": "ADR-0001 + decision D-017"},
        ],
    }
    import sys
    sys.path.insert(0, str(ROOT / "packages" / "python"))
    from atlas.schemas import validate
    validate("harness-capability-report.schema.json", report)
    out = ROOT / "builder" / "conformance" / "claude-capability-report.json"
    out.write_text(json.dumps(report, indent=1) + "\n")
    print(f"wrote {out} (suite_green={suite_green})")


if __name__ == "__main__":
    main()
