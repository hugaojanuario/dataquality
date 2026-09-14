import pytest

from sincro.config import validate_config


def test_validate_config_rejects_plain_list():
    with pytest.raises(ValueError, match="raiz"):
        validate_config([])


def test_validate_config_accepts_package_mode():
    config = {"mode": "package", "package": {"files": [{"path": "file.csv"}]}}
    assert validate_config(config) is config


def test_validate_config_accepts_named_datasets():
    config = {
        "datasets": {
            "protocols": {"path": "protocols.csv"},
            "parts": {"path": "parts.csv"},
        },
        "checks": {"rules": []},
    }
    assert validate_config(config) is config


def test_validate_config_requires_single_jdbc_relation():
    config = {
        "source": {
            "type": "jdbc", "engine": "firebird", "database": "source",
            "user": "user", "jar": "driver.jar", "table": "A", "query": "select 1",
        },
        "target": {"path": "target.csv"},
        "key": "id", "checks": {},
    }
    with pytest.raises(ValueError, match="exatamente"):
        validate_config(config)


# @hugaojanuario
