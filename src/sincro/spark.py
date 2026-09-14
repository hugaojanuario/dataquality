import os
import sys
from pathlib import Path

import pyspark
from pyspark.sql import SparkSession


def create_spark_session(jars: list[str] | None = None) -> SparkSession:
    """Cria uma sessão local e carrega drivers JDBC quando necessário."""
    os.environ.setdefault("SPARK_HOME", str(Path(pyspark.__file__).parent))
    os.environ.setdefault("PYSPARK_PYTHON", sys.executable)
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", sys.executable)

    builder = (
        SparkSession.builder
        .master("local[*]")
        .appName("sincro")
    )
    if jars:
        builder = builder.config("spark.jars", ",".join(jars))

    return builder.getOrCreate()


# @hugaojanuario
