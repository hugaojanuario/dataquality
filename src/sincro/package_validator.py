import codecs
import csv
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any

from sincro.models import CheckResult, ValidationReport


def _result(name: str, rule: str, issues: list[dict[str, Any]]) -> CheckResult:
    count = len(issues)
    return CheckResult(
        name=name,
        rule=rule,
        status="passed" if count == 0 else "failed",
        issue_count=count,
        message=(
            "Nenhuma divergência encontrada."
            if count == 0
            else f"{count} divergência(s) encontrada(s)."
        ),
        sample=issues[:20],
    )


def check_csv_layout(file_config: dict[str, Any]) -> list[CheckResult]:
    """Valida existência, UTF-8 sem BOM e ordem exata do cabeçalho."""
    path = Path(file_config["path"])
    if not path.is_file():
        return [_result(path.name, "file_exists", [{"path": str(path)}])]

    data = path.read_bytes()
    encoding_issues = []
    if data.startswith(codecs.BOM_UTF8):
        encoding_issues.append({"path": str(path), "problem": "UTF-8 BOM"})
    try:
        text = data.decode(file_config.get("encoding", "utf-8"))
    except UnicodeDecodeError as error:
        text = ""
        encoding_issues.append({"path": str(path), "problem": str(error)})

    results = [_result(path.name, "utf8_without_bom", encoding_issues)]
    expected = file_config.get("expected_columns")
    if expected is not None and text:
        header = next(csv.reader([text.splitlines()[0]], delimiter=file_config.get("delimiter", ",")))
        issues = [] if header == expected else [{"expected": expected, "actual": header}]
        results.append(_result(path.name, "csv_header", issues))
    return results


def check_attachments(config: dict[str, Any]) -> CheckResult:
    """Confere caminho, tamanho e hash dos arquivos listados no manifesto."""
    manifest = Path(config["manifest"])
    root = Path(config["root"]).resolve()
    issues: list[dict[str, Any]] = []
    if not manifest.is_file():
        return _result("Anexos", "attachments", [{"manifest": str(manifest)}])

    with manifest.open(encoding=config.get("encoding", "utf-8"), newline="") as file:
        for row_number, row in enumerate(csv.DictReader(file), start=2):
            relative = row.get(config["path_column"], "")
            candidate = (root / relative).resolve()
            issue: dict[str, Any] = {"row": row_number, "path": relative}
            if root not in candidate.parents and candidate != root:
                issue["problem"] = "path_outside_root"
            elif not candidate.is_file():
                issue["problem"] = "missing"
            else:
                expected_size = row.get(config.get("size_column", ""))
                if expected_size and candidate.stat().st_size != int(expected_size):
                    issue["problem"] = "size_mismatch"
                hash_column = config.get("hash_column")
                expected_hash = row.get(hash_column, "") if hash_column else ""
                if expected_hash:
                    algorithm = config.get("algorithm", "sha256")
                    digest = hashlib.new(algorithm, candidate.read_bytes()).hexdigest()
                    if digest.lower() != expected_hash.lower():
                        issue["problem"] = "hash_mismatch"
            if "problem" in issue:
                issues.append(issue)
    return _result("Anexos", "attachments", issues)


def run_package_validation(config: dict[str, Any]) -> ValidationReport:
    """Executa validações anteriores à importação do pacote."""
    report = ValidationReport(
        config.get("migration", {}).get("name", "package"),
        datetime.now(),
    )
    package = config["package"]
    for file_config in package.get("files", []):
        report.results.extend(check_csv_layout(file_config))
    if package.get("attachments"):
        report.results.append(check_attachments(package["attachments"]))
    sample_size = max(0, min(20, int(config.get("report", {}).get("sample_size", 0))))
    for result in report.results:
        result.sample = [
            {key: "[redigido]" for key in sample}
            for sample in result.sample[:sample_size]
        ]
    report.finished_at = datetime.now()
    return report


# @hugaojanuario
