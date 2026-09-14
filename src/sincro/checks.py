from functools import reduce

from pyspark.sql import DataFrame
from pyspark.sql.functions import col, instr, length, lit, trim, try_to_timestamp


def find_duplicate_keys(dataframe: DataFrame, key: str | list[str]) -> DataFrame:
    """Retorna chaves que aparecem mais de uma vez."""
    keys = [key] if isinstance(key, str) else key
    return dataframe.groupBy(*keys).count().filter(col("count") > 1)


def find_missing_records(
    source: DataFrame, target: DataFrame, key: str | list[str]
) -> DataFrame:
    """Retorna registros da origem que não existem no destino."""
    keys = [key] if isinstance(key, str) else key
    return source.join(target.select(*keys).dropDuplicates(), on=keys, how="left_anti")


def find_value_differences(
    source: DataFrame, target: DataFrame, key: str, column: str
) -> DataFrame:
    """Compara uma coluna entre registros com a mesma chave."""
    joined = source.alias("source").join(
        target.dropDuplicates([key]).alias("target"),
        col(f"source.{key}") == col(f"target.{key}"),
        how="inner",
    )
    return joined.filter(
        ~col(f"source.{column}").eqNullSafe(col(f"target.{column}"))
    ).select(
        col(f"source.{key}").alias(key),
        col(f"source.{column}").alias("source_value"),
        col(f"target.{column}").alias("target_value"),
    )


def find_null_values(dataframe: DataFrame, columns: list[str]) -> DataFrame:
    """Encontra campos obrigatórios nulos ou vazios."""
    if not columns:
        raise ValueError("Informe ao menos uma coluna obrigatória.")
    conditions = [
        col(column).isNull() | (trim(col(column).cast("string")) == "")
        for column in columns
    ]
    return dataframe.filter(reduce(lambda left, right: left | right, conditions))


def find_invalid_values(
    dataframe: DataFrame, column: str, allowed: list[str]
) -> DataFrame:
    """Encontra valores fora de um domínio permitido."""
    return dataframe.filter(col(column).isNotNull() & ~col(column).isin(allowed))


def find_invalid_pattern(
    dataframe: DataFrame, column: str, pattern: str
) -> DataFrame:
    """Encontra textos que não respeitam uma expressão regular."""
    return dataframe.filter(
        col(column).isNotNull() & ~col(column).cast("string").rlike(pattern)
    )


def find_invalid_dates(
    dataframe: DataFrame, column: str, date_format: str
) -> DataFrame:
    """Encontra datas preenchidas que não podem ser interpretadas."""
    value = trim(col(column).cast("string"))
    return dataframe.filter(
        (length(value) > 0)
        & try_to_timestamp(value, lit(date_format)).isNull()
    )


def find_orphan_records(
    child: DataFrame,
    parent: DataFrame,
    child_key: str | list[str],
    parent_key: str | list[str],
) -> DataFrame:
    """Encontra filhos sem registro correspondente no conjunto pai."""
    child_keys = [child_key] if isinstance(child_key, str) else child_key
    parent_keys = [parent_key] if isinstance(parent_key, str) else parent_key
    if len(child_keys) != len(parent_keys):
        raise ValueError("As chaves filha e pai devem ter o mesmo tamanho.")
    parent_projection = parent.select(
        *[
            col(parent_name).alias(child_name)
            for child_name, parent_name in zip(child_keys, parent_keys, strict=True)
        ]
    ).dropDuplicates()
    return child.join(parent_projection, on=child_keys, how="left_anti")


def find_suspicious_text(
    dataframe: DataFrame, columns: list[str]
) -> DataFrame:
    """Detecta caracteres de substituição, NUL e prefixo antes do RTF."""
    if not columns:
        raise ValueError("Informe ao menos uma coluna de texto.")
    conditions = []
    for column in columns:
        value = col(column).cast("string")
        conditions.extend(
            [
                instr(value, "�") > 0,
                instr(value, chr(0)) > 0,
                instr(value, r"{\rtf") > 1,
            ]
        )
    return dataframe.filter(reduce(lambda left, right: left | right, conditions))


# @hugaojanuario
