"""Local stack health checks (PLT-002 core): a stopped dependency is
identified BY NAME, never as a generic failure."""
import pathlib


def check_postgres(engine) -> dict:
    try:
        import sqlalchemy as sa
        with engine.connect() as c:
            c.execute(sa.text("SELECT 1"))
        return {"dependency": "postgresql", "state": "ok"}
    except Exception as e:
        return {"dependency": "postgresql", "state": "unavailable",
                "detail": str(e).splitlines()[0][:200]}


def check_evidence_store(root) -> dict:
    root = pathlib.Path(root)
    try:
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".health-probe"
        probe.write_bytes(b"ok")
        assert probe.read_bytes() == b"ok"
        probe.unlink()
        return {"dependency": "evidence_store", "state": "ok"}
    except Exception as e:
        return {"dependency": "evidence_store", "state": "unavailable",
                "detail": str(e)[:200]}


def stack_health(engine, store_root) -> dict:
    checks = [check_postgres(engine), check_evidence_store(store_root)]
    return {"healthy": all(c["state"] == "ok" for c in checks),
            "checks": checks}
