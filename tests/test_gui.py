from sincro.gui import build_database_config


def test_build_database_config_keeps_passwords_in_memory():
    values = {
        "migration_name": "example",
        "source_host": "firebird.local", "source_port": "3050",
        "source_database": "source.fdb", "source_user": "SYSDBA",
        "source_password": "source-secret", "source_table": "PROTOCOL",
        "source_jar": "jaybird.jar",
        "target_host": "postgres.local", "target_port": "5432",
        "target_database": "target", "target_user": "validator",
        "target_password": "target-secret", "target_table": "protocol",
        "target_jar": "postgresql.jar", "key": "id",
        "compare_columns": "name, status",
    }

    config = build_database_config(values)

    assert config["source"]["engine"] == "firebird"
    assert config["target"]["engine"] == "postgresql"
    assert config["checks"]["compare_columns"] == ["name", "status"]
    assert config["source"]["password"] == "source-secret"


# @hugaojanuario
