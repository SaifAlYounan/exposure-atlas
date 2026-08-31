"""Durable byte anchors into canonical text (DOC-002)."""
from .canonical import sha256_hex

PREFIX_LEN = 32


class AnchorError(ValueError):
    pass


def create_anchor(text: bytes, quote: str, *, anchor_id: str,
                  text_artifact_id: str, occurrence: int | None = None,
                  page_label: str | None = None,
                  anchor_basis: str = "native_text") -> dict:
    qb = quote.encode("utf-8")
    if not qb:
        raise AnchorError("empty quote; absence uses none_known + SearchedScope, never an empty span")
    positions = []
    start = 0
    while True:
        idx = text.find(qb, start)
        if idx == -1:
            break
        positions.append(idx)
        start = idx + 1
    if not positions:
        raise AnchorError("quote not found in canonical text")
    if len(positions) > 1 and occurrence is None:
        raise AnchorError(
            f"quote occurs {len(positions)} times; occurrence required for disambiguation")
    pos = positions[(occurrence or 1) - 1]
    end = pos + len(qb)
    return {
        "schema_version": "atlas-anchor/v1",
        "anchor_id": anchor_id,
        "text_artifact_id": text_artifact_id,
        "quote": quote,
        "quote_sha256": sha256_hex(qb),
        "start_byte": pos,
        "end_byte": end,
        "prefix": text[max(0, pos - PREFIX_LEN):pos].decode("utf-8", "replace"),
        "suffix": text[end:end + PREFIX_LEN].decode("utf-8", "replace"),
        "page_label": page_label,
        "anchor_basis": anchor_basis,
    }


def verify_anchor(text: bytes, text_sha256: str, artifact: dict, anchor: dict) -> list[str]:
    """Returns a list of failure strings; empty = anchor resolves exactly."""
    fails = []
    if anchor["text_artifact_id"] != artifact["text_artifact_id"]:
        fails.append("anchor bound to a different text artifact")
    if artifact["canonical_sha256"] != text_sha256:
        fails.append("canonical text hash does not match artifact")
    span = text[anchor["start_byte"]:anchor["end_byte"]]
    qb = anchor["quote"].encode("utf-8")
    if span != qb:
        fails.append("byte range does not decode to the stored quote")
    if sha256_hex(qb) != anchor["quote_sha256"]:
        fails.append("quote hash mismatch")
    return fails
