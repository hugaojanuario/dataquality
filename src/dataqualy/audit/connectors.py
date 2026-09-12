"""JDBC metadata discovery; SQL differences stay in engines, not orchestration."""
from collections import defaultdict
from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from threading import Event, Lock
from typing import Protocol
import os

from .domain import Column, ColumnProfile, ConnectionProfile, ForeignKey, Index, PrimaryKey, Table, TableProfile, CaptureOptions
from .engines import family, get_engine, jdbc_url


class AuditError(Exception):
    """Only public, actionable messages may cross the connector boundary."""


class Cancelled(AuditError):
    pass


class Connector(Protocol):
    engine: str

    def discover(self, options: CaptureOptions) -> list[Table]: ...
    def profile(self, table: Table, options: CaptureOptions, token) -> TableProfile: ...
    def rows(self, table: Table, columns: list[Column], options: CaptureOptions) -> Iterator[list[object]]: ...
    def close(self) -> None: ...


_JVM_LOCK = Lock()


class JDBCConnector:
    def __init__(self, profile: ConnectionProfile, password: str | None = None, cancel: Event | None = None):
        self.engine = get_engine(profile.engine).name
        self.dialect = get_engine(self.engine)
        self.cancel_event = cancel or Event()
        self.connection = None
        self.statement = None
        try:
            import jpype
            if not Path(profile.jar).is_file():
                raise AuditError('Selecione um JAR JDBC existente.')
            url = jdbc_url(asdict(profile))
            import hashlib
            self.identity = hashlib.sha256(url.encode('utf-8')).hexdigest()
            secret = password if password is not None else os.environ.get(profile.password_env)
            if secret is None:
                raise AuditError('Defina a variável de senha ou preencha a senha na interface.')
            with _JVM_LOCK:
                jpype.addClassPath(str(Path(profile.jar).resolve()))
                if not jpype.isJVMStarted():
                    jpype.startJVM(convertStrings=True)
            properties = jpype.JClass('java.util.Properties')()
            properties.setProperty('user', profile.user)
            properties.setProperty('password', secret)
            if self.engine == 'mysql':
                properties.setProperty('useCursorFetch', 'true')
                properties.setProperty('useServerPrepStmts', 'true')
            if self.engine == 'sqlserver':
                properties.setProperty('responseBuffering', 'adaptive')
            # Driver.connect supports dynamically loaded JARs and avoids DriverManager classloader issues.
            driver = jpype.JClass(self.dialect.driver)()
            self.connection = driver.connect(url, properties)
            self.connection.setReadOnly(True)
            self.connection.setAutoCommit(False)
        except AuditError:
            self.close()
            raise
        except Exception:
            self.close()
            raise AuditError('Conexão indisponível. Verifique Java, extra jdbc, JAR, endereço, permissões e credenciais.') from None

    def checkpoint(self):
        if self.cancel_event.is_set():
            raise Cancelled('Operação cancelada; captura incompleta.')

    def cancel(self):
        self.cancel_event.set()
        try:
            if self.statement is not None:
                self.statement.cancel()
        except Exception:
            pass  # Cooperative cancellation remains set; this is not an audit result.

    def close(self):
        if self.connection is not None:
            try:
                self.connection.rollback()
            except Exception:
                pass
            try:
                self.connection.close()
            except Exception:
                pass
            self.connection = None

    def _metadata(self, method, *args):
        result = None
        try:
            self.checkpoint()
            result = getattr(self.connection.getMetaData(), method)(*args)
            meta = result.getMetaData()
            labels = [str(meta.getColumnLabel(i)) for i in range(1, meta.getColumnCount() + 1)]
            rows = []
            while result.next():
                self.checkpoint()
                rows.append({name: (None if (v := result.getString(i)) is None else str(v)) for i, name in enumerate(labels, 1)})
            return rows
        finally:
            if result is not None:
                result.close()

    def discover(self, options):
        try:
            catalog = self.connection.getCatalog()
            tables = []
            # TABLE excludes views; SYSTEM TABLE is explicitly opt-in.
            kinds = ['TABLE', 'SYSTEM TABLE'] if options.include_system else ['TABLE']
            for row in self._metadata('getTables', catalog, None, '%', kinds):
                table = Table(row['TABLE_NAME'].rstrip(), row.get('TABLE_SCHEM') or '', row.get('TABLE_CAT') or '')
                if not options.include_system and self.dialect.is_system(table.schema, table.name, table.catalog):
                    continue
                args = (table.catalog or None, table.schema or None, table.name)
                # getColumns takes a pattern; escape literal wildcard characters in names.
                escape = str(self.connection.getMetaData().getSearchStringEscape())
                pattern = table.name.replace(escape, escape + escape) if escape else table.name
                if escape:
                    pattern = pattern.replace('_', escape + '_').replace('%', escape + '%')
                column_rows = self._metadata('getColumns', args[0], args[1], pattern, '%')
                for c in sorted(column_rows, key=lambda c: int(c['ORDINAL_POSITION'])):
                    if c['TABLE_NAME'].rstrip() != table.name:
                        continue
                    table.columns.append(Column(c['COLUMN_NAME'].rstrip(), c['TYPE_NAME'], int(c['DATA_TYPE']), c['NULLABLE'] != '0', int(c.get('COLUMN_SIZE') or 0), int(c.get('DECIMAL_DIGITS') or 0)))
                pk = sorted(self._metadata('getPrimaryKeys', *args), key=lambda c: int(c['KEY_SEQ']))
                table.primary_key = PrimaryKey([c['COLUMN_NAME'].rstrip() for c in pk], (pk[0].get('PK_NAME') or '') if pk else '')
                groups = defaultdict(list)
                for fk in self._metadata('getImportedKeys', *args):
                    if not fk.get('FK_NAME'):
                        raise AuditError('Metadados retornaram FK sem identificador; revise o driver.')
                    groups[fk['FK_NAME']].append(fk)
                for name, members in groups.items():
                    members.sort(key=lambda c: int(c['KEY_SEQ']))
                    first = members[0]
                    parent = Table(first['PKTABLE_NAME'].rstrip(), first.get('PKTABLE_SCHEM') or '', first.get('PKTABLE_CAT') or '')
                    table.foreign_keys.append(ForeignKey(name, [c['FKCOLUMN_NAME'].rstrip() for c in members], parent.id, [c['PKCOLUMN_NAME'].rstrip() for c in members]))
                groups.clear()
                for index in self._metadata('getIndexInfo', *args, False, False):
                    if index.get('INDEX_NAME'):
                        groups[index['INDEX_NAME']].append(index)
                for name, members in groups.items():
                    members.sort(key=lambda c: int(c['ORDINAL_POSITION']))
                    table.indexes.append(Index(name, [c['COLUMN_NAME'].rstrip() for c in members if c.get('COLUMN_NAME')], members[0]['NON_UNIQUE'].lower() in ('false', '0', 'f'), any(c.get('FILTER_CONDITION') or not c.get('COLUMN_NAME') for c in members)))
                if not table.columns:
                    raise AuditError('Tabela sem colunas visíveis; verifique permissões de metadados.')
                tables.append(table)
            self.tables = {t.id: t for t in tables}
            return tables
        except Cancelled:
            raise
        except Exception:
            raise AuditError('Descoberta incompleta. Verifique permissões de catálogo e compatibilidade do driver.') from None

    def _query(self, sql, options):
        result = statement = None
        try:
            self.checkpoint()
            statement = self.connection.createStatement()
            self.statement = statement
            statement.setQueryTimeout(options.timeout_seconds)
            statement.setFetchSize(options.batch_size)
            result = statement.executeQuery(sql)
            yield result
        finally:
            self.statement = None
            if result is not None:
                result.close()
            if statement is not None:
                statement.close()

    def _aggregate(self, sql, options):
        from contextlib import contextmanager
        with contextmanager(self._query)(sql, options) as result:
            if not result.next():
                raise AuditError('Consulta agregada não retornou evidência.')
            return [None if (v := result.getString(i)) is None else str(v) for i in range(1, result.getMetaData().getColumnCount() + 1)]

    def profile(self, table, options, token):
        try:
            q, relation = self.dialect.identifier, self.dialect.table(table)
            profile = TableProfile(int(self._aggregate(self.dialect.count_sql(table), options)[0]))
            for column in table.columns:
                self.checkpoint()
                name = q(column.name)
                supported = family(column) != 'unsupported'
                expr = f'COUNT(*) - COUNT({name})'
                if options.profile != 'fast' and supported:
                    expr += f', COUNT(DISTINCT {name})'
                # Never serialize actual min/max, even for numeric fields.
                bounds = options.profile != 'fast' and family(column) in ('number', 'date') and token is not None
                if bounds:
                    expr += f', MIN({name}), MAX({name})'
                values = self._aggregate(f'SELECT {expr} FROM {relation}', options)
                cp = ColumnProfile(int(values[0]), int(values[1]) if len(values) > 1 else None)
                if bounds:
                    cp.minimum, cp.maximum = (token(v, column) if v is not None else None for v in values[-2:])
                profile.columns[column.name] = cp
            keys = options.keys.get(table.id, table.primary_key.columns)
            if keys:
                if not set(keys) <= {c.name for c in table.columns}:
                    raise AuditError('Chave configurada contém coluna inexistente.')
                profile.duplicate_keys = int(self._aggregate(self.dialect.duplicates_sql(table, keys), options)[0])
                profile.null_keys = int(self._aggregate(f'SELECT COUNT(*) FROM {relation} WHERE ' + ' OR '.join(f'{q(c)} IS NULL' for c in keys), options)[0])
            if options.profile != 'fast':
                for index in table.indexes:
                    if index.unique and index.columns and not index.partial:
                        profile.unique_violations[index.name] = int(self._aggregate(self.dialect.duplicates_sql(table, index.columns, exclude_nulls=True), options)[0])
                for fk in table.foreign_keys:
                    parent = self.tables.get(fk.target_table)
                    if parent is None:
                        continue  # Comparison will explicitly mark missing FK evidence.
                    nonnull = ' AND '.join(f'c.{q(c)} IS NOT NULL' for c in fk.columns)
                    join = ' AND '.join(f'c.{q(c)} = p.{q(p)}' for c, p in zip(fk.columns, fk.target_columns, strict=True))
                    sql = f'SELECT COUNT(*) FROM {relation} c WHERE {nonnull} AND NOT EXISTS (SELECT 1 FROM {self.dialect.table(parent)} p WHERE {join})'
                    profile.orphans[fk.name] = int(self._aggregate(sql, options)[0])
            return profile
        except Cancelled:
            raise
        except Exception:
            raise AuditError('Perfil incompleto. Verifique permissões SELECT, timeout e tipos suportados.') from None

    def rows(self, table, columns, options):
        from contextlib import contextmanager
        sql = f'SELECT {", ".join(self.dialect.identifier(c.name) for c in columns)} FROM {self.dialect.table(table)}'
        try:
            with contextmanager(self._query)(sql, options) as result:
                while result.next():
                    self.checkpoint()
                    values = []
                    for i, column in enumerate(columns, 1):
                        v = result.getBoolean(i) if family(column) == 'boolean' else result.getString(i)
                        values.append(None if result.wasNull() else v)
                    yield values
        except Cancelled:
            raise
        except Exception:
            raise AuditError('Leitura interrompida. Verifique timeout, conexão e tipos suportados.') from None
