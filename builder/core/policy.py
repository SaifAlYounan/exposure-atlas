"""Compiled role/tool capability policy (HAR-002, solo scale).

Declarative source: config/builder-roles.yaml. Deny-by-default: a tool
not granted to a role is unavailable, not discouraged. The compiled
policy carries a content hash; any change is a new version and a
requalification event (BOOT-060/070).
"""
import pathlib

import yaml

from atlas.canonical import obj_sha256

ROOT = pathlib.Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "config" / "builder-roles.yaml"


class PolicyDenied(PermissionError):
    pass


def compile_policy(path: pathlib.Path = POLICY_PATH) -> dict:
    doc = yaml.safe_load(path.read_text())
    roles = doc["roles"]
    for role, spec in roles.items():
        if not isinstance(spec.get("tools"), list):
            raise ValueError(f"role {role}: tools list required")
    return {"version": doc["policy_version"], "roles": roles,
            "hash": obj_sha256({"version": doc["policy_version"],
                                "roles": roles})}


def check_tool(policy: dict, role: str, tool: str) -> None:
    spec = policy["roles"].get(role)
    if spec is None:
        raise PolicyDenied(f"unknown role {role!r}: deny by default")
    if tool in spec.get("disallowed_tools", []):
        raise PolicyDenied(f"role {role!r}: tool {tool!r} explicitly disallowed")
    if tool not in spec["tools"]:
        raise PolicyDenied(f"role {role!r}: tool {tool!r} not granted "
                           "(deny by default)")
