"""Source adapter SDK, registry and conformance kit (SRC-001).

Adapters have NO capability to write accepted domain state by
construction: they return candidates/bytes/observations only. Live
network mode is not implemented under A0; fixture mode is deterministic
for CI.
"""
import pathlib

import yaml

from .fetchguard import validate_url
from .schemas import validate

PAGE_SIZE = 2


class AdapterError(ValueError):
    pass


def load_registry(config_dir: pathlib.Path) -> dict[str, dict]:
    registry = {}
    for f in sorted(pathlib.Path(config_dir).glob("*.yaml")):
        doc = yaml.safe_load(f.read_text())
        if not isinstance(doc, dict) or "source_id" not in doc:
            continue  # tracker files etc. are validated by COV-001
        validate("source-registry-entry.schema.json", doc)
        registry[doc["source_id"]] = doc
    return registry


class FixtureAdapter:
    """Deterministic adapter over a local manifest: the reference
    implementation for the adapter contract and its conformance kit."""

    def __init__(self, source_entry: dict, leads: list[dict]):
        self.entry = source_entry
        self._leads = sorted(leads, key=lambda x: x["lead_id"])

    def discover(self, cursor: int | None = None):
        start = cursor or 0
        page = self._leads[start:start + PAGE_SIZE]
        next_cursor = start + len(page) if start + len(page) < len(self._leads) else None
        for lead in page:
            validate_url(lead["url"], self.entry["host_allowlist"])
        return page, next_cursor

    def fetch(self, lead: dict) -> bytes:
        validate_url(lead["url"], self.entry["host_allowlist"])
        return pathlib.Path(lead["fixture_path"]).read_bytes()

    def check_updates(self, lead: dict) -> dict:
        return {"lead_id": lead["lead_id"], "observed": "unchanged"}

    def healthcheck(self) -> dict:
        return {"source_id": self.entry["source_id"], "state": "ok",
                "expected_volume": len(self._leads)}


def run_conformance(adapter) -> list[str]:
    """Returns failures; empty = conformant."""
    failures = []
    seen, cursor = [], None
    for _ in range(100):
        page, cursor = adapter.discover(cursor)
        seen.extend(lead["lead_id"] for lead in page)
        if cursor is None:
            break
    else:
        failures.append("pagination did not terminate")
    if len(seen) != len(set(seen)):
        failures.append("duplicate leads within one discovery window")
    seen2, cursor = [], None
    while True:
        page, cursor = adapter.discover(cursor)
        seen2.extend(lead["lead_id"] for lead in page)
        if cursor is None:
            break
    if seen != seen2:
        failures.append("re-running an identical window is not idempotent")
    for attr in ("write_assertion", "approve", "publish", "write_accepted"):
        if hasattr(adapter, attr):
            failures.append(f"adapter exposes forbidden capability {attr}")
    try:
        adapter.fetch({"lead_id": "evil", "url": "https://evil.example/x",
                       "fixture_path": "/dev/null"})
        failures.append("unregistered host was not refused")
    except Exception:
        pass
    return failures
