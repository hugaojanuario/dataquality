from threading import Event
from unittest.mock import Mock

import pytest

from dataqualy.audit.connectors import AuditError, Cancelled, JDBCConnector
from dataqualy.audit.domain import CaptureOptions, Column, ConnectionProfile, ForeignKey, Index, PrimaryKey, Table
from dataqualy.audit.engines import ENGINES, compatible, get_engine, jdbc_url
from dataqualy.audit.evidence import Hasher


@pytest.mark.parametrize('engine,expected', [
    ('firebird', 'jdbc:firebirdsql://localhost:3050/db'),
    ('postgresql', 'jdbc:postgresql://localhost:5432/db'),
    ('mysql', 'jdbc:mysql://localhost:3306/db'),
    ('sqlserver', 'jdbc:sqlserver://localhost:1433;databaseName=db'),
])
def test_catalog_urls_and_quote(engine, expected):
    assert jdbc_url({'engine': engine, 'database': 'db'}) == expected
    e = get_engine(engine)
    assert e.driver
    q = e.quote
    assert e.identifier(f'a{q}b') == f'{q}a{q}{q}b{q}'
    assert 'COUNT(*)' in e.count_sql(Table('items', 'public', 'db'))
    assert 'GROUP BY' in e.duplicates_sql(Table('items'), ['a', 'b'])
    assert 'IS NOT NULL' in e.duplicates_sql(Table('items'), ['a'], exclude_nulls=True)


@pytest.mark.parametrize('config', [
    {'engine': 'oracle', 'database': 'db'},
    {'engine': 'postgresql', 'database': 'db?password=secret'},
    {'engine': 'sqlserver', 'database': 'db;password=secret'},
    {'engine': 'mysql', 'database': 'db', 'host': 'user:secret@host'},
    {'engine': 'firebird', 'database': 'db', 'port': 99999},
])
def test_reject_unknown_engine_and_credential_url(config):
    with pytest.raises(ValueError) as exc:
        jdbc_url(config)
    assert 'secret' not in str(exc.value)


def make_connector(engine):
    connector = JDBCConnector.__new__(JDBCConnector)
    connector.engine, connector.dialect = engine, get_engine(engine)
    connector.cancel_event, connector.statement = Event(), None
    connector.connection = Mock()
    connector.connection.getCatalog.return_value = None
    connector.connection.getMetaData.return_value.getSearchStringEscape.return_value = '\\'
    return connector


@pytest.mark.parametrize('engine', ENGINES)
def test_discovery_metadata_including_composite_keys_and_system_filter(engine):
    connector = make_connector(engine)
    calls = []
    def metadata(method, *args):
        calls.append((method, args))
        if method == 'getTables':
            return [{'TABLE_NAME': 'A_%', 'TABLE_SCHEM': '', 'TABLE_CAT': ''}, {'TABLE_NAME': 'internal', 'TABLE_SCHEM': 'sys', 'TABLE_CAT': ''}]
        if method == 'getColumns':
            return [{'TABLE_NAME': 'A_%', 'ORDINAL_POSITION': str(i), 'COLUMN_NAME': name, 'DATA_TYPE': '4', 'TYPE_NAME': 'INTEGER', 'NULLABLE': '0', 'COLUMN_SIZE': '10', 'DECIMAL_DIGITS': '0'} for i, name in enumerate(['ID', 'SEQ'], 1)]
        if method == 'getPrimaryKeys':
            return [{'KEY_SEQ': '2', 'COLUMN_NAME': 'SEQ', 'PK_NAME': 'PK'}, {'KEY_SEQ': '1', 'COLUMN_NAME': 'ID', 'PK_NAME': 'PK'}]
        if method == 'getImportedKeys':
            return [{'FK_NAME': 'FK', 'KEY_SEQ': '1', 'PKTABLE_NAME': 'PARENT', 'PKTABLE_SCHEM': '', 'PKTABLE_CAT': '', 'FKCOLUMN_NAME': 'ID', 'PKCOLUMN_NAME': 'ID'}]
        if method == 'getIndexInfo':
            return [{'INDEX_NAME': 'IX', 'ORDINAL_POSITION': '1', 'COLUMN_NAME': 'ID', 'NON_UNIQUE': 'false', 'FILTER_CONDITION': None}]
        raise AssertionError(method)
    connector._metadata = metadata
    tables = connector.discover(CaptureOptions())
    assert len(tables) == 1
    assert tables[0].primary_key.columns == ['ID', 'SEQ']
    assert tables[0].foreign_keys[0].target_table == Table('PARENT').id
    assert tables[0].indexes[0].unique
    assert next(args for method, args in calls if method == 'getColumns')[2] == 'A\\_\\%'


@pytest.mark.parametrize('engine', ENGINES)
def test_profile_uses_aggregates_and_quoted_identifiers(engine):
    c = make_connector(engine)
    parent = Table('parent', columns=[Column('ID', 'int', 4, False, 10)])
    table = Table('items', columns=[Column('ID', 'int', 4, False, 10)], primary_key=PrimaryKey(['ID']), foreign_keys=[ForeignKey('FK', ['ID'], parent.id, ['ID'])], indexes=[Index('IX', ['ID'], True)])
    c.tables = {parent.id: parent, table.id: table}
    sqls = []
    def aggregate(sql, options):
        sqls.append(sql)
        if 'MIN(' in sql:
            return ['0', '2', '1', '2']
        if sql == c.dialect.count_sql(table):
            return ['2']
        return ['0']
    c._aggregate = aggregate
    profile = c.profile(table, CaptureOptions(), Hasher('synthetic-key-for-test-only-123456789').token)
    assert profile.count == 2 and profile.duplicate_keys == 0
    assert profile.orphans == {'FK': 0}
    assert profile.columns['ID'].minimum != '1'
    assert any('NOT EXISTS' in sql for sql in sqls)
    assert any('COUNT(DISTINCT' in sql for sql in sqls)
    assert all('SELECT *' not in sql for sql in sqls)


def test_metadata_and_query_failures_are_redacted():
    c = make_connector('firebird')
    c._metadata = Mock(side_effect=RuntimeError('password=VERY_SECRET'))
    with pytest.raises(AuditError) as exc:
        c.discover(CaptureOptions())
    assert 'VERY_SECRET' not in str(exc.value)
    c.cancel_event.set()
    with pytest.raises(Cancelled):
        c.checkpoint()


def test_jdbc_connection_error_redacts_secret(tmp_path, caplog, capsys):
    with pytest.raises(AuditError) as exc:
        JDBCConnector(ConnectionProfile('firebird', 'db', 'user', str(tmp_path / 'missing.jar')), password='VERY_SECRET')
    assert 'VERY_SECRET' not in str(exc.value) + caplog.text + capsys.readouterr().out


def test_resultsets_and_statements_close_on_error():
    from contextlib import contextmanager
    c = make_connector('postgresql')
    statement = c.connection.createStatement.return_value
    with pytest.raises(RuntimeError):
        with contextmanager(c._query)('SELECT x', CaptureOptions()) as rs:
            raise RuntimeError()
    rs.close.assert_called_once()
    statement.close.assert_called_once()
    statement.setFetchSize.assert_called_once_with(500)
    statement.setQueryTimeout.assert_called_once_with(60)


@pytest.mark.parametrize('source_engine', ENGINES)
@pytest.mark.parametrize('target_engine', ENGINES)
def test_cross_engine_type_matrix(source_engine, target_engine):
    assert compatible(source_engine, target_engine, Column('x', 'decimal', 3, size=10, scale=2), Column('x', 'numeric', 2, size=12, scale=3)) is True
    assert compatible(source_engine, target_engine, Column('x', 'decimal', 3, size=10, scale=2), Column('x', 'numeric', 2, size=10, scale=3)) is False
    assert compatible(source_engine, target_engine, Column('x', 'varchar', 12, size=100), Column('x', 'varchar', 12, size=10)) is False
    assert compatible(source_engine, target_engine, Column('x', 'text', 12), Column('x', 'text', 12)) is None
    assert compatible(source_engine, target_engine, Column('x', 'float', 6), Column('x', 'double', 8)) is None


def test_system_catalog_exclusions():
    assert get_engine('firebird').is_system('', 'RDB$RELATIONS')
    assert get_engine('postgresql').is_system('pg_toast', 'internal')
    assert get_engine('mysql').is_system('', 'user', 'mysql')
    assert get_engine('sqlserver').is_system('sys', 'tables')
