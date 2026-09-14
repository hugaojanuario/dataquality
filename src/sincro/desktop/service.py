"""Worker-side adapter to existing domain services. No Qt or UI objects here."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Callable, Iterator
import shutil

from sincro.audit.checks import compare
from sincro.audit.cli import read_connection
from sincro.audit.connectors import Cancelled, JDBCConnector
from sincro.audit.domain import AuditRun, CaptureOptions, ConnectionProfile, Manifest, Snapshot
from sincro.audit.mapping import suggest, validate_manifest
from sincro.audit.orchestration import Project, Workflow
from sincro.audit.storage import load, save


class UserError(Exception):
    """Static, actionable UI messages only; never interpolate driver input."""


@dataclass
class Request:
    action: str
    directory: Path
    profiles: dict[str, ConnectionProfile] = field(default_factory=dict)
    passwords: dict[str, str | None] = field(default_factory=dict, repr=False)
    options: CaptureOptions = field(default_factory=CaptureOptions)
    secret: str | None = field(default=None, repr=False)
    manifest: Manifest | None = None
    discovery: dict[str, Snapshot] = field(default_factory=dict)
    file: str = ''


@dataclass
class Result:
    action: str
    message: str = 'Operação concluída.'
    snapshots: dict[str, Snapshot] = field(default_factory=dict)
    discovery: dict[str, Snapshot] = field(default_factory=dict)
    manifest: Manifest | None = None
    project: Project | None = None
    run: AuditRun | None = None
    report_path: str = ''
    connection: ConnectionProfile | None = None


class AuditService:
    def __init__(self, connector_factory=JDBCConnector) -> None:
        self.connector_factory = connector_factory
        self.cancelled = Event()
        self._lock = Lock()
        self._connector = None

    def cancel(self) -> None:
        self.cancelled.set()
        # Statement.cancel can block in a JDBC driver; never call it on the UI thread.
        with self._lock:
            connector = self._connector
        if connector is not None and hasattr(connector, 'cancel'):
            Thread(target=connector.cancel, daemon=True).start()

    def checkpoint(self) -> None:
        if self.cancelled.is_set():
            raise Cancelled()

    @contextmanager
    def connection(self, request: Request, side: str) -> Iterator[JDBCConnector]:
        self.checkpoint()
        connector = self.connector_factory(request.profiles[side], request.passwords.get(side), self.cancelled)
        with self._lock:
            self._connector = connector
        try:
            self.checkpoint()
            yield connector
        finally:
            connector.close()
            with self._lock:
                self._connector = None

    def read_project(self, directory: Path, action: str, *, include_run: bool = True) -> Result:
        result = Result(action)
        if not (directory / 'project.json').exists():
            return result
        result.project = load(directory / 'project.json', Project)
        for role in ('source', 'baseline', 'target'):
            if (directory / f'{role}.json').exists():
                result.snapshots[role] = load(directory / f'{role}.json')
        for side in ('source', 'target'):
            if (directory / f'discovery-{side}.json').exists():
                result.discovery[side] = load(directory / f'discovery-{side}.json')
        if (directory / 'mapping.json').exists():
            result.manifest = load(directory / 'mapping.json', Manifest)
        if include_run and len(result.snapshots) == 3 and result.manifest is not None:
            result.run = compare(result.snapshots['source'], result.snapshots['baseline'],
                                 result.snapshots['target'], result.manifest, source_dir=directory,
                                 target_dir=directory, cancel=self.cancelled)
            if (directory / 'report.html').exists():
                result.report_path = str(directory / 'report.html')
        return result

    def execute(self, request: Request, progress: Callable[[str], None]) -> Result:
        self.checkpoint()
        action, directory = request.action, request.directory
        if action.startswith('test_'):
            with self.connection(request, action[5:]):
                return Result(action, 'Conexão estabelecida. Descubra as tabelas para verificar o catálogo.')
        if action.startswith('import_'):
            return Result(action, 'Perfil YAML carregado. Senha obtida apenas da variável de ambiente.',
                          connection=read_connection(request.file))
        if action == 'export':
            shutil.copyfile(directory / 'report.html', request.file)
            return Result(action, 'Relatório HTML exportado.')
        if action == 'load':
            return self.read_project(directory, action)
        if action == 'demo':
            from .demo import create_demo
            create_demo(directory, progress, self.cancelled)
            return self.read_project(directory, action)
        workflow = Workflow(directory)
        if action == 'discover':
            result = Result(action, project=workflow.project)
            for side in ('source', 'target'):
                progress('Descobrindo ' + ('origem' if side == 'source' else 'destino') + '…')
                with self.connection(request, side) as connector:
                    snapshot = Snapshot(workflow.project.run_id, side, connector.engine,
                                        tables=connector.discover(request.options))
                    save(directory / f'discovery-{side}.json', snapshot)
                    result.discovery[side] = snapshot
            return result
        if action == 'suggest':
            if request.manifest and request.manifest.mappings:
                raise UserError('Já existe uma revisão. Edite os mapeamentos para preservar suas decisões.')
            source = request.discovery.get('source')
            target = request.discovery.get('target') or request.discovery.get('baseline')
            if source is None or target is None:
                raise UserError('Descubra os dois bancos ou carregue as capturas antes de gerar sugestões.')
            manifest = suggest(source, target)
            save(directory / 'mapping.json', manifest)
            return Result(action, 'Sugestões geradas e salvas. Revise e confirme cada tabela.', manifest=manifest)
        if action == 'save_mapping':
            if request.manifest is None:
                raise UserError('Gere sugestões antes de salvar o mapeamento.')
            validate_manifest(request.manifest)
            save(directory / 'mapping.json', request.manifest)
            return Result(action, 'Mapeamento revisado salvo.', manifest=request.manifest)
        if action in ('source', 'baseline', 'target'):
            options = deepcopy(request.options)
            if not options.quiescent:
                raise UserError('Suspenda as escritas e confirme essa condição na tela de validação.')
            if request.manifest is not None:
                validate_manifest(request.manifest)
                save(directory / 'mapping.json', request.manifest)
                for mapping in request.manifest.mappings:
                    table = mapping.source if action == 'source' else mapping.target
                    keys = mapping.source_key if action == 'source' else mapping.target_key
                    if not mapping.ignored and table and keys:
                        options.keys[table] = keys
            with self.connection(request, 'source' if action == 'source' else 'target') as connector:
                snapshot = workflow.capture(action, connector, options=options, secret=request.secret,
                                            progress=progress, cancel=self.cancelled)
            self.checkpoint()
            if not snapshot.complete:
                result = self.read_project(directory, action, include_run=False)
                result.message = 'Captura incompleta. Consulte os detalhes e refaça a etapa; nenhuma aprovação emitida.'
                return result
            if action != 'target':
                result = self.read_project(directory, action, include_run=False)
                result.message = 'Captura concluída. Continue para a próxima etapa.'
                return result
        if action in ('target', 'report'):
            progress('Comparando snapshots e gerando relatório…')
            run, path = workflow.report(cancel=self.cancelled)
            result = self.read_project(directory, action, include_run=False)
            result.run, result.report_path = run, str(path)
            return result
        raise UserError('Operação não disponível.')
