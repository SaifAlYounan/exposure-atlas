"""PLT-002/PLT-003 tests."""
import pytest
import sqlalchemy as sa

from atlas.config import (REDACTED, AtlasConfig, MissingSecret, redact,
                          require_secret)
from atlas.health import stack_health


def test_missing_secret_has_no_default(monkeypatch):
    monkeypatch.delenv("ATLAS_TEST_SECRET", raising=False)
    with pytest.raises(MissingSecret):
        require_secret("ATLAS_TEST_SECRET")
    monkeypatch.setenv("ATLAS_TEST_SECRET", "s3cr3t-value")
    assert require_secret("ATLAS_TEST_SECRET") == "s3cr3t-value"


def test_nonlocal_env_requires_injected_db(monkeypatch):
    monkeypatch.setenv("ATLAS_ENV", "internal_a3")
    monkeypatch.delenv("ATLAS_DATABASE_URL", raising=False)
    with pytest.raises(MissingSecret):
        AtlasConfig.from_env()
    monkeypatch.setenv("ATLAS_ENV", "local")
    assert AtlasConfig.from_env().environment == "local"


def test_redaction():
    line = ("fetch password=hunter2 token=abc from "
            "https://x.example/f.pdf?X-Amz-Signature=deadbeef done")
    out = redact(line, known_secrets=("hunter2",))
    assert "hunter2" not in out and "deadbeef" not in out
    assert REDACTED in out


def test_stack_health_names_missing_dependency(pg_engine, tmp_path):
    h = stack_health(pg_engine, tmp_path / "store")
    assert h["healthy"] and all(c["state"] == "ok" for c in h["checks"])
    dead = sa.create_engine(
        "postgresql+psycopg://nobody@/nope?host=/nonexistent-sock")
    h = stack_health(dead, tmp_path / "store")
    assert not h["healthy"]
    bad = [c for c in h["checks"] if c["state"] != "ok"]
    assert bad and bad[0]["dependency"] == "postgresql"
