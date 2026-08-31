"""HAR-001/HAR-003 confinement qualification — the portion provable
without live network or the wired SDK (ADR-0002).

What this proves now (host-substitution + in-code layers):
  - private/metadata/link-local egress blocked in-code (fetchguard);
  - the SDK-denial fixture set is enforced by the compiled host policy
    (every declared denial is actually denied);
  - source allowlist rejects unregistered hosts.
What it does NOT claim (recorded, not diluted):
  - OS-level egress enforcement (proven by harden-runner block mode in
    the A1 live-fetch workflow, gated by the operator environment);
  - SDK-internal subagent tool denial (proven once HAR-003 is wired);
  - 'agent cannot modify host policy' (operator branch-protection +
    CODEOWNERS + protected environment; R1, operator-only config).
"""
import pathlib

import pytest
import yaml

from atlas.fetchguard import FetchPolicyError, validate_peer_ip, validate_url
from builder.core.policy import PolicyDenied, check_tool, compile_policy

ROOT = pathlib.Path(__file__).resolve().parent.parent


def test_metadata_and_private_egress_blocked_in_code():
    for ip in ["169.254.169.254", "127.0.0.1", "10.0.0.5", "100.64.0.1",
               "192.168.1.1", "172.16.0.1", "::1", "fe80::1", "fc00::1"]:
        with pytest.raises(FetchPolicyError):
            validate_peer_ip(ip)
    validate_peer_ip("93.184.216.34")  # a public address passes


def test_sdk_denial_fixture_set_is_enforced_by_host_policy():
    fixtures = yaml.safe_load(
        (ROOT / "builder" / "conformance" / "sdk_denial_fixtures"
         / "fixtures.yaml").read_text())["fixtures"]
    policy = compile_policy()
    assert fixtures, "denial fixture set must be non-empty"
    for fx in fixtures:
        with pytest.raises(PolicyDenied):
            check_tool(policy, fx["role"], fx["denied_tool"])


def test_source_allowlist_rejects_unregistered_hosts():
    registry_hosts = []
    for f in (ROOT / "config" / "sources").glob("*.yaml"):
        doc = yaml.safe_load(f.read_text())
        if isinstance(doc, dict):
            registry_hosts += doc.get("host_allowlist", [])
    assert "www.ftc.gov" in registry_hosts
    validate_url("https://www.ftc.gov/x", registry_hosts)
    for bad in ["https://evil.example/x", "https://169.254.169.254/x",
                "http://localhost/x"]:
        with pytest.raises(FetchPolicyError):
            validate_url(bad, registry_hosts)


def test_confinement_residuals_are_declared_in_adr():
    adr = (ROOT / "docs" / "adr" / "0002-github-hosted-confinement.md").read_text()
    # the honest residuals must remain documented; this guards against a
    # future edit silently dropping them
    for marker in ["R1 — the agent authored its own confinement",
                   "R2 — SDK-internal tool restriction",
                   "R3 — DNS rebinding",
                   "branch protection", "CODEOWNERS", "protected"]:
        assert marker in adr, f"ADR-0002 lost residual marker: {marker!r}"
