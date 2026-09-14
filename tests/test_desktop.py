"""GUI adapter regression tests; synthetic domain data only, no database required."""
import json
import os
from dataclasses import asdict
from pathlib import Path
from threading import Event, get_ident
import time

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QT_QUICK_BACKEND', 'software')

import pytest
from PySide6.QtCore import QObject, QMetaObject, QSettings, QTimer, Qt, qInstallMessageHandler
from PySide6.QtGui import QFont, QGuiApplication
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtTest import QTest
import shiboken6

from sincro.desktop.app import create_engine
from sincro.desktop.service import AuditService, Request, Result
from sincro.desktop.updater import UpdateInfo
from sincro.desktop.viewmodel import AppViewModel, ConnectionViewModel, default_project_directory, migrate_settings, safe_error
from sincro.audit.domain import CaptureOptions, ConnectionProfile, Manifest
from sincro.audit.storage import load
from sincro.audit.synthetic import MemoryConnector
from sincro.audit.connectors import AuditError, Cancelled


def test_connection_prerequisite_errors_are_actionable():
    message = 'Selecione um JAR JDBC existente.'
    summary, details = safe_error(AuditError(message), 'test_target')
    assert summary == message
    assert 'test_target' in details
    assert 'cancelada' in safe_error(Cancelled(), 'test_target')[0]


@pytest.fixture(scope='module')
def qt_app():
    QQuickStyle.setStyle('Basic')
    app = QGuiApplication.instance() or QGuiApplication([])
    app.setFont(QFont('Helvetica Neue' if os.sys.platform == 'darwin' else 'Segoe UI', 11))
    yield app


@pytest.fixture
def model(qt_app, tmp_path):
    vm = AppViewModel(directory=str(tmp_path / 'project'), settings=QSettings(str(tmp_path / 'preferences.ini'), QSettings.Format.IniFormat))
    yield vm
    vm.shutdown()


def wait_for(qt_app, condition, timeout=8):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        qt_app.processEvents()
        QTest.qWait(5)
    assert condition(), 'GUI operation did not finish'


def test_password_is_write_only_and_never_serialized(model):
    secret = 'private-password-DO-NOT-PERSIST'
    model.source.setSecret(secret)
    assert secret not in json.dumps(model.state)
    assert secret not in json.dumps(model.source.fields)
    assert 'password' not in model.source.fields
    assert model.source.metaObject().indexOfProperty('password') == -1
    for exc in (RuntimeError(secret), ValueError(secret), OSError(secret)):
        assert secret not in ' '.join(safe_error(exc, 'source'))
    assert secret not in model._settings.allKeys()


def test_engine_defaults_and_invalid_port(model):
    model.source.setField('engine', 'mysql')
    assert model.source.fields['port'] == '3306'
    assert model.source.fields['driver'] == 'com.mysql.cj.jdbc.Driver'
    model.source.setField('database', 'synthetic')
    model.source.setField('port', '')
    assert model.source.fields['port'] == ''
    with pytest.raises(ValueError):  # UserError handled below separately
        int(model.source.fields['port'])
    from sincro.desktop.service import UserError
    with pytest.raises(UserError):
        model.source.profile()


def test_default_project_directory_does_not_depend_on_process_working_directory(qt_app, tmp_path, monkeypatch):
    monkeypatch.chdir('/')
    directory = default_project_directory()
    assert directory.is_absolute()
    assert directory.name == 'audit-project'
    assert directory != Path('/reports/audit-project')
    vm = AppViewModel(settings=QSettings(str(tmp_path / 'preferences.ini'), QSettings.Format.IniFormat))
    try:
        assert vm._directory == directory
    finally:
        vm.shutdown()


def test_renamed_application_migrates_saved_settings(tmp_path):
    legacy = QSettings(str(tmp_path / 'legacy.ini'), QSettings.Format.IniFormat)
    current = QSettings(str(tmp_path / 'current.ini'), QSettings.Format.IniFormat)
    legacy.setValue('lastProject', '/projects/existing')
    legacy.setValue('dark', True)
    legacy.sync()

    migrate_settings(current, legacy)

    assert current.value('lastProject') == '/projects/existing'
    assert current.value('dark', False, type=bool) is True


def test_sidebar_exposes_a_new_release_without_blocking_the_app(qt_app, model):
    info = UpdateInfo('0.5.0', 'v0.5.0', 'Sincro-macOS-arm64.zip',
                      'https://github.com/hugaojanuario/sincro/releases/download/v0.5.0/Sincro-macOS-arm64.zip',
                      'sha256:' + '0' * 64, 1, '')
    model._update_checked(info)
    engine = create_engine(model)
    try:
        window = engine.rootObjects()[0]
        QTest.qWait(30)
        qt_app.processEvents()
        button = window.findChild(QObject, 'updateButton')
        assert button is not None
        assert button.property('visible') is True
        assert button.property('text') == 'Atualizar para v0.5.0'
        assert model.state['currentVersion'] == '0.4.0'
    finally:
        shiboken6.delete(engine)


def test_project_configuration_round_trips_without_password(qt_app, tmp_path):
    project = tmp_path / 'migration-a'
    preferences = tmp_path / 'preferences.ini'
    first = AppViewModel(directory=str(project), settings=QSettings(str(preferences), QSettings.Format.IniFormat))
    try:
        first.execute('load')
        wait_for(qt_app, lambda: not first.state['busy'])
        first.source.setField('host', 'firebird.internal')
        first.source.setField('database', '/data/source.fdb')
        first.source.setField('user', 'audit_source')
        first.source.setField('jar', '/drivers/jaybird.jar')
        first.source.setField('password_env', 'SOURCE_PASSWORD')
        first.target.setField('host', 'postgres.internal')
        first.target.setField('database', 'converted')
        first.target.setField('user', 'audit_target')
        first.target.setField('jar', '/drivers/postgresql.jar')
        first.source.setSecret('never-save-this-password')
        first.configure('name', 'Conversão A')
        first.configure('description', 'Firebird para PostgreSQL')
        first.configure('profile', 'exhaustive')
        first.configure('keyEnv', 'PROJECT_EVIDENCE_KEY')
        first.configure('system', 'true')
        first.configure('quiescent', 'true')
        first.navigate(3)
        document = (project / 'project.json').read_text()
        assert 'never-save-this-password' not in document
    finally:
        first.shutdown()

    resumed = AppViewModel(settings=QSettings(str(preferences), QSettings.Format.IniFormat))
    try:
        resumed.execute('load')
        wait_for(qt_app, lambda: not resumed.state['busy'])
        assert resumed._directory == project.resolve()
        assert resumed.state['projectName'] == 'Conversão A'
        assert resumed.state['description'] == 'Firebird para PostgreSQL'
        assert resumed.state['profile'] == 'exhaustive'
        assert resumed.state['keyEnv'] == 'PROJECT_EVIDENCE_KEY'
        assert resumed.state['includeSystem'] is True
        assert resumed.state['quiescent'] is False
        assert resumed.state['page'] == 3
        assert resumed.source.fields['database'] == '/data/source.fdb'
        assert resumed.source.fields['password_env'] == 'SOURCE_PASSWORD'
        assert resumed.target.fields['database'] == 'converted'
        assert resumed.source._password is None
        assert resumed.state['recentProjects'][0]['current'] is True
    finally:
        resumed.shutdown()


def test_switching_projects_restores_each_context(qt_app, tmp_path):
    first_project = tmp_path / 'migration-a'
    second_project = tmp_path / 'migration-b'
    vm = AppViewModel(directory=str(first_project), settings=QSettings(str(tmp_path / 'preferences.ini'), QSettings.Format.IniFormat))
    try:
        vm.execute('load')
        wait_for(qt_app, lambda: not vm.state['busy'])
        vm.configure('name', 'Conversão A')
        vm.source.setField('database', '/data/a.fdb')

        vm.chooseDirectory(second_project.as_uri())
        wait_for(qt_app, lambda: not vm.state['busy'])
        vm.configure('name', 'Conversão B')
        vm.source.setField('database', '/data/b.fdb')

        vm.openRecentProject(str(first_project.resolve()))
        wait_for(qt_app, lambda: not vm.state['busy'])
        assert vm.state['projectName'] == 'Conversão A'
        assert vm.source.fields['database'] == '/data/a.fdb'

        vm.openRecentProject(str(second_project.resolve()))
        wait_for(qt_app, lambda: not vm.state['busy'])
        assert vm.state['projectName'] == 'Conversão B'
        assert vm.source.fields['database'] == '/data/b.fdb'
    finally:
        vm.shutdown()


def test_worker_is_responsive_queued_and_cancellable(qt_app, model):
    started = Event()
    worker_threads, ui_threads = [], []
    class SlowService(AuditService):
        def execute(self, request, progress):
            worker_threads.append(get_ident())
            started.set()
            self.cancelled.wait(3)
            self.checkpoint()
    model._service_factory = SlowService
    model.changed.connect(lambda: ui_threads.append(get_ident()))
    model.execute('load')
    wait_for(qt_app, started.is_set)
    assert model.state['busy']
    model.navigate(6)
    assert model.state['page'] == 6
    timer_fired = []
    QTimer.singleShot(0, lambda: timer_fired.append(True))
    wait_for(qt_app, lambda: bool(timer_fired))
    model.cancel()
    wait_for(qt_app, lambda: not model.state['busy'])
    assert worker_threads[0] != get_ident()
    assert set(ui_threads) == {get_ident()}
    assert 'cancelada' in model.state['error']


def test_connection_cleanup_even_when_discovery_fails(tmp_path):
    closed = []
    class BrokenConnector:
        engine = 'firebird'
        def __init__(self, *args): pass
        def discover(self, options): raise RuntimeError('hidden password')
        def close(self): closed.append(True)
    request = Request('discover', tmp_path, profiles={'source': ConnectionProfile('firebird', 'synthetic', 'reader')})
    with pytest.raises(RuntimeError):
        AuditService(BrokenConnector).execute(request, lambda _: None)
    assert closed == [True]


def test_demo_runs_domain_and_mapping_review(qt_app, tmp_path):
    vm = AppViewModel(demo=True, settings=QSettings(str(tmp_path / 'prefs.ini'), QSettings.Format.IniFormat))
    try:
        vm.execute('demo')
        wait_for(qt_app, lambda: not vm.state['busy'])
        assert vm.state['hasResult']
        assert vm.state['resultStatus'] == 'failed'
        assert vm.state['failed'] == 1
        assert vm.state['sourceRows'] == '60'
        assert vm.state['tableCoverage'] == '100%'
        assert vm.state['findingRows'][0]['tone'] == 'failed'
        assert 'sincro-demo-' not in json.dumps(vm.state)
        assert vm.state['recentProjects'] == []
        vm.editMapping(0)
        vm.updateMapping('ignored', 'true')
        vm.confirmMapping()
        assert not vm.state['mappingEditor']['confirmed']
        vm.updateMapping('justification', 'Synthetic exclusion for UI test')
        vm.confirmMapping()
        assert vm.state['mappingEditor']['confirmed']
        assert not vm.state['hasResult']
        vm.execute('save_mapping')
        wait_for(qt_app, lambda: not vm.state['busy'])
        assert load(vm._directory / 'mapping.json', Manifest).mappings[0].ignored
        vm.filter('mapping', 'Ignorados')
        assert len(vm.state['mappingRows']) == 1
    finally:
        vm.shutdown()


def test_real_adapter_workflow_with_injected_memory_connector(qt_app, model, monkeypatch):
    from sincro.audit.domain import Column, PrimaryKey, Table
    source = Table('ITEMS', columns=[Column('ID', 'INTEGER', 4, False, 10)], primary_key=PrimaryKey(['ID']))
    target = Table('items', 'public', columns=[Column('id', 'int4', 4, False, 10)], primary_key=PrimaryKey(['id']))
    target_rows = []
    def connector(profile, password, cancel):
        if profile.engine == 'firebird':
            return MemoryConnector('firebird', [source], {source.id: [{'ID': 1}]})
        return MemoryConnector('postgresql', [target], {target.id: list(target_rows)})
    model._service_factory = lambda: AuditService(connector)
    for vm in (model.source, model.target):
        vm.setField('database', 'synthetic')
        vm.setSecret('never-persist-this-secret')
    monkeypatch.setenv('SINCRO_EVIDENCE_KEY', 'synthetic-test-key-' * 3)
    model.configure('profile', 'exhaustive')
    model.configure('quiescent', 'true')
    for action in ('discover', 'suggest', 'source', 'baseline'):
        model.execute(action)
        wait_for(qt_app, lambda: not model.state['busy'])
        assert not model.state['error']
        if action == 'discover':
            assert (model._directory / 'discovery-source.json').exists()
            assert (model._directory / 'discovery-target.json').exists()
        if action == 'suggest':
            assert (model._directory / 'mapping.json').exists()
    model.editMapping(0)
    model.confirmMapping()
    assert model.state['mappingEditor']['confirmed']
    target_rows.append({'id': 1})
    model.execute('target')
    wait_for(qt_app, lambda: not model.state['busy'])
    assert model.state['resultStatus'] == 'passed'
    assert model.state['page'] == 7
    for path in model._directory.glob('*.json'):
        assert 'never-persist-this-secret' not in path.read_text()
    export = model._directory.parent / 'export.html'
    model.exportReport(export.as_uri())
    wait_for(qt_app, lambda: not model.state['busy'])
    assert export.exists()
    model.execute('load')
    wait_for(qt_app, lambda: not model.state['busy'])
    assert model.state['resultStatus'] == 'passed'
    class FailedCapture(AuditService):
        def execute(self, request, progress):
            raise RuntimeError('never-persist-this-secret')
    model._service_factory = FailedCapture
    model.execute('target')
    assert not model.state['hasResult']
    wait_for(qt_app, lambda: not model.state['busy'])
    assert not model.state['hasResult'] and not model.state['hasReport']
    assert 'never-persist-this-secret' not in json.dumps(model.state)


def test_qml_all_pages_themes_minimum_size_and_keyboard(qt_app, tmp_path):
    vm = AppViewModel(demo=True, settings=QSettings(str(tmp_path / 'prefs.ini'), QSettings.Format.IniFormat))
    warnings = []
    previous = qInstallMessageHandler(lambda kind, context, message: warnings.append(message))
    engine = None
    try:
        engine = create_engine(vm)
        window = engine.rootObjects()[0]
        vm.execute('demo')
        wait_for(qt_app, lambda: not vm.state['busy'])
        assert vm.state['hasResult']
        loader = window.findChild(QObject, 'pageLoader')
        for dark in (True, False):
            vm.setDark(dark)
            for width, height in ((1280, 800), (1024, 700)):
                window.setWidth(width)
                window.setHeight(height)
                for page in range(8):
                    vm.navigate(page)
                    QTest.qWait(30)
                    qt_app.processEvents()
                    assert loader.property('item') is not None
                    assert window.width() >= 1024 and window.height() >= 700
        vm.navigate(0)
        QTest.keyClick(window, Qt.Key.Key_Tab)
        assert window.activeFocusItem() is not None
        # Open the actual modal, edit a column and keep keyboard focus through notifications.
        vm.navigate(3)
        vm.editMapping(0)
        qt_app.processEvents()
        dialog = window.findChild(QObject, 'mappingDialog')
        QMetaObject.invokeMethod(dialog, 'open')
        QTest.qWait(30)
        assert dialog.property('visible')
        def find_visual(item, name):
            if item.objectName() == name:
                return item
            for child in item.childItems():
                found = find_visual(child, name)
                if found is not None:
                    return found
            return None
        field = find_visual(window.contentItem(), 'input-Destino de ID')
        assert field is not None
        field.forceActiveFocus()
        QTest.keyClick(window, Qt.Key.Key_End)
        QTest.keyClick(window, Qt.Key.Key_X)
        qt_app.processEvents()
        assert field.property('activeFocus')
        assert vm.state['mappingEditor']['columns'][0]['target'].endswith('x')
        QMetaObject.invokeMethod(dialog, 'close')
        vm.execute('report')
        wait_for(qt_app, lambda: not vm.state['busy'])
        vm.navigate(7)
        vm.showFinding(0)
        QTest.qWait(30)
        assert window.property('detailsOpen')
        vm.setReducedMotion(True)
        assert vm.reducedMotion
    finally:
        if engine is not None: shiboken6.delete(engine)
        vm.shutdown()
        qInstallMessageHandler(previous)
    assert not warnings, '\n'.join(warnings)


def test_project_switcher_opens_from_header(qt_app, model):
    engine = create_engine(model)
    try:
        window = engine.rootObjects()[0]
        model.execute('load')
        wait_for(qt_app, lambda: not model.state['busy'])
        switcher = window.findChild(QObject, 'projectSwitcher')
        menu = window.findChild(QObject, 'projectMenu')
        assert switcher is not None and menu is not None
        assert QMetaObject.invokeMethod(switcher, 'click')
        qt_app.processEvents()
        assert menu.property('visible')
    finally:
        shiboken6.delete(engine)


def test_empty_gui_and_incomplete_capture_remain_honest(qt_app, model):
    from sincro.audit.domain import Finding, Snapshot
    engine = create_engine(model)
    try:
        for page in range(8):
            model.navigate(page)
            QTest.qWait(30)
        assert model.state['tableCoverage'] == '—'
        assert not model.state['hasResult']
        snapshot = Snapshot('synthetic-run', 'source', 'firebird', findings=[Finding('capture', 'error', 'Captura incompleta.')])
        model._done(Result('source', snapshots={'source': snapshot}))
        assert model.state['page'] == 7
        assert not model.state['hasResult']
        assert model.state['findingRows'][0]['tone'] == 'error'
        assert model.state['sourceReady'] is False
    finally:
        shiboken6.delete(engine)


def test_cli_gui_switches_and_screenshot_privacy_gate(monkeypatch):
    from sincro.cli import main
    from sincro.desktop import app
    calls = []
    monkeypatch.setattr(app, 'launch_gui', lambda **kw: calls.append(kw) or 0)
    assert main(['gui', '--demo']) == 0
    assert calls[-1]['demo'] is True
    assert main(['gui', '--screenshots', 'synthetic-output']) == 2
    assert len(calls) == 1
