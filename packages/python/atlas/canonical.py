"""Canonical byte-deterministic serialization and hashing (DOM-001)."""
import hashlib
import json


def canonical_json_bytes(obj) -> bytes:
    """Byte-deterministic canonical JSON: sorted keys, minimal separators,
    UTF-8, no trailing newline. Floats are rejected — money and other
    decimals must be strings (SPEC 4.3)."""
    _reject_floats(obj)
    return json.dumps(obj, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def _reject_floats(obj):
    if isinstance(obj, float):
        raise ValueError("float values are forbidden in canonical objects")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _reject_floats(k)
            _reject_floats(v)
    elif isinstance(obj, (list, tuple)):
        for v in obj:
            _reject_floats(v)


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def obj_sha256(obj) -> str:
    return sha256_hex(canonical_json_bytes(obj))
