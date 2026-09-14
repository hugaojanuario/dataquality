import os
from pathlib import Path
from typing import Any

from pyspark.sql import DataFrame, SparkSession
from sincro.audit.engines import ENGINES, jdbc_url


DEFAULT_DRIVERS = {name: engine.driver for name, engine in ENGINES.items()}

DEFAULT_PORTS = {name: engine.port for name, engine in ENGINES.items()}


def build_jdbc_url(config: dict[str, Any]) -> str:
    """Monta a URL JDBC sem incluir usuário ou senha."""
    return jdbc_url(config)


def resolve_password(config: dict[str, Any]) -> str:
    """Obtém senha em memória, preferindo uma variável de ambiente."""
    password_env = config.get("password_env")
    if password_env:
        password = os.getenv(str(password_env))
        if password is None:
            raise ValueError(
                f"Variável de ambiente não definida: {password_env}"
            )
        return password

    if "password" in config:
        return str(config["password"])
    raise ValueError("Informe password_env para a conexão JDBC.")


def collect_jars(*configs: dict[str, Any]) -> list[str]:
    """Coleta os drivers JDBC usados pelas fontes configuradas."""
    jars: list[str] = []
    for config in configs:
        if config.get("type", "csv") != "jdbc":
            continue
        jar = config.get("jar")
        if not jar:
            raise ValueError("Uma fonte JDBC precisa informar o caminho 'jar'.")
        resolved = str(Path(jar).expanduser().resolve())
        if not Path(resolved).is_file():
            raise FileNotFoundError(f"Driver JDBC não encontrado: {resolved}")
        if resolved not in jars:
            jars.append(resolved)
    return jars


def read_dataset(
    spark: SparkSession,
    config: dict[str, Any],
) -> DataFrame:
    """Lê CSV ou consulta JDBC usando uma configuração comum."""
    source_type = config.get("type", "csv")
    if source_type == "csv":
        return (
            spark.read
            .option("header", config.get("header", True))
            .option("delimiter", config.get("delimiter", ","))
            .option("encoding", config.get("encoding", "UTF-8"))
            .option("inferSchema", config.get("infer_schema", True))
            .csv(config["path"])
        )

    if source_type != "jdbc":
        raise ValueError(f"Tipo de fonte não suportado: {source_type}")

    engine = str(config["engine"]).lower()
    table = config.get("table")
    query = config.get("query")
    if bool(table) == bool(query):
        raise ValueError("Informe exatamente um dos campos: table ou query.")
    dbtable = table or f"({query}) sincro_query"

    return (
        spark.read.format("jdbc")
        .option("url", build_jdbc_url(config))
        .option("dbtable", dbtable)
        .option("driver", config.get("driver", DEFAULT_DRIVERS[engine]))
        .option("user", config["user"])
        .option("password", resolve_password(config))
        .load()
    )


# @hugaojanuario
