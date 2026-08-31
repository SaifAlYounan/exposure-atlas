"""Append-only hash-chained audit ledger (DOM-003 primitive)."""
import json
import pathlib

from .canonical import canonical_json_bytes, sha256_hex
from .schemas import validate


def append_event(path: pathlib.Path, actor: str, action: str, at: str,
                 detail: dict) -> dict:
    path.parent.mkdir(parents=True, exist_ok=True)
    prev_hash, seq = "genesis", 0
    if path.exists():
        lines = path.read_text().splitlines()
        if lines:
            last = json.loads(lines[-1])
            seq = last["seq"] + 1
            prev_hash = sha256_hex(canonical_json_bytes(last))
    event = {"schema_version": "atlas-audit-event/v1", "seq": seq,
             "prev_hash": prev_hash, "actor": actor, "action": action,
             "at": at, "detail": detail}
    validate("audit-event.schema.json", event)
    with open(path, "a") as f:
        f.write(json.dumps(event, sort_keys=True) + "\n")
    return event


def verify_chain(path: pathlib.Path) -> None:
    prev_hash, prev = "genesis", None
    for i, line in enumerate(path.read_text().splitlines()):
        ev = json.loads(line)
        validate("audit-event.schema.json", ev)
        if ev["seq"] != i:
            raise RuntimeError(f"audit chain: sequence break at {i}")
        if ev["prev_hash"] != prev_hash:
            raise RuntimeError(f"audit chain: hash break at seq {i}")
        prev = ev
        prev_hash = sha256_hex(canonical_json_bytes(prev))
