from pyspark.sql import DataFrame, SparkSession
from pyspark.sql.types import IntegerType, StringType, StructField, StructType

RECORD_SCHEMA = StructType([
    StructField("id", IntegerType(), nullable=False),
    StructField("name", StringType(), nullable=False),
    StructField("status", StringType(), nullable=False),
])

def read_records(spark: SparkSession, path: str) -> DataFrame:
    return (
        spark.read
        .option("header", True)
        .schema(RECORD_SCHEMA)
        .csv(path)
    )

"""
O codigo acima define os tipos esperados de dados,
Evita que o Spark tente adivinhar o shchema e
le qualquer CSV de registros no mesmo formato

@hugaojanuario
"""