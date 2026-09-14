from typing import Any

from pyspark.sql import DataFrame

from sincro.checks import (
    find_duplicate_keys,
    find_invalid_dates,
    find_invalid_pattern,
    find_invalid_values,
    find_missing_records,
    find_null_values,
    find_orphan_records,
    find_suspicious_text,
    find_value_differences,
)


def _count_difference(
    source: DataFrame,
    target: DataFrame,
) -> DataFrame:
    source_count = source.count()
    target_count = target.count()
    if source_count == target_count:
        return source.sparkSession.createDataFrame(
            [],
            "source_count long, target_count long, difference long",
        )
    return source.sparkSession.createDataFrame(
        [(source_count, target_count, target_count - source_count)],
        ["source_count", "target_count", "difference"],
    )


def execute_rule(
    rule_config: dict[str, Any],
    datasets: dict[str, DataFrame],
) -> DataFrame:
    """Traduz uma regra YAML para uma validação Spark."""
    rule = rule_config["rule"]
    dataframe = datasets[rule_config.get("dataset", "target")]
    if rule == "unique":
        return find_duplicate_keys(dataframe, rule_config["key"])
    if rule == "not_null":
        return find_null_values(dataframe, rule_config["columns"])
    if rule == "allowed_values":
        return find_invalid_values(dataframe, rule_config["column"], rule_config["allowed"])
    if rule == "pattern":
        return find_invalid_pattern(dataframe, rule_config["column"], rule_config["pattern"])
    if rule == "valid_date":
        return find_invalid_dates(dataframe, rule_config["column"], rule_config["format"])
    if rule == "no_orphans":
        return find_orphan_records(
            dataframe,
            datasets[rule_config["parent_dataset"]],
            rule_config["child_key"],
            rule_config["parent_key"],
        )
    if rule == "suspicious_text":
        return find_suspicious_text(dataframe, rule_config["columns"])
    if rule == "count_matches":
        return _count_difference(dataframe, datasets[rule_config["target_dataset"]])
    if rule == "missing_records":
        return find_missing_records(
            dataframe,
            datasets[rule_config["target_dataset"]],
            rule_config["key"],
        )
    if rule == "value_differences":
        return find_value_differences(
            dataframe,
            datasets[rule_config["target_dataset"]],
            rule_config["key"],
            rule_config["column"],
        )
    raise ValueError(f"Regra não suportada: {rule}")


# @hugaojanuario
