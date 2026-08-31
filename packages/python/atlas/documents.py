"""Canonical text pipeline (DOC-001 core).

Canonical text is UTF-8, Unicode NFC, LF newlines. Every other
transformation is fixed by CANONICALIZER_VERSION; a toolchain change
creates a NEW text artifact rather than altering anchors.
"""
import io
import unicodedata
from html.parser import HTMLParser

CANONICALIZER_VERSION = "1.0.0"
_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6",
          "section", "article", "blockquote"}


def canonicalize_text(text: str) -> bytes:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if text.startswith("﻿"):
        text = text[1:]
    text = unicodedata.normalize("NFC", text)
    lines = [ln.rstrip() for ln in text.split("\n")]
    out = "\n".join(ln for ln in lines)
    while "\n\n\n" in out:
        out = out.replace("\n\n\n", "\n\n")
    return out.strip("\n").encode("utf-8") + b"\n"


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        elif tag in _BLOCK:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)


def html_to_canonical(data: bytes) -> bytes:
    p = _TextExtractor()
    p.feed(data.decode("utf-8", errors="strict"))
    return canonicalize_text("".join(p.parts))


def pdf_to_canonical(data: bytes) -> tuple[bytes, list[dict]]:
    """Native-text PDF extraction with a page map. OCR fallback is a
    later DOC-001 atom; a page with no native text raises."""
    import fitz  # PyMuPDF, pinned in pyproject

    doc = fitz.open(stream=io.BytesIO(data).read(), filetype="pdf")
    pages, page_map, cursor = [], [], 0
    try:
        for i, page in enumerate(doc):
            text = page.get_text("text")
            if not text.strip():
                raise ValueError(f"page {i + 1} has no native text; OCR path not qualified")
            canon = canonicalize_text(text)
            pages.append(canon)
            page_map.append({"page_label": str(i + 1), "start_byte": cursor,
                             "end_byte": cursor + len(canon)})
            cursor += len(canon)
    finally:
        doc.close()
    return b"".join(pages), page_map
