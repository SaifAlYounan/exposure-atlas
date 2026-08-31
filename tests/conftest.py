"""Ephemeral PostgreSQL cluster for DOM-002/003 tests.

Runs initdb/pg_ctl in a temp dir on a unix socket. When running as root
(this managed container), pg commands run as the `postgres` system user.
In CI the runner user is unprivileged and runs them directly.
"""
import os
import pathlib
import shlex
import shutil
import subprocess
import tempfile

import pytest

PG_BIN = pathlib.Path("/usr/lib/postgresql/16/bin")


def _pg_available():
    return (PG_BIN / "initdb").exists() or shutil.which("initdb")


def _bin(name):
    p = PG_BIN / name
    return str(p) if p.exists() else name


def _run(cmd, **kw):
    if os.geteuid() == 0:
        cmd = ["su", "-s", "/bin/bash", "postgres", "-c",
               " ".join(shlex.quote(c) for c in cmd)]
    subprocess.run(cmd, check=True, capture_output=True, **kw)


@pytest.fixture(scope="session")
def pg_engine():
    if not _pg_available():
        pytest.fail("PostgreSQL binaries missing: DOM-002/003 tests require them")
    import sqlalchemy as sa
    tmp = tempfile.mkdtemp(prefix="atlas-pg-")
    data = os.path.join(tmp, "data")
    sock = os.path.join(tmp, "sock")
    os.makedirs(sock)
    if os.geteuid() == 0:
        subprocess.run(["chown", "-R", "postgres:postgres", tmp], check=True)
    _run([_bin("initdb"), "-D", data, "-A", "trust", "-U", "atlas"])
    conf = os.path.join(data, "postgresql.conf")
    extra = (f"\nunix_socket_directories = '{sock}'\n"
             "listen_addresses = ''\n")
    if os.geteuid() == 0:
        subprocess.run(["su", "-s", "/bin/bash", "postgres", "-c",
                        f"cat >> {shlex.quote(conf)}"], input=extra.encode(),
                       check=True)
    else:
        with open(conf, "a") as f:
            f.write(extra)
    _run([_bin("pg_ctl"), "-D", data, "-l", os.path.join(tmp, "log"), "start"])
    try:
        _run([_bin("createdb"), "-h", sock, "-U", "atlas", "atlas_test"])
        engine = sa.create_engine(
            f"postgresql+psycopg://atlas@/atlas_test?host={sock}")
        from atlas.db import create_all
        create_all(engine)
        yield engine
        engine.dispose()
    finally:
        _run([_bin("pg_ctl"), "-D", data, "-m", "immediate", "stop"])
        shutil.rmtree(tmp, ignore_errors=True)
