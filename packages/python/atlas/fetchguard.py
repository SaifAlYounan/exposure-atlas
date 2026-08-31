"""Hostile-URL and hostile-byte guards (SRC-002 / SEC-001 core).

Pure, network-free logic so every rule is unit-testable. Live fetching
is not implemented under A0; the fixture adapter reads local files
through the same guards.
"""
import ipaddress
from urllib.parse import urlsplit

MAX_FETCH_BYTES = 50 * 1024 * 1024
MAX_REDIRECTS = 5

_BLOCKED_NETS = [ipaddress.ip_network(n) for n in (
    "0.0.0.0/8", "10.0.0.0/8", "100.64.0.0/10", "127.0.0.0/8",
    "169.254.0.0/16", "172.16.0.0/12", "192.168.0.0/16", "198.18.0.0/15",
    "::1/128", "fc00::/7", "fe80::/10",
)]


class FetchPolicyError(ValueError):
    pass


def validate_url(url: str, allowed_hosts: list[str]) -> None:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        raise FetchPolicyError(f"scheme not permitted: {parts.scheme!r}")
    if parts.username or parts.password:
        raise FetchPolicyError("credentials in URL are not permitted")
    host = (parts.hostname or "").lower()
    if host not in [h.lower() for h in allowed_hosts]:
        raise FetchPolicyError(f"host not in source allowlist: {host!r}")


def validate_peer_ip(ip: str) -> None:
    """Must be called for the ACTUALLY CONNECTED peer at every redirect
    hop and after re-resolution (DNS rebinding defence)."""
    addr = ipaddress.ip_address(ip)
    for net in _BLOCKED_NETS:
        if addr in net:
            raise FetchPolicyError(f"destination address blocked: {ip}")


def bounded_bytes(data: bytes, limit: int = MAX_FETCH_BYTES) -> bytes:
    if len(data) > limit:
        raise FetchPolicyError(f"payload exceeds byte limit ({len(data)} > {limit})")
    return data


def sniff_kind(data: bytes) -> str:
    head = data[:1024].lstrip()
    if head.startswith(b"%PDF-"):
        return "pdf"
    low = head[:256].lower()
    if low.startswith((b"<!doctype html", b"<html")) or b"<html" in low:
        return "html"
    return "unknown"


def check_mime(declared_mime: str, data: bytes) -> None:
    """MIME/signature mismatch quarantines (SEC-05)."""
    kind = sniff_kind(data)
    expect = {"application/pdf": "pdf", "text/html": "html"}.get(declared_mime)
    if expect is None:
        raise FetchPolicyError(f"mime type not permitted: {declared_mime}")
    if kind != expect:
        raise FetchPolicyError(
            f"file signature ({kind}) does not match declared mime "
            f"({declared_mime}); quarantined")
