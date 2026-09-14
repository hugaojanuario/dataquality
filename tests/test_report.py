from datetime import datetime

from sincro.models import CheckResult, ValidationReport
from sincro.report import write_html_report


def test_write_html_report_escapes_values(tmp_path):
    report = ValidationReport(
        migration_name="example",
        started_at=datetime(2026, 1, 1, 10, 0),
        finished_at=datetime(2026, 1, 1, 10, 1),
        results=[
            CheckResult(
                name="Required fields",
                rule="not_null",
                status="failed",
                issue_count=1,
                message="Divergence",
                sample=[{"name": "<script>alert(1)</script>"}],
            )
        ],
    )

    output = write_html_report(report, tmp_path / "report.html")
    html = output.read_text(encoding="utf-8")

    assert report.passed is False
    assert report.issue_count == 1
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# @hugaojanuario
