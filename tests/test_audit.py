from copy import deepcopy
from dataclasses import asdict
import json
from threading import Event

import pytest

from dataqualy.audit.checks import compare
from dataqualy.audit.domain import CaptureOptions, Column, ColumnMapping, ConnectionProfile, ForeignKey, Index, Manifest, PrimaryKey, Snapshot, Table, TableMapping
from dataqualy.audit.evidence import Hasher, canonical
from dataqualy.audit.inventory import capture
from dataqualy.audit.mapping import suggest, validate_manifest
from dataqualy.audit.orchestration import Workflow
from dataqualy.audit.reporting import write_report
from dataqualy.audit.storage import decode, load, save
from dataqualy.audit.synthetic import MemoryConnector, demo

SECRET = 'synthetic-key-for-tests-only-0123456789'


@pytest.fixture
def fixtures():
    table = Table('ITEMS', columns=[Column('ID', 'INTEGER', 4, False, 10), Column('VALUE', 'VARCHAR', 12, True, 80)], primary_key=PrimaryKey(['ID']))
    return [table], {table.id: [{'ID': 1, 'VALUE': 'PRIVATE_VALUE_A'}, {'ID': 2, 'VALUE': 'PRIVATE_VALUE_B'}]}


def capture_three(tmp_path, fixtures, *, target_data=None, options=None):
    tables, data = fixtures
    options = options or CaptureOptions('exhaustive', quiescent=True, batch_size=1)
    source = capture(MemoryConnector('firebird', tables, data), run_id='test', role='source', path=tmp_path / 'source.json', options=options, secret=SECRET)
    baseline = capture(MemoryConnector('postgresql', tables, {t.id: [] for t in tables}), run_id='test', role='baseline', path=tmp_path / 'baseline.json', options=options, secret=SECRET)
    target = capture(MemoryConnector('postgresql', tables, target_data if target_data is not None else data), run_id='test', role='target', path=tmp_path / 'target.json', options=options, secret=SECRET)
    manifest = suggest(source, target)
    for mapping in manifest.mappings:
        mapping.confirmed = True
    return source, baseline, target, manifest


def check(tmp_path, snapshots):
    return compare(*snapshots, source_dir=tmp_path, target_dir=tmp_path)


def test_vertical_flow_and_privacy(tmp_path, fixtures):
    snapshots = capture_three(tmp_path, fixtures)
    run = check(tmp_path, snapshots)
    assert run.status == run.quality == 'passed'
    assert run.table_coverage == run.column_coverage == 100
    path = write_report(run, tmp_path / 'report.html')
    assert 'DataQuality' in path.read_text()
    assert load(tmp_path / 'source.json') == snapshots[0]
    for path in tmp_path.iterdir():
        content = path.read_bytes()
        assert SECRET.encode() not in content
        assert b'PRIVATE_VALUE' not in content
    assert 'password' not in asdict(ConnectionProfile('firebird', 'db', 'user'))


@pytest.mark.parametrize('change,expected', [('unmapped', 'inconclusive'), ('unconfirmed', 'inconclusive'), ('missing_table', 'failed'), ('missing_column', 'failed'), ('empty_source', 'inconclusive'), ('bad_run', 'error'), ('incomplete', 'error'), ('missing_profile', 'error'), ('no_quiescence', 'inconclusive'), ('different_engine', 'error'), ('custom', 'inconclusive'), ('transformation', 'inconclusive'), ('bad_key', 'inconclusive')])
def test_no_silent_approval(tmp_path, fixtures, change, expected):
    s, b, t, m = capture_three(tmp_path, fixtures)
    if change == 'unmapped': m.mappings.clear()
    if change == 'unconfirmed': m.mappings[0].confirmed = False
    if change == 'missing_table': m.mappings[0].target = 'absent'
    if change == 'missing_column': m.mappings[0].columns[1].target = 'absent'
    if change == 'empty_source':
        s.tables.clear(); s.profiles.clear(); m.mappings.clear()
    if change == 'bad_run': t.run_id = 'other'
    if change == 'incomplete': t.complete = False
    if change == 'missing_profile': t.profiles.clear()
    if change == 'no_quiescence': t.options.quiescent = False
    if change == 'different_engine': t.engine = 'mysql'
    if change == 'custom': m.mappings[0].expected_filter = 'declared only'
    if change == 'transformation': m.mappings[0].columns[1].transformation = 'uppercase'
    if change == 'bad_key': m.mappings[0].source_key = ['VALUE']; m.mappings[0].target_key = ['VALUE']
    assert check(tmp_path, (s, b, t, m)).status == expected


def test_missing_extra_and_value_differences(tmp_path, fixtures):
    table = fixtures[0][0]
    target = {table.id: [{'ID': 1, 'VALUE': 'changed'}, {'ID': 3, 'VALUE': 'extra'}]}
    run = check(tmp_path, capture_three(tmp_path, fixtures, target_data=target))
    findings = {f.check: f for f in run.findings}
    assert run.status == 'failed'
    assert findings['missing:VALUE'].metrics['violations'] == 1
    assert findings['extra:VALUE'].metrics['violations'] == 1
    assert findings['values:VALUE'].metrics['violations'] == 1


def test_duplicate_keys_do_not_fingerprint(tmp_path, fixtures):
    tables, data = fixtures
    target = deepcopy(data)
    target[tables[0].id][1]['ID'] = 1
    snapshots = capture_three(tmp_path, fixtures, target_data=target)
    run = check(tmp_path, snapshots)
    assert run.status == 'failed'
    assert any(f.check == 'target_duplicate_keys' and f.status == 'failed' for f in run.findings)
    assert not snapshots[2].profiles[tables[0].id].evidence_columns


def test_partial_failure_is_saved_and_redacted(tmp_path, fixtures):
    class Broken(MemoryConnector):
        def profile(self, *args):
            raise RuntimeError('password=secret PRIVATE_VALUE_A')
    tables, data = fixtures
    snapshot = capture(Broken('firebird', tables, data), run_id='r', role='source', path=tmp_path / 'failed.json')
    assert not snapshot.complete
    assert snapshot.findings[0].status == 'error'
    assert 'secret' not in (tmp_path / 'failed.json').read_text()


def test_discovery_failure_not_empty_success(tmp_path):
    class Broken:
        engine = 'firebird'
        def discover(self, options):
            raise RuntimeError('secret')
    snapshot = capture(Broken(), run_id='r', role='source', path=tmp_path / 'failed.json')
    assert not snapshot.complete
    assert snapshot.findings[0].status == 'error'


def test_cancelled_capture_can_never_approve(tmp_path, fixtures):
    event = Event(); event.set()
    tables, data = fixtures
    snapshot = capture(MemoryConnector('firebird', tables, data), run_id='r', role='source', path=tmp_path / 'cancel.json', cancel=event)
    assert not snapshot.complete
    assert snapshot.findings[0].status == 'inconclusive'


def test_tampered_evidence(tmp_path, fixtures):
    snapshots = capture_three(tmp_path, fixtures)
    (tmp_path / snapshots[2].evidence_file).write_bytes(b'corrupt')
    assert check(tmp_path, snapshots).status == 'error'


def test_empty_fingerprint_store_does_not_prove_equality(tmp_path, fixtures):
    import sqlite3
    from dataqualy.audit.evidence import checksum
    snapshots = capture_three(tmp_path, fixtures)
    for snapshot in (snapshots[0], snapshots[2]):
        path = tmp_path / snapshot.evidence_file
        with sqlite3.connect(path) as db:
            db.execute('DELETE FROM cells')
        snapshot.evidence_sha256 = checksum(path)
    assert check(tmp_path, snapshots).status == 'error'


def test_different_destination_rejected(tmp_path, fixtures):
    snapshots = capture_three(tmp_path, fixtures)
    snapshots[2].connection_id = 'another-database'
    assert check(tmp_path, snapshots).status == 'error'


def test_comparison_cancellation(tmp_path, fixtures):
    snapshots = capture_three(tmp_path, fixtures)
    cancel = Event(); cancel.set()
    run = compare(*snapshots, source_dir=tmp_path, target_dir=tmp_path, cancel=cancel)
    assert run.status == 'inconclusive'
    assert any(f.check == 'comparison_cancelled' for f in run.findings)


def test_different_hmac_key_does_not_approve(tmp_path, fixtures):
    snapshots = capture_three(tmp_path, fixtures)
    snapshots[2].key_id = 'different-key'
    assert check(tmp_path, snapshots).status == 'inconclusive'


def test_no_secret_exhaustive_is_inconclusive(tmp_path, fixtures):
    tables, data = fixtures
    source = capture(MemoryConnector('firebird', tables, data), run_id='test', role='source', path=tmp_path / 's.json', options=CaptureOptions('exhaustive', quiescent=True))
    assert source.complete and not source.evidence_file


def test_empty_migrated_table_is_provable(tmp_path, fixtures):
    fixtures[1][fixtures[0][0].id] = []
    assert check(tmp_path, capture_three(tmp_path, fixtures)).status == 'passed'


@pytest.mark.parametrize('profile', ['fast', 'balanced'])
def test_aggregate_profiles_do_not_prove_row_equality(tmp_path, fixtures, profile):
    snapshots = capture_three(tmp_path, fixtures, options=CaptureOptions(profile, quiescent=True))
    assert check(tmp_path, snapshots).status == 'inconclusive'


def test_justified_exclusions_and_column_coverage(tmp_path, fixtures):
    tables, data = fixtures
    extra = Table('EXCLUDED', columns=[Column('ID', 'int', 4, size=10)])
    snapshots = capture_three(tmp_path, fixtures)
    s, b, t, m = snapshots
    s.tables.append(extra)
    s.profiles[extra.id] = deepcopy(next(iter(s.profiles.values())))
    assert check(tmp_path, snapshots).status == 'inconclusive'
    m.mappings.append(TableMapping(extra.id, ignored=True, justification='Synthetic scope exclusion', confirmed=True))
    run = check(tmp_path, snapshots)
    assert run.status == 'passed'
    assert run.excluded_tables == 1
    m.mappings[0].columns.pop()
    assert check(tmp_path, snapshots).column_coverage < 100
    assert check(tmp_path, snapshots).status == 'inconclusive'


def test_manifest_validation(tmp_path, fixtures):
    m = capture_three(tmp_path, fixtures)[3]
    m.mappings[0].ignored = True
    with pytest.raises(ValueError, match='justificativa'):
        validate_manifest(m)
    m.mappings[0].justification = 'test'
    validate_manifest(m)
    m.mappings.append(deepcopy(m.mappings[0]))
    with pytest.raises(ValueError, match='duplicada'):
        validate_manifest(m)


def test_ambiguous_suggestions_require_manual_selection():
    s = Snapshot('r', 'source', 'firebird', tables=[Table('ITEMS')])
    t = Snapshot('r', 'baseline', 'postgresql', tables=[Table('items', 'a'), Table('items', 'b')])
    mapping = suggest(s, t).mappings[0]
    assert not mapping.target and not mapping.confirmed
    assert 'Ambíguo' in mapping.reason


def test_normalized_names_and_composite_keys():
    s = Snapshot('r', 'source', 'firebird', tables=[Table('Order-Items', columns=[Column('ORDER_ID', 'int', 4), Column('ITEM_ID', 'int', 4)], primary_key=PrimaryKey(['ORDER_ID', 'ITEM_ID']))])
    t = Snapshot('r', 'target', 'postgresql', tables=[Table('order_items', columns=[Column('order_id', 'int', 4), Column('item_id', 'int', 4)])])
    m = suggest(s, t).mappings[0]
    assert m.confidence == .75
    assert m.target_key == ['order_id', 'item_id']


def test_composite_key_evidence(tmp_path, fixtures):
    fixtures[0][0].primary_key.columns = ['ID', 'VALUE']
    assert check(tmp_path, capture_three(tmp_path, fixtures)).status == 'passed'


def test_null_key_and_orphans(tmp_path, fixtures):
    tables, data = fixtures
    child = Table('CHILD', columns=[Column('ID', 'int', 4, False, 10), Column('PARENT', 'int', 4, True, 10)], primary_key=PrimaryKey(['ID']), foreign_keys=[ForeignKey('fk', ['PARENT'], tables[0].id, ['ID'])])
    tables.append(child)
    data[child.id] = [{'ID': 1, 'PARENT': 999}]
    run = check(tmp_path, capture_three(tmp_path, fixtures))
    assert run.status == 'failed'
    assert any(f.check == 'target_fk:fk' and f.status == 'failed' for f in run.findings)


def test_uniqueness_preservation(tmp_path, fixtures):
    tables, data = fixtures
    tables[0].indexes = [Index('unique_value', ['VALUE'], True)]
    snapshots = capture_three(tmp_path, fixtures)
    assert check(tmp_path, snapshots).status == 'passed'
    snapshots[2].tables[0].indexes.clear()
    assert check(tmp_path, snapshots).status == 'inconclusive'


def test_baseline_must_be_empty(tmp_path, fixtures):
    snapshots = capture_three(tmp_path, fixtures)
    next(iter(snapshots[1].profiles.values())).count = 1
    assert check(tmp_path, snapshots).status == 'failed'


def test_strict_versioned_storage(tmp_path):
    path = tmp_path / 'snapshot.json'
    save(path, Snapshot('r', 'source', 'firebird'))
    assert load(path).format_version == 1
    data = json.loads(path.read_text())
    data['format_version'] = 99
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='versão'):
        load(path)
    with pytest.raises(ValueError):
        decode(ConnectionProfile, {'engine': 'firebird', 'database': 'x', 'user': 'x', 'password': 'secret'})


def test_canonical_types_and_hash_key():
    number, text = Column('n', 'NUMERIC', 2), Column('s', 'VARCHAR', 12)
    assert canonical('1.00', number) == canonical(1, number)
    assert canonical('-0.00', number) == canonical(0, number)
    assert canonical('1', text) != canonical(1, number)
    assert Hasher(SECRET).token('1.00', number) == Hasher(SECRET).token(1, number)
    for column, value in [(Column('f', 'FLOAT', 6), 1.0), (Column('t', 'TIMESTAMP', 93), '2026-01-01'), (number, 'NaN'), (text, 'x' * 65537)]:
        with pytest.raises(ValueError):
            canonical(value, column)


def test_demo_and_resume(tmp_path):
    run, path = demo(tmp_path)
    assert run.status == 'passed' and path.exists()
    workflow = Workflow(tmp_path)
    assert workflow.project.run_id == run.run_id
    assert workflow.report()[0].status == 'passed'
    with pytest.raises(ValueError, match='já existe'):
        workflow.suggest()
    with pytest.raises(ValueError, match='Baseline já existe'):
        workflow.capture('source', None)


def test_atomic_replace_failure_preserves_old_file(tmp_path, monkeypatch):
    path = tmp_path / 'x.json'
    path.write_text('old')
    def fail(*args): raise OSError('disk full')
    monkeypatch.setattr('dataqualy.audit.storage.os.replace', fail)
    with pytest.raises(OSError):
        save(path, Manifest())
    assert path.read_text() == 'old'
    assert list(tmp_path.iterdir()) == [path]
