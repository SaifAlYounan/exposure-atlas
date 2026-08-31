"""SRC-004-80 — A1 live-probe entrypoint (D-021 scope), behind the D-027
activation gate.

This module contains the probe logic, but run_live_probe REFUSES to
execute unless an explicit activation token is present that ONLY the
operator-approved protected `live-fetch` environment supplies. Under A0
and un-activated A1 the entrypoint is inert; it is exercised only via
the deterministic dry-run path (an injected adapter, no network).

Caps enforced (D-021): <=50 documents/source; host allowlist +
connected-peer-IP validation; recorded acquisition receipts; NO runtime
model calls (that is A2).
"""
import os

from .fetchguard import MAX_REDIRECTS, validate_peer_ip, validate_url

MAX_DOCS_PER_SOURCE = 50
ACTIVATION_ENV = "ATLAS_LIVE_FETCH_ACTIVATION"


class ProbeNotActivated(PermissionError):
    pass


class ProbeCapExceeded(RuntimeError):
    pass


def _require_activation() -> str:
    """The activation token is injected only by the protected live-fetch
    environment after the operator's per-run review (D-027). Its absence
    keeps the probe inert everywhere else."""
    token = os.environ.get(ACTIVATION_ENV)
    if not token:
        raise ProbeNotActivated(
            "live probe not activated: the protected live-fetch environment "
            "must inject the operator activation token (D-027). Refusing to "
            "fetch.")
    return token


def plan_probe(adapter, *, max_docs: int = MAX_DOCS_PER_SOURCE) -> list[dict]:
    """Deterministic, network-free: enumerate the leads a probe WOULD
    fetch, enforcing the document cap and the host allowlist. Safe under
    A0; used for dry-run tests and for the receipt the operator reviews
    before activating."""
    leads, cursor = [], None
    while True:
        page, cursor = adapter.discover(cursor)
        leads.extend(page)
        if cursor is None or len(leads) > max_docs:
            break
    if len(leads) > max_docs:
        raise ProbeCapExceeded(
            f"{adapter.source_id}: {len(leads)} leads exceeds cap {max_docs}")
    for lead in leads:
        validate_url(lead["url"], adapter.host_allowlist)
    return leads[:max_docs]


def run_live_probe(adapter, *, fetcher, peer_ip_resolver,
                   max_docs: int = MAX_DOCS_PER_SOURCE) -> list[dict]:
    """LIVE path. `fetcher` and `peer_ip_resolver` are injected by the
    activated workflow (real HTTP under harden-runner egress block).
    Refuses without the activation token. Returns acquisition receipts;
    never writes accepted domain state; never calls a model."""
    _require_activation()
    plan = plan_probe(adapter, max_docs=max_docs)
    receipts = []
    for lead in plan:
        peer_ip = peer_ip_resolver(lead["url"])
        validate_peer_ip(peer_ip)   # DNS-rebinding defence at the socket
        data, meta = fetcher(lead["url"], max_redirects=MAX_REDIRECTS)
        receipts.append({"lead_id": lead["lead_id"], "url": lead["url"],
                         "bytes": len(data), "http_meta": meta,
                         "peer_ip": peer_ip})
    return receipts
