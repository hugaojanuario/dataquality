from html import escape
from pathlib import Path

from dataqualy.models import CheckResult, ValidationReport


def _render_sample(result: CheckResult) -> str:
    if not result.sample:
        return "<p>Sem amostra de divergências.</p>"

    columns = list(result.sample[0])
    header = "".join(f"<th>{escape(column)}</th>" for column in columns)
    rows = []
    for item in result.sample:
        cells = "".join(
            f"<td>{escape(str(item.get(column, '')))}</td>" for column in columns
        )
        rows.append(f"<tr>{cells}</tr>")

    return (
        "<table><thead><tr>"
        f"{header}</tr></thead><tbody>{''.join(rows)}</tbody></table>"
    )


def write_html_report(report: ValidationReport, path: str | Path) -> Path:
    """Gera um relatório HTML autocontido, sem dados de conexão."""
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)

    cards = []
    for result in report.results:
        status_label = "APROVADO" if result.passed else "DIVERGÊNCIA"
        cards.append(
            "<section class='check'>"
            f"<h2>{escape(result.name)}</h2>"
            f"<p class='{result.status}'>{status_label}</p>"
            f"<p>{escape(result.message)}</p>"
            f"<p><strong>Regra:</strong> {escape(result.rule)} | "
            f"<strong>Ocorrências:</strong> {result.issue_count}</p>"
            f"{_render_sample(result)}"
            "</section>"
        )

    finished = report.finished_at.isoformat(timespec="seconds") if report.finished_at else "-"
    overall = "APROVADO" if report.passed else "COM DIVERGÊNCIAS"
    html = f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>DataQualy - {escape(report.migration_name)}</title>
  <style>
    body {{ font: 15px Arial, sans-serif; margin: 32px; color: #172033; }}
    header, .check {{ border: 1px solid #d8deea; border-radius: 10px; padding: 20px; margin-bottom: 16px; }}
    .passed {{ color: #16794b; font-weight: bold; }}
    .failed, .error {{ color: #b42318; font-weight: bold; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
    th, td {{ border: 1px solid #d8deea; padding: 8px; text-align: left; }}
    th {{ background: #f3f6fa; }}
  </style>
</head>
<body>
  <header>
    <h1>DataQualy</h1>
    <p>Amostras, quando presentes, podem conter dados pessoais. No fluxo de validação são limitadas e mascaradas.</p>
    <p><strong>Migração:</strong> {escape(report.migration_name)}</p>
    <p><strong>Resultado:</strong> {overall}</p>
    <p><strong>Divergências:</strong> {report.issue_count}</p>
    <p><strong>Início:</strong> {report.started_at.isoformat(timespec="seconds")}</p>
    <p><strong>Fim:</strong> {finished}</p>
  </header>
  {''.join(cards)}
</body>
</html>
"""
    output.write_text(html, encoding="utf-8")
    return output


# @hugaojanuario
