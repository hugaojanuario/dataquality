from pathlib import Path

import pytest

from sincro.datasource import (
    build_jdbc_url,
    collect_jars,
    resolve_password,
)


def test_build_firebird_url_uses_default_port():
    url = build_jdbc_url(
        {
            "engine": "firebird",
            "host": "database.local",
            "database": "C:/data/source.fdb",
        }
    )

    assert url == "jdbc:firebirdsql://database.local:3050/C:/data/source.fdb"


def test_build_postgresql_url():
    url = build_jdbc_url(
        {
            "engine": "postgresql",
            "host": "database.local",
            "port": 5433,
            "database": "target",
        }
    )

    assert url == "jdbc:postgresql://database.local:5433/target"


def test_resolve_password_reads_environment(monkeypatch):
    monkeypatch.setenv("SINCRO_TEST_PASSWORD", "secret")

    assert (
        resolve_password({"password_env": "SINCRO_TEST_PASSWORD"})
        == "secret"
    )


def test_collect_jars_validates_driver_file(tmp_path):
    jar = tmp_path / "driver.jar"
    jar.write_bytes(b"driver")

    result = collect_jars(
        {"type": "csv", "path": "source.csv"},
        {"type": "jdbc", "jar": str(jar)},
    )

    assert result == [str(Path(jar).resolve())]


def test_collect_jars_rejects_missing_driver(tmp_path):
    with pytest.raises(FileNotFoundError):
        collect_jars({"type": "jdbc", "jar": str(tmp_path / "missing.jar")})


# @hugaojanuario
