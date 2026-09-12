from datetime import datetime
from typing import Any

from pyspark.sql import DataFrame, Row

from dataqualy.checks import (
    find_duplicate_keys,
    find_missing_records,
    find_value_differences,
)
from dataqualy.datasource import collect_jars, read_dataset
from dataqualy.models import CheckResult, ValidationReport
from dataqualy.rules import execute_rule
from dataqualy.spark import create_spark_session


def _evaluate(
    dataframe: DataFrame, *, name: str, rule: str, sample_size: int
) -> CheckResult:
    issue_count = dataframe.count()
    sample = [
        {key: "[redigido]" for key in row.asDict(recursive=True)}
        for row in dataframe.limit(sample_size).collect()
    ]
    return CheckResult(
        name, rule, "passed" if issue_count == 0 else "failed", issue_count,
        "Nenhuma divergência encontrada." if issue_count == 0
        else f"{issue_count} divergência(s) encontrada(s).",
        sample,
    )


def run_validation(config: dict[str, Any]) -> ValidationReport:
    """Executa regras sobre duas ou várias fontes configuradas."""
    report = ValidationReport(
        config.get("migration", {}).get("name", "validation"),
        datetime.now(),
    )
    sample_size = max(0, min(20, int(config.get("report", {}).get("sample_size", 0))))
    source_configs = config.get("datasets") or {
        "source": config["source"],
        "target": config["target"],
    }
    spark = None
    try:
        spark = create_spark_session(collect_jars(*source_configs.values()))
        spark.sparkContext.setLogLevel("ERROR")
        datasets = {
            name: read_dataset(spark, source_config)
            for name, source_config in source_configs.items()
        }
        checks = config["checks"]
        if "source" in datasets and "target" in datasets and config.get("key"):
            source, target, key = datasets["source"], datasets["target"], config["key"]
            if checks.get("duplicate_keys", False):
                report.results.append(_evaluate(
                    find_duplicate_keys(target, key), name="Chaves duplicadas",
                    rule="duplicate_keys", sample_size=sample_size,
                ))
            if checks.get("missing_records", False):
                report.results.append(_evaluate(
                    find_missing_records(source, target, key),
                    name="Registros ausentes no destino",
                    rule="missing_records", sample_size=sample_size,
                ))
            for column in checks.get("compare_columns", []):
                report.results.append(_evaluate(
                    find_value_differences(source, target, key, column),
                    name=f"Diferenças na coluna {column}",
                    rule="value_differences", sample_size=sample_size,
                ))
        for rule_config in checks.get("rules", []):
            report.results.append(_evaluate(
                execute_rule(rule_config, datasets),
                name=rule_config.get("name", rule_config["rule"]),
                rule=rule_config["rule"], sample_size=sample_size,
            ))
    except Exception:
        report.results.append(CheckResult(
            "Execução incompleta", "execution", "error", 0,
            "Verifique conexão, driver, permissões, tipos e configuração. Nenhuma aprovação emitida.",
        ))
    finally:
        report.finished_at = datetime.now()
        if spark is not None:
            spark.stop()
    return report


# @hugaojanuario
