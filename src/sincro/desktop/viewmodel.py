"""Typed Qt view models. Only queued slots mutate presentation state."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
import json
import os
import re

from PySide6.QtCore import QObject, Property, QRunnable, QSettings, QStandardPaths, QThreadPool, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices

from sincro.audit.connectors import AuditError, Cancelled
from sincro.audit.domain import AuditRun, CaptureOptions, ConnectionProfile, Manifest, Snapshot
from sincro.audit.engines import ENGINES
from sincro.audit.mapping import validate_manifest
from sincro.audit.orchestration import Project
from sincro.audit.storage import save
from .service import AuditService, Request, Result, UserError

STATUS = {'passed': 'Aprovado', 'failed': 'Divergência', 'inconclusive': 'Inconclusivo',
          'error': 'Erro', 'skipped': 'Ignorado', 'pending': 'Pendente', 'running': 'Em execução'}
ENGINELABELS = ['Firebird', 'PostgreSQL', 'SQL Server · experimental', 'MySQL · experimental']
STAGES = {'source': 'Captura da origem', 'baseline': 'Baseline do destino',
          'target': 'Destino convertido', 'comparison': 'Comparação'}


def migrate_settings(current: QSettings, legacy: QSettings) -> QSettings:
    """Carry saved projects and appearance into the renamed application."""
    if not current.allKeys():
        for key in legacy.allKeys():
            current.setValue(key, legacy.value(key))
        current.sync()
    return current


def application_settings() -> QSettings:
    current = QSettings('Sincro', 'Desktop')
    legacy = QSettings('Data' + 'Quality', 'Desktop')
    return migrate_settings(current, legacy)


def default_project_directory() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppLocalDataLocation)
    return Path(base or Path.home() / '.sincro') / 'projects' / 'audit-project'


def display_table(table_id: str) -> str:
    try:
        parts = json.loads(table_id)
        return '.'.join(p for p in parts if p) if isinstance(parts, list) else table_id
    except (ValueError, TypeError):
        return table_id or 'Sem destino'


def safe_error(exc: Exception, action: str) -> tuple[str, str]:
    # Raw exception text / traceback can contain JDBC URLs and secrets. Never forward it.
    if isinstance(exc, UserError):
        return str(exc), 'Verifique os pré-requisitos indicados e tente novamente.'
    if isinstance(exc, Cancelled):
        return 'Operação cancelada. Nenhuma nova aprovação emitida.', 'Cancelamento cooperativo solicitado pelo operador.'
    if isinstance(exc, AuditError):
        # Connector errors contain only controlled public messages, never raw driver text.
        return str(exc), f'Etapa: {action}. Verifique os pré-requisitos indicados e tente novamente.'
    if isinstance(exc, ModuleNotFoundError):
        return ('Dependência ausente no ambiente ou executável.', 'Confira a inclusão de módulos Python no empacotamento.')
    category = 'arquivo ou formato' if isinstance(exc, (OSError, ValueError, TypeError)) else 'conexão ou execução'
    return ('Não foi possível concluir. Confira projeto, JAR, Java, credenciais, permissões e ordem das etapas.',
            f'Etapa: {action}. Categoria: {category}. Detalhes do driver omitidos para proteger credenciais.')


class ConnectionViewModel(QObject):
    changed = Signal()
    profileChanged = Signal()

    def __init__(self, engine: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._profile = ConnectionProfile(engine, '', '')
        self._port_text = str(ENGINES[engine].port)
        self._password: str | None = None
        self._status = 'Não testada'

    @Property('QVariantMap', notify=changed)
    def fields(self) -> dict[str, Any]:
        result = asdict(self._profile)
        result.update(port=self._port_text,
                      driver=ENGINES[self._profile.engine].driver,
                      engineIndex=list(ENGINES).index(self._profile.engine), status=self._status)
        return result

    @Slot(str, str)
    def setField(self, name: str, value: str) -> None:
        if name == 'engine':
            if value not in ENGINES:
                return
            self._profile.engine, self._profile.port = value, ENGINES[value].port
            self._port_text = str(ENGINES[value].port)
        elif name == 'port':
            self._port_text = value
            self._profile.port = int(value) if value.isdigit() and 1 <= int(value) <= 65535 else 0
        elif name in ('host', 'database', 'user', 'jar', 'password_env'):
            setattr(self._profile, name, value)
        else:
            return
        self._status = 'Não testada'
        self.changed.emit()
        self.profileChanged.emit()

    @Slot(str)
    def setSecret(self, value: str) -> None:
        self._password = value
        self._status = 'Não testada'
        self.changed.emit()

    def profile(self) -> ConnectionProfile:
        if not self._profile.database.strip() or self._profile.port == 0:
            raise UserError('Preencha o banco e uma porta válida nas conexões.')
        return deepcopy(self._profile)

    def replace(self, profile: ConnectionProfile) -> None:
        self._profile, self._password, self._status = profile, None, 'Não testada'
        self._port_text = str(profile.port or ENGINES[profile.engine].port)
        self.changed.emit()


class WorkerSignals(QObject):
    done = Signal(object)
    failed = Signal(str, str)
    progress = Signal(str)


class Job(QRunnable):
    def __init__(self, service: AuditService, request: Request) -> None:
        super().__init__()
        self.service, self.request = service, request
        self.signals = WorkerSignals()

    @Slot()
    def run(self) -> None:
        try:
            result = self.service.execute(self.request, self.signals.progress.emit)
            self.signals.done.emit(result)
        except Exception as exc:
            self.signals.failed.emit(*safe_error(exc, self.request.action))
        finally:
            self.request.passwords.clear()
            self.request.secret = None


class AppViewModel(QObject):
    changed = Signal()
    appearanceChanged = Signal()
    toast = Signal(str, str)
    readyToClose = Signal()
    detailsRequested = Signal()

    def __init__(self, *, demo: bool = False, directory: str = '',
                 service_factory=AuditService, settings: QSettings | None = None) -> None:
        super().__init__()
        self.source = ConnectionViewModel('firebird', self)
        self.target = ConnectionViewModel('postgresql', self)
        self.source.changed.connect(self.changed)
        self.target.changed.connect(self.changed)
        self.source.profileChanged.connect(self._persist_project)
        self.target.profileChanged.connect(self._persist_project)
        self._settings = settings if settings is not None else application_settings()
        self._native_backdrop = False
        self._dark = self._settings.value('dark', False, type=bool)
        self._reduced = self._settings.value('reducedMotion', False, type=bool)
        self._temp = TemporaryDirectory(prefix='sincro-demo-') if demo else None
        last_project = self._settings.value('lastProject', '')
        remembered = Path(last_project) if last_project and Path(last_project).exists() else None
        self._directory = Path(self._temp.name) if self._temp else Path(directory) if directory else remembered or default_project_directory()
        self._demo, self._page = demo, 0
        self._name = 'Migração de catálogo' if demo else self._directory.name
        self._description = 'Dados sintéticos para demonstração' if demo else 'Auditoria local de migração de dados'
        self._busy, self._closing, self._status = False, False, 'Pronto para começar'
        self._error, self._details, self._progress = '', '', -1.0
        self._profile, self._quiescent, self._system = 'exhaustive' if demo else 'balanced', False, False
        self._key_env = 'SINCRO_EVIDENCE_KEY'
        self._discovery: dict[str, Snapshot] = {}
        self._snapshots: dict[str, Snapshot] = {}
        self._manifest: Manifest | None = None
        self._project: Project | None = None
        self._run: AuditRun | None = None
        self._active_action = ""
        self._report = ''
        self._selected: set[str] = set()
        self._mapping_index = -1
        self._search, self._mapping_filter = '', 'Todos'
        self._finding_search, self._finding_status, self._finding_rule = '', 'Todos', 'Todas'
        self._timeline: list[str] = []
        self._service_factory = service_factory
        self._service: AuditService | None = None
        self._job: Job | None = None
        self._loading_project = False
        self._pool = QThreadPool(self)
        self._pool.setMaxThreadCount(1)
        if demo:
            for vm, database in [(self.source, 'synthetic_source'), (self.target, 'synthetic_target')]:
                vm._profile.database = database
                vm._profile.host = 'demo.invalid'
                vm._profile.user = 'synthetic_reader'
                vm._status = 'Simulada · sem conexão'

    def _project_document(self) -> Project:
        project = self._project or Project()
        project.name = self._name
        project.description = self._description
        project.source = deepcopy(self.source._profile)
        project.target = deepcopy(self.target._profile)
        project.capture_profile = self._profile
        project.include_system = self._system
        project.key_env = self._key_env
        project.last_page = self._page
        return project

    @Slot()
    def _persist_project(self) -> None:
        if self._demo or self._loading_project or self._busy:
            return
        try:
            self._project = self._project_document()
            save(self._directory / 'project.json', self._project)
        except (OSError, ValueError, TypeError):
            self.toast.emit('Não foi possível salvar o projeto. Confira a pasta selecionada.', 'error')

    def _persist_manifest(self) -> None:
        if self._demo or self._manifest is None:
            return
        try:
            save(self._directory / 'mapping.json', self._manifest)
        except (OSError, ValueError, TypeError):
            self.toast.emit('Não foi possível salvar o mapeamento.', 'error')

    def _remember_project(self) -> None:
        if self._demo:
            return
        current = str(self._directory.resolve())
        stored = self._settings.value('recentProjects', [])
        paths = [stored] if isinstance(stored, str) else list(stored or [])
        self._settings.setValue('recentProjects', [current] + [p for p in paths if p != current][:4])
        self._settings.setValue('lastProject', current)

    def _restore_project(self, project: Project) -> None:
        self._loading_project = True
        try:
            self._project = project
            self._name = project.name or self._directory.name
            self._description = project.description or 'Auditoria local de migração de dados'
            self._profile = project.capture_profile
            self._system = project.include_system
            self._key_env = project.key_env
            self._page = project.last_page if 0 <= project.last_page <= 7 else 0
            self._quiescent = False
            if project.source is not None:
                self.source.replace(project.source)
            if project.target is not None:
                self.target.replace(project.target)
        finally:
            self._loading_project = False

    def _reset_project_context(self, directory: Path) -> None:
        self._loading_project = True
        try:
            self._directory = directory
            self._name = directory.name
            self._description = 'Auditoria local de migração de dados'
            self._profile, self._quiescent, self._system = 'balanced', False, False
            self._key_env, self._page = 'SINCRO_EVIDENCE_KEY', 0
            self.source.replace(ConnectionProfile('firebird', '', ''))
            self.target.replace(ConnectionProfile('postgresql', '', ''))
            self._snapshots, self._discovery, self._manifest, self._project, self._run = {}, {}, None, None, None
            self._report, self._mapping_index, self._selected = '', -1, set()
        finally:
            self._loading_project = False

    @Property(QObject, constant=True)
    def sourceConnection(self) -> ConnectionViewModel:
        return self.source

    @Property(QObject, constant=True)
    def targetConnection(self) -> ConnectionViewModel:
        return self.target

    @Property(bool, notify=appearanceChanged)
    def nativeBackdrop(self) -> bool:
        return self._native_backdrop

    @Property(bool, notify=appearanceChanged)
    def dark(self) -> bool:
        return self._dark

    @Property(bool, notify=appearanceChanged)
    def reducedMotion(self) -> bool:
        return self._reduced

    @Slot(bool)
    def setDark(self, value: bool) -> None:
        self._dark = value
        self._settings.setValue('dark', value)
        self.appearanceChanged.emit()

    @Slot(bool)
    def setReducedMotion(self, value: bool) -> None:
        self._reduced = value
        self._settings.setValue('reducedMotion', value)
        self.appearanceChanged.emit()

    def _mapping_status(self, mapping) -> str:
        if mapping.ignored:
            return 'Ignorado'
        if not mapping.target:
            return 'Ambíguo' if ('Ambíguo' in mapping.reason or 'disputado' in mapping.reason) else 'Não mapeado'
        return 'Confirmado' if mapping.confirmed else 'Revisar'

    @Property('QVariantMap', notify=changed)
    def state(self) -> dict[str, Any]:
        mappings = self._manifest.mappings if self._manifest else []
        rows = []
        ignored = {m.source for m in mappings if m.ignored}
        for side, snapshot in self._discovery.items():
            if side == 'baseline':
                continue
            for table in snapshot.tables:
                if self._search.casefold() not in display_table(table.id).casefold():
                    continue
                rows.append(dict(id=side + ':' + table.id, tableId=table.id, side=side,
                                 selected=table.id in self._selected and side == 'source',
                                 name=display_table(table.id), origin='Origem' if side == 'source' else 'Destino',
                                 columns=str(len(table.columns)), pk=', '.join(table.primary_key.columns) or 'Sem PK',
                                 fk=str(len(table.foreign_keys)), status='Ignorada' if side == 'source' and table.id in ignored else 'No inventário'))
        maprows = []
        for i, mapping in enumerate(mappings):
            status = self._mapping_status(mapping)
            filters = {'Mapeados': bool(mapping.target) and not mapping.ignored,
                       'Não mapeados': not mapping.target and status != 'Ambíguo' and not mapping.ignored,
                       'Ambíguos': status == 'Ambíguo', 'Ignorados': mapping.ignored}
            if self._mapping_filter != 'Todos' and not filters.get(self._mapping_filter, False):
                continue
            maprows.append(dict(index=i, source=display_table(mapping.source), target=display_table(mapping.target),
                                confidence=f'{mapping.confidence:.0%}', status=status,
                                tone='passed' if status == 'Confirmado' else 'skipped' if mapping.ignored else 'inconclusive'))
        editor: dict[str, Any] = {}
        if 0 <= self._mapping_index < len(mappings):
            mapping = mappings[self._mapping_index]
            editor = dict(index=self._mapping_index, source=display_table(mapping.source), target=mapping.target,
                          sourceKey=', '.join(mapping.source_key), targetKey=', '.join(mapping.target_key),
                          ignored=mapping.ignored, justification=mapping.justification, confirmed=mapping.confirmed,
                          reason=mapping.reason, columns=[asdict(c) for c in mapping.columns])
        target_snapshot = self._discovery.get('target') or self._snapshots.get('baseline')
        targets = [dict(label='Selecione o destino', value='')]
        if target_snapshot:
            targets += [dict(label=display_table(t.id), value=t.id) for t in target_snapshot.tables]
        findings = []
        all_findings = self._run.findings if self._run else [f for s in self._snapshots.values() for f in s.findings]
        for i, finding in enumerate(all_findings):
            if self._finding_search.casefold() not in display_table(finding.table).casefold():
                continue
            if self._finding_status != 'Todos' and STATUS[finding.status] != self._finding_status:
                continue
            if self._finding_rule != 'Todas' and finding.check != self._finding_rule:
                continue
            findings.append(dict(index=i, table=display_table(finding.table) if finding.table else 'Escopo global',
                                 rule=finding.check, status=STATUS[finding.status], tone=finding.status,
                                 severity={'info': 'Informação', 'warning': 'Alerta', 'critical': 'Crítica'}[finding.severity],
                                 message=finding.message))
        findings.sort(key=lambda f: {'error': 0, 'failed': 1, 'inconclusive': 2, 'skipped': 3, 'passed': 4}.get(f['tone'], 5))
        stages = [dict(name=STAGES.get(s.name, s.name), status=STATUS[s.status], tone=s.status,
                       time=s.finished_at[:19].replace('T', ' ')) for s in self._project.stages] if self._project else []
        counts = [sum(p.count for p in self._snapshots[side].profiles.values()) if side in self._snapshots else None
                  for side in ('source', 'target')]
        blocked = sum(not m.confirmed or (not m.ignored and (not m.target or any(not c.target and not c.ignored for c in m.columns))) for m in mappings)
        result_status = self._run.status if self._run else 'pending'
        completed = sum(role in self._snapshots and self._snapshots[role].complete for role in ('source', 'baseline', 'target')) + bool(self._run)
        stored = self._settings.value('recentProjects', [])
        recent_paths = [stored] if isinstance(stored, str) else list(stored or [])
        recent_projects = [dict(name=Path(path).name, path=path,
                                current=Path(path) == self._directory.resolve())
                           for path in recent_paths if Path(path).exists()]
        return dict(demo=self._demo, page=self._page, projectName=self._name, description=self._description,
                    directory='Ambiente temporário de demonstração' if self._demo else str(self._directory),
                    busy=self._busy, status=self._status, error=self._error, details=self._details, progress=self._progress,
                    engineNames=ENGINELABELS, engineKeys=list(ENGINES), profile=self._profile, keyEnv=self._key_env,
                    quiescent=self._quiescent, includeSystem=self._system, discoveryRows=rows,
                    discovered=sum(len(s.tables) for s in self._discovery.values()), selectedCount=len(self._selected),
                    mappingRows=maprows, mappingEditor=editor, targetOptions=targets, blocked=blocked,
                    mappingCount=len(mappings), confirmed=sum(m.confirmed for m in mappings),
                    findingRows=findings, findingStatus=self._finding_status, findingRule=self._finding_rule,
                    findingSearch=self._finding_search, discoverySearch=self._search, mappingFilter=self._mapping_filter, rules=['Todas'] + sorted({f.check for f in all_findings}),
                    findingCount=len(all_findings), passed=sum(f.status == 'passed' for f in all_findings),
                    failed=sum(f.status == 'failed' for f in all_findings), resultStatus=result_status,
                    resultLabel=STATUS[result_status], hasResult=self._run is not None,
                    quality=STATUS[self._run.quality] if self._run else 'Não avaliada',
                    tableCoverage=f'{self._run.table_coverage:.0f}%' if self._run else '—',
                    columnCoverage=f'{self._run.column_coverage:.0f}%' if self._run else '—',
                    sourceRows=str(counts[0]) if counts[0] is not None else '—',
                    targetRows=str(counts[1]) if counts[1] is not None else '—',
                    tableCount=str(len(self._snapshots['source'].tables)) if 'source' in self._snapshots else '—',
                    stages=stages, completed=completed, lastRun=stages[-1]['time'] if stages else 'Nenhuma execução',
                    sourceReady=bool(self._snapshots.get('source') and self._snapshots['source'].complete),
                    baselineReady=bool(self._snapshots.get('baseline') and self._snapshots['baseline'].complete),
                    targetReady=bool(self._snapshots.get('target') and self._snapshots['target'].complete),
                    hasReport=bool(self._report), timeline=self._timeline, recentProjects=recent_projects)

    @Slot(int)
    def navigate(self, page: int) -> None:
        if 0 <= page <= 7:
            self._page = page
            self._persist_project()
            self.changed.emit()

    @Slot(str, str)
    def configure(self, field: str, value: str) -> None:
        if self._busy:
            return
        if field == 'name': self._name = value
        elif field == 'description': self._description = value
        elif field == 'profile' and value in ('fast', 'balanced', 'exhaustive'): self._profile = value
        elif field == 'keyEnv': self._key_env = value
        elif field == 'quiescent': self._quiescent = value == 'true'
        elif field == 'system': self._system = value == 'true'
        self._persist_project()
        self.changed.emit()

    @Slot(str, str)
    def filter(self, field: str, value: str) -> None:
        names = {'discovery': '_search', 'mapping': '_mapping_filter', 'table': '_finding_search',
                 'status': '_finding_status', 'rule': '_finding_rule'}
        if field in names:
            setattr(self, names[field], value)
            self.changed.emit()

    @Slot(str, bool)
    def selectTable(self, table_id: str, selected: bool) -> None:
        if selected: self._selected.add(table_id)
        else: self._selected.discard(table_id)
        self.changed.emit()

    @Slot(bool)
    def selectAll(self, selected: bool) -> None:
        for row in self.state['discoveryRows']:
            if row['side'] == 'source':
                if selected: self._selected.add(row['tableId'])
                else: self._selected.discard(row['tableId'])
        self.changed.emit()

    @Slot(str)
    def excludeSelected(self, justification: str) -> None:
        if self._busy: return
        if not justification.strip() or not self._selected or not self._manifest:
            self.toast.emit('Gere sugestões, selecione tabelas de origem e informe uma justificativa.', 'error')
            return
        for mapping in self._manifest.mappings:
            if mapping.source in self._selected:
                mapping.ignored, mapping.confirmed, mapping.justification = True, True, justification.strip()
        self._run, self._report = None, ''
        self._persist_manifest()
        self.changed.emit()
        self.toast.emit('Exclusões aplicadas e salvas; a cobertura será reduzida.', 'inconclusive')

    @Slot(int)
    def editMapping(self, index: int) -> None:
        self._mapping_index = index
        self.changed.emit()

    @Slot(str, str)
    def updateMapping(self, field: str, value: str) -> None:
        if self._busy or not self._manifest or not 0 <= self._mapping_index < len(self._manifest.mappings): return
        mapping = self._manifest.mappings[self._mapping_index]
        if field in ('target', 'justification'): setattr(mapping, field, value)
        elif field in ('source_key', 'target_key'): setattr(mapping, field, [v.strip() for v in value.split(',') if v.strip()])
        elif field == 'ignored': mapping.ignored = value == 'true'
        else: return
        mapping.confirmed = False
        self._run, self._report = None, ''
        self._persist_manifest()
        self.changed.emit()

    @Slot(int, str, str)
    def updateColumn(self, index: int, field: str, value: str) -> None:
        if self._busy or not self._manifest or not 0 <= self._mapping_index < len(self._manifest.mappings): return
        mapping = self._manifest.mappings[self._mapping_index]
        if not 0 <= index < len(mapping.columns): return
        column = mapping.columns[index]
        if field in ('target', 'justification'): setattr(column, field, value)
        elif field == 'ignored': column.ignored = value == 'true'
        else: return
        mapping.confirmed = False
        self._run, self._report = None, ''
        self._persist_manifest()
        self.changed.emit()

    @Slot()
    def confirmMapping(self) -> None:
        if self._busy or not self._manifest or not 0 <= self._mapping_index < len(self._manifest.mappings): return
        mapping = self._manifest.mappings[self._mapping_index]
        try:
            validate_manifest(self._manifest)
            if not mapping.ignored:
                target = next((t for t in self._discovery.get('target', Snapshot('', 'target', '')).tables if t.id == mapping.target), None)
                if target is None or any(not c.ignored and c.target not in {t.name for t in target.columns} for c in mapping.columns):
                    raise UserError('Escolha uma tabela e colunas de destino existentes antes de confirmar.')
                source = next((t for t in self._discovery.get('source', Snapshot('', 'source', '')).tables if t.id == mapping.source), None)
                if source is None or not set(mapping.source_key) <= {c.name for c in source.columns} or not set(mapping.target_key) <= {c.name for c in target.columns}:
                    raise UserError('Revise as chaves: use nomes de colunas existentes, separados por vírgula.')
            mapping.confirmed = True
            self._persist_manifest()
            self.changed.emit()
            self.toast.emit('Tabela revisada e salva.', 'passed')
        except Exception as exc:
            message = str(exc) if isinstance(exc, (UserError, ValueError)) else 'Revise tabela, colunas, chaves e justificativas.'
            self.toast.emit(message, 'error')

    @Slot(str)
    def chooseDirectory(self, url: str) -> None:
        if self._busy or self._demo: return
        path = QUrl(url).toLocalFile()
        if not path: return
        self._reset_project_context(Path(path))
        self.execute('load')

    @Slot(str)
    def openRecentProject(self, path: str) -> None:
        if self._busy or self._demo or not path:
            return
        self._reset_project_context(Path(path))
        self.execute('load')

    @Slot(str, str, str)
    def chooseFile(self, purpose: str, side: str, url: str) -> None:
        if self._busy or self._demo: return
        path = QUrl(url).toLocalFile()
        if not path: return
        if purpose == 'jar':
            (self.source if side == 'source' else self.target).setField('jar', path)
        elif purpose == 'import': self._start('import_' + side, path)
        elif purpose == 'export': self._start('export', path)

    @Slot(str)
    def exportReport(self, url: str) -> None:
        path = QUrl(url).toLocalFile()
        if path and self._report and not self._busy: self._start('export', path)

    @Slot()
    def openReport(self) -> None:
        if self._report:
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(self._report).resolve()))):
                self.toast.emit('Não foi possível abrir o navegador. Exporte o HTML.', 'error')

    @Slot(int)
    def showFinding(self, index: int) -> None:
        findings = self._run.findings if self._run else [f for s in self._snapshots.values() for f in s.findings]
        if 0 <= index < len(findings):
            finding = findings[index]
            self._details = f'{finding.check} · {STATUS[finding.status]}\n\n{finding.message}\n\nMétricas: ' + json.dumps(finding.metrics, ensure_ascii=False) + '\n\nEvidências: ' + (', '.join('[redigido]' for _ in finding.sample[:20]) or 'Sem amostras de dados. Comparação por evidências HMAC.')
            self.changed.emit()
            self.detailsRequested.emit()

    @Slot(str)
    def execute(self, action: str) -> None:
        if self._busy: return
        if self._demo and action not in ('demo', 'load', 'report', 'save_mapping', 'suggest'):
            self.toast.emit('Demonstração sintética: conexões e capturas reais estão desativadas.', 'inconclusive')
            return
        if action == 'demo' and (not self._demo or self._snapshots): return
        self._start(action)

    def _start(self, action: str, file: str = '') -> None:
        if self._busy: return
        self._active_action = action
        if action in ('source', 'baseline', 'target', 'report'):
            # A new attempt must never retain approval from an earlier run.
            self._run, self._report = None, ''
        request = Request(action, self._directory, options=CaptureOptions(profile=self._profile,
                          quiescent=self._quiescent, include_system=self._system),
                          manifest=deepcopy(self._manifest), discovery=deepcopy(self._discovery), file=file)
        try:
            sides = ['source', 'target'] if action == 'discover' else [action[5:]] if action.startswith('test_') else ['source' if action == 'source' else 'target'] if action in ('source', 'baseline', 'target') else []
            for side in sides:
                vm = self.source if side == 'source' else self.target
                request.profiles[side], request.passwords[side] = vm.profile(), vm._password
            if action in ('source', 'baseline', 'target'):
                request.secret = os.getenv(self._key_env)
        except Exception as exc:
            self._failed(*safe_error(exc, action))
            return
        self._busy, self._error, self._details, self._progress = True, '', '', -1.0
        self._status = 'Executando…'
        self._timeline = []
        self._service = self._service_factory()
        self._job = Job(self._service, request)
        self._job.signals.done.connect(self._done, Qt.ConnectionType.QueuedConnection)
        self._job.signals.failed.connect(self._failed, Qt.ConnectionType.QueuedConnection)
        self._job.signals.progress.connect(self._on_progress, Qt.ConnectionType.QueuedConnection)
        self.changed.emit()
        self._pool.start(self._job)

    @Slot(str)
    def _on_progress(self, message: str) -> None:
        # Domain progress contains only role and ordinal, never table names/driver errors.
        if re.fullmatch(r'(source|baseline|target): tabela \d+/\d+', message):
            current, total = map(int, message.split()[-1].split('/'))
            self._progress = max(0, current - 1) / max(1, total)
        else:
            self._progress = -1
        self._status = message
        self._timeline = (self._timeline + [message])[-100:]
        self.changed.emit()

    @Slot(object)
    def _done(self, result: Result) -> None:
        self._busy, self._status, self._progress = False, result.message, 1.0
        if result.action == 'discover':
            self._discovery, self._selected = result.discovery, set()
        elif result.action in ('load', 'demo', 'source', 'baseline', 'target', 'report'):
            self._snapshots = result.snapshots
            self._discovery = dict(result.discovery)
            if not self._discovery:
                self._discovery = dict(result.snapshots)
                if 'baseline' in self._discovery:
                    baseline = self._discovery.pop('baseline')
                    self._discovery.setdefault('target', baseline)
            self._run, self._report = result.run, result.report_path
        if result.manifest is not None: self._manifest = result.manifest
        if result.project is not None:
            self._project = result.project
            if result.action == 'load':
                self._restore_project(result.project)
        if result.action.startswith('test_'):
            vm = self.source if result.action[5:] == 'source' else self.target
            vm._status = 'Conectada'
            vm.changed.emit()
        if result.connection:
            (self.source if result.action.endswith('source') else self.target).replace(result.connection)
        if result.action in ('target', 'report') and result.run: self._page = 7
        if result.action in ('source', 'baseline', 'target') and any(not s.complete for s in result.snapshots.values()):
            self._page = 7
            self._details = 'Captura incompleta. Revise as condições e repita a etapa.\n\n' + '\n'.join(f.message for s in result.snapshots.values() for f in s.findings[:20])
        if result.action == 'load':
            if result.project is None:
                self._persist_project()
            self._remember_project()
        elif not self._demo:
            self._persist_project()
        self.changed.emit()
        if self._details:
            self.detailsRequested.emit()
        if result.action not in ('demo', 'load'):
            tone = result.run.status if result.run else 'inconclusive' if 'incompleta' in result.message else 'passed'
            self.toast.emit(result.message, tone)
        if self._closing: self.readyToClose.emit()

    @Slot(str, str)
    def _failed(self, message: str, details: str) -> None:
        self._busy, self._error, self._details, self._status, self._progress = False, message, details, message, -1
        self.changed.emit()
        self.toast.emit(message, 'error')
        if self._active_action.startswith('test_'):
            vm = self.source if self._active_action.endswith('source') else self.target
            vm._status = 'Falha no teste'
            vm.changed.emit()
        self.detailsRequested.emit()
        if self._closing: self.readyToClose.emit()

    @Slot()
    def cancel(self) -> None:
        if self._service and self._busy:
            self._service.cancel()
            self._status = 'Cancelando… aguardando o driver liberar a operação.'
            self.changed.emit()

    @Slot(result=bool)
    def requestClose(self) -> bool:
        if not self._busy: return True
        self._closing = True
        self.cancel()
        return False

    def shutdown(self) -> None:
        self.cancel()
        self._pool.waitForDone()
        self.source._password = self.target._password = None
        if self._temp: self._temp.cleanup()
