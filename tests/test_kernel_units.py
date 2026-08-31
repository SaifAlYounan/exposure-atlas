"""G1 unit tests: canonical bytes, store, fetch guards, anchors, audit."""
import pathlib

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent

from atlas.anchors import AnchorError, create_anchor, verify_anchor
from atlas.audit import append_event, verify_chain
from atlas.canonical import canonical_json_bytes, sha256_hex
from atlas.documents import canonicalize_text, html_to_canonical
from atlas.fetchguard import (FetchPolicyError, bounded_bytes, check_mime,
                              validate_peer_ip, validate_url)
from atlas.store import EvidenceStore

AT = "2026-08-31T12:00:00Z"


def test_canonical_bytes_deterministic_and_reject_floats():
    a = canonical_json_bytes({"b": 1, "a": [1, 2]})
    b = canonical_json_bytes({"a": [1, 2], "b": 1})
    assert a == b
    with pytest.raises(ValueError):
        canonical_json_bytes({"money": 5.0})


def test_store_content_addressed_never_overwrites(tmp_path):
    s = EvidenceStore(tmp_path)
    d1 = s.put(b"hello")
    d2 = s.put(b"hello")
    assert d1 == d2 == sha256_hex(b"hello")
    assert s.get(d1) == b"hello"


def test_fetchguard_blocks_bad_urls_and_ips():
    validate_url("https://www.ftc.gov/x", ["www.ftc.gov"])
    for bad in ["file:///etc/passwd", "ftp://www.ftc.gov/x",
                "https://evil.example/x", "https://user:pw@www.ftc.gov/x"]:
        with pytest.raises(FetchPolicyError):
            validate_url(bad, ["www.ftc.gov"])
    for ip in ["127.0.0.1", "10.1.2.3", "169.254.169.254", "192.168.1.1",
               "::1", "fe80::1"]:
        with pytest.raises(FetchPolicyError):
            validate_peer_ip(ip)
    validate_peer_ip("93.184.216.34")


def test_fetchguard_size_and_mime():
    with pytest.raises(FetchPolicyError):
        bounded_bytes(b"x" * 100, limit=10)
    check_mime("application/pdf", b"%PDF-1.7 blah")
    check_mime("text/html", b"<!doctype html><html></html>")
    with pytest.raises(FetchPolicyError):  # SEC-05: mime/signature mismatch
        check_mime("application/pdf", b"<html>polyglot?</html>")
    with pytest.raises(FetchPolicyError):  # unknown mime not permitted
        check_mime("application/zip", b"PK\x03\x04")


def test_canonical_text_rules():
    out = canonicalize_text("a\r\nb\r\rc\n\n\n\nd  \n")
    assert out == b"a\nb\n\nc\n\nd\n"
    html = b"<html><script>evil()</script><p>Hello</p><p>World</p></html>"
    assert html_to_canonical(html) == b"Hello\n\nWorld\n"


def test_anchor_exactness_and_disambiguation():
    text = b"pay $5,000,000 now. pay $5,000,000 later.\n"
    with pytest.raises(AnchorError):
        create_anchor(text, "pay $5,000,000", anchor_id="anc_aaaaaaaaaaaa",
                      text_artifact_id="txt_aaaaaaaaaaaa")
    anc = create_anchor(text, "pay $5,000,000", occurrence=2,
                        anchor_id="anc_aaaaaaaaaaaa",
                        text_artifact_id="txt_aaaaaaaaaaaa")
    assert anc["start_byte"] == 20
    with pytest.raises(AnchorError):
        create_anchor(text, "not present", anchor_id="anc_bbbbbbbbbbbb",
                      text_artifact_id="txt_aaaaaaaaaaaa")
    with pytest.raises(AnchorError):  # fabricated empty span forbidden
        create_anchor(text, "", anchor_id="anc_cccccccccccc",
                      text_artifact_id="txt_aaaaaaaaaaaa")
    art = {"text_artifact_id": "txt_aaaaaaaaaaaa",
           "canonical_sha256": sha256_hex(text)}
    assert verify_anchor(text, sha256_hex(text), art, anc) == []
    bad = dict(anc, start_byte=0, end_byte=3)
    assert verify_anchor(text, sha256_hex(text), art, bad)


def test_audit_chain_detects_tamper(tmp_path):
    p = tmp_path / "audit.jsonl"
    append_event(p, "x", "one", AT, {})
    append_event(p, "x", "two", AT, {})
    verify_chain(p)
    lines = p.read_text().splitlines()
    p.write_text("\n".join([lines[1]]) + "\n")  # delete first event
    with pytest.raises(RuntimeError):
        verify_chain(p)
