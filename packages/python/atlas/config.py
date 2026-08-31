"""Typed configuration and secret handling (PLT-003 core).

Rules: no production secret has a development default; a missing
required secret raises instead of defaulting; log rendering redacts
secret values, signed URLs and source text.
"""
import os
import re
from dataclasses import dataclass, field

_REDACT_PATTERNS = [
    re.compile(r"(?i)(password|secret|token|api_key|authorization)=\S+"),
    re.compile(r"https?://[^\s]*[?&](X-Amz-Signature|sig|token)=[^\s&]+"),
]
REDACTED = "[REDACTED]"


class MissingSecret(RuntimeError):
    pass


def require_secret(name: str) -> str:
    """Secrets come only from the environment (injected by the host);
    there is deliberately no default parameter."""
    val = os.environ.get(name)
    if not val:
        raise MissingSecret(
            f"required secret {name} is not set; no development default exists")
    return val


def redact(text: str, known_secrets: tuple[str, ...] = ()) -> str:
    for s in known_secrets:
        if s:
            text = text.replace(s, REDACTED)
    for pat in _REDACT_PATTERNS:
        text = pat.sub(REDACTED, text)
    return text


@dataclass(frozen=True)
class AtlasConfig:
    environment: str = "local"
    database_url: str | None = None       # injected; never a prod default
    evidence_store_path: str = "var/evidence"
    supported_languages: tuple[str, ...] = ("en",)
    allowed_hosts: tuple[str, ...] = field(default_factory=tuple)

    @classmethod
    def from_env(cls) -> "AtlasConfig":
        env = os.environ.get("ATLAS_ENV", "local")
        if env not in ("local", "internal_a3", "beta_a4"):
            raise ValueError(f"unknown environment {env!r}")
        db = os.environ.get("ATLAS_DATABASE_URL")
        if env != "local" and not db:
            raise MissingSecret("non-local environments require "
                                "ATLAS_DATABASE_URL injection")
        return cls(environment=env, database_url=db)
