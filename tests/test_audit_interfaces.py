from dataclasses import asdict
import json
from threading import Event, get_ident

import pytest

from sincro.cli import main
from sincro.audit.cli import read_connection
from sincro.audit.domain import Manifest, TableMapping
from sincro.audit.gui import Worker
from sincro.audit.providers import AIConfig, parse_provider_line, validate_ai_suggestion
from sincro.models import ValidationReport
from datetime import datetime


def test_demo_cli_and_offline_compare(tmp_path):
    assert main(['audit', 'demo', '--project', str(tmp_path)]) == 0
    args = ['audit', 'compare', '--source', str(tmp_path / 'source.json'), '--baseline', str(tmp_path / 'baseline.json'), '--target', str(tmp_path / 'target.json'), '--mapping', str(tmp_path / 'mapping.json'), '--report', str(tmp_path / 'offline.html')]
    assert main(args) == 0
    data = json.loads((tmp_path / 'mapping.json').read_text())
    data['mappings'][0]['confirmed'] = False
    (tmp_path / 'mapping.json').write_text(json.dumps(data))
    assert main(args) == 3


def test_connection_yaml_no_password(tmp_path):
    path = tmp_path / 'profile.yml'
    path.write_text('engine: firebird\ndatabase: test\nuser: test\npassword: SECRET\n')
    with pytest.raises(ValueError) as exc:
        read_connection(path)
    assert 'SECRET' not in str(exc.value)


def test_worker_never_runs_io_on_ui_thread():
    worker = Worker()
    started, release = Event(), Event()
    main_thread = get_ident()
    def action():
        assert get_ident() != main_thread
        started.set()
        release.wait(2)
        return ('message', 'OK')
    assert worker.start(action)
    assert started.wait(1)
    assert worker.busy
    assert worker.start(action) is False
    worker.stop()
    assert worker.cancel.is_set()
    release.set()
    worker.thread.join(2)
    assert worker.events.get_nowait() == ('done', ('message', 'OK'))


def test_worker_redacts_exceptions():
    worker = Worker()
    def action(): raise RuntimeError('SECRET_PASSWORD personal@example.invalid')
    worker.start(action)
    worker.thread.join(2)
    event, message = worker.events.get_nowait()
    assert event == 'error' and 'SECRET_PASSWORD' not in message and '@' not in message


def test_empty_legacy_report_is_not_passed():
    assert not ValidationReport('empty', datetime.now()).passed


def test_ai_default_off_and_cannot_confirm():
    assert AIConfig().enabled is False
    m = Manifest([TableMapping('x', 'y', confirmed=True)])
    result = validate_ai_suggestion(json.dumps(asdict(m)))
    assert not result.mappings[0].confirmed
    assert 'Sugestão' in result.mappings[0].reason
    with pytest.raises(ValueError):
        validate_ai_suggestion('{"approved": true}')
    data = asdict(m)
    data['mappings'][0]['confidence'] = float('nan')
    with pytest.raises(ValueError):
        validate_ai_suggestion(json.dumps(data))


@pytest.mark.parametrize('kind', ['capabilities', 'validate_config', 'start', 'progress', 'table_metrics', 'completed', 'failed', 'cancel', 'cancelled'])
def test_provider_envelope(kind):
    data = {'protocol_version': 1, 'request_id': 'q', 'run_id': 'r', 'type': kind, 'payload': {}}
    assert parse_provider_line(json.dumps(data)).type == kind
    data['protocol_version'] = 99
    with pytest.raises(ValueError):
        parse_provider_line(json.dumps(data))


def test_provider_invalid_or_oversize():
    for line in ('bad SECRET', 'x' * 65537, '{"type":"approve"}'):
        with pytest.raises(ValueError) as exc:
            parse_provider_line(line)
        assert 'SECRET' not in str(exc.value)
