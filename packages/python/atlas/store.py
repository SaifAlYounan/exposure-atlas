"""Content-addressed evidence store (SRC-002 core).

Write-once by construction: objects are named by SHA-256; identical
bytes dedupe while every acquisition receipt is preserved separately.
"""
import pathlib

from .canonical import sha256_hex


class EvidenceStore:
    def __init__(self, root: pathlib.Path):
        self.root = pathlib.Path(root)
        (self.root / "blobs").mkdir(parents=True, exist_ok=True)

    def _path(self, digest: str) -> pathlib.Path:
        return self.root / "blobs" / digest[:2] / digest

    def put(self, data: bytes) -> str:
        digest = sha256_hex(data)
        p = self._path(digest)
        if p.exists():
            if p.read_bytes() != data:  # pragma: no cover - hash collision
                raise RuntimeError("content-address collision")
            return digest
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(".tmp")
        tmp.write_bytes(data)
        tmp.rename(p)
        return digest

    def get(self, digest: str) -> bytes:
        data = self._path(digest).read_bytes()
        if sha256_hex(data) != digest:
            raise RuntimeError(f"stored bytes fail integrity check: {digest}")
        return data

    def exists(self, digest: str) -> bool:
        return self._path(digest).exists()
