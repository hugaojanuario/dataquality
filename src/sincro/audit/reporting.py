from dataclasses import asdict
from datetime import datetime
from html import escape
import json
from pathlib import Path

from sincro import __version__
from .storage import atomic_write, save


def write_report(run, path):
    def e(value):
        return escape(str(value))

    sections = []
    for severity in ('critical', 'warning', 'info'):
        rows = ''.join(f'<tr><td>{e(f.table)}</td><td>{e(f.check)}</td><td class="{e(f.status)}">{e(f.status)}</td><td>{e(f.message)}</td><td>{e(json.dumps(f.metrics, ensure_ascii=False))}</td></tr>' for f in sorted(run.findings, key=lambda f: (f.table, f.check)) if f.severity == severity)
        sections.append(f'<h2>{severity}</h2><table><tr><th>Tabela</th><th>Validação</th><th>Estado</th><th>Mensagem</th><th>Métricas</th></tr>{rows}</table>')
    stages = []
    for stage in run.stages:
        try:
            duration = f'{(datetime.fromisoformat(stage.finished_at) - datetime.fromisoformat(stage.started_at)).total_seconds():.2f}s'
        except (ValueError, TypeError):
            duration = 'indisponível'
        stages.append(f'<li>{e(stage.name)}: {e(stage.status)} — {duration}</li>')
    inventories = []
    for snapshot in run.snapshots:
        rows = ''.join(f'<tr><td>{e(t.id)}</td><td>{len(t.columns)}</td><td>{snapshot.profiles[t.id].count if t.id in snapshot.profiles else "erro"}</td></tr>' for t in snapshot.tables)
        inventories.append(f'<h3>{e(snapshot.role)} / {e(snapshot.engine)}</h3><p>Snapshot {e(snapshot.id)} · {e(snapshot.captured_at)} · completo: {snapshot.complete}</p><table><tr><th>Tabela</th><th>Colunas</th><th>Registros</th></tr>{rows}</table>')
    explanation = ('Evidências implementadas conferem dentro do escopo confirmado; exclusões não foram auditadas.' if run.status == 'passed' else 'Sem aprovação global: consulte divergências, erros e evidências pendentes abaixo.')
    html = f'''<!doctype html><html lang="pt-BR"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Sincro — auditoria</title>
<style>body{{font:15px system-ui;margin:32px;color:#182737}}table{{border-collapse:collapse;width:100%;margin-bottom:24px}}td,th{{border:1px solid #ccd5dd;padding:8px;text-align:left;overflow-wrap:anywhere}}pre{{white-space:pre-wrap;overflow-wrap:anywhere}}.passed{{color:#176b36}}.failed,.error{{color:#ad2525}}.inconclusive{{color:#875900}}</style>
<h1>Sincro — {e(run.status)}</h1><p>{e(explanation)}</p>
<p>Execução: {e(run.run_id)} · Sincro {e(__version__)} · formato snapshot/manifesto: 1</p>
<p>Qualidade encontrada: {e(run.quality)}. Cobertura de tabelas: {run.table_coverage:.1f}%; colunas: {run.column_coverage:.1f}%.
Exclusões justificadas incluídas na cobertura: {run.excluded_tables} tabelas, {run.excluded_columns} colunas.</p>
<p>Amostras desativadas. Extremos e registros são comparados por HMAC, sem valores reais. Inventário pode revelar estrutura interna; proteja os artefatos.</p>
<h2>Etapas e duração</h2><ul>{''.join(stages)}</ul>
<h2>Inventário antes/depois</h2>{''.join(inventories)}
<h2>Mapeamentos e exclusões</h2><pre>{e(json.dumps(asdict(run.manifest), ensure_ascii=False, indent=2))}</pre>
{''.join(sections)}</html>'''
    output = atomic_write(path, html)
    # Persist machine-readable audit state/evidence alongside the human report.
    save(Path(path).with_suffix('.json'), run)
    return output
