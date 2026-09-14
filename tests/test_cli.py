from datetime import datetime
from unittest.mock import patch

from sincro.cli import main
from sincro.models import CheckResult, ValidationReport


def _report() -> ValidationReport:
    return ValidationReport(
        migration_name="example",
        started_at=datetime(2026, 1, 1),
        finished_at=datetime(2026, 1, 1),
        results=[CheckResult('synthetic', 'count', 'passed', 0, 'OK')],
    )


def test_validate_command_generates_report(tmp_path):
    config = {"migration": {"name": "example"}}
    output = tmp_path / "report.html"
    with (
        patch("sincro.cli.load_config", return_value=config),
        patch("sincro.cli.run_validation", return_value=_report()) as run,
    ):
        exit_code = main(
            ["validate", "--config", "configs/example.yml", "--report", str(output)]
        )
    assert exit_code == 0
    assert output.exists()
    run.assert_called_once_with(config)


def test_validate_command_dispatches_package_mode(tmp_path):
    config = {"mode": "package", "package": {"files": []}}
    with (
        patch("sincro.cli.load_config", return_value=config),
        patch(
            "sincro.cli.run_package_validation", return_value=_report()
        ) as run,
    ):
        exit_code = main(
            ["validate", "--config", "package.yml", "--report", str(tmp_path / "r.html")]
        )
    assert exit_code == 0
    run.assert_called_once_with(config)


# @hugaojanuario
