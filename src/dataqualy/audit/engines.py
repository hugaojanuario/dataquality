from dataclasses import dataclass


@dataclass(frozen=True)
class Engine:
    name: str
    port: int
    driver: str
    quote: str = '"'

    def identifier(self, name: str) -> str:
        return self.quote + name.replace(self.quote, self.quote * 2) + self.quote

    def table(self, table) -> str:
        parts = [table.schema, table.name]
        if self.name == 'mysql':
            parts = [table.catalog, table.name]
        return '.'.join(self.identifier(p) for p in parts if p)

    def is_system(self, schema: str, name: str, catalog: str = '') -> bool:
        return (schema.lower() in {'information_schema', 'sys', 'pg_catalog'}
                or schema.lower().startswith(('pg_toast', 'pg_temp'))
                or (self.name == 'firebird' and name.upper().startswith(('RDB$', 'MON$', 'SEC$')))
                or (self.name == 'mysql' and catalog.lower() in {'mysql', 'sys', 'information_schema', 'performance_schema'}))

    def count_sql(self, table) -> str:
        return f'SELECT COUNT(*) FROM {self.table(table)}'

    def duplicates_sql(self, table, columns: list[str], *, exclude_nulls=False) -> str:
        names = ', '.join(self.identifier(c) for c in columns)
        where = (' WHERE ' + ' AND '.join(f'{self.identifier(c)} IS NOT NULL' for c in columns)) if exclude_nulls else ''
        return f'SELECT COUNT(*) FROM (SELECT {names} FROM {self.table(table)}{where} GROUP BY {names} HAVING COUNT(*) > 1) dq_groups'


ENGINES = {e.name: e for e in (
    Engine('firebird', 3050, 'org.firebirdsql.jdbc.FBDriver'),
    Engine('postgresql', 5432, 'org.postgresql.Driver'),
    Engine('sqlserver', 1433, 'com.microsoft.sqlserver.jdbc.SQLServerDriver'),
    Engine('mysql', 3306, 'com.mysql.cj.jdbc.Driver', '`'),
)}


def get_engine(name: str) -> Engine:
    try:
        return ENGINES[name.lower()]
    except (KeyError, AttributeError):
        raise ValueError('Banco não suportado. Use firebird, postgresql, sqlserver ou mysql.') from None


def jdbc_url(config: dict) -> str:
    engine = get_engine(config['engine'])
    host, database = str(config.get('host', 'localhost')), str(config['database'])
    # Do not allow URL properties, userinfo or query-string credential injection.
    if any(c in host + database for c in ';?&#@=\r\n') or '://' in host or not host or not database:
        raise ValueError('Host/banco inválido; propriedades e credenciais não são permitidas na URL.')
    port = int(config.get('port') or engine.port)
    if not 1 <= port <= 65535:
        raise ValueError('Porta deve estar entre 1 e 65535.')
    if engine.name == 'sqlserver':
        return f'jdbc:sqlserver://{host}:{port};databaseName={database}'
    scheme = 'firebirdsql' if engine.name == 'firebird' else engine.name
    return f'jdbc:{scheme}://{host}:{port}/{database}'


# JDBC type families are portable; native names are retained for precision checks.
def family(column) -> str:
    code = column.jdbc_type
    if code in (-6, 5, 4, -5, 2, 3):
        return 'number'
    if code in (1, 12, -9, -15):
        if column.size > 65536 or column.type_name.lower() in ('text', 'ntext', 'longtext', 'mediumtext', 'clob', 'nclob'):
            return 'unsupported'
        return 'text'
    if code in (16, -7):
        return 'boolean'
    if code == 91:
        return 'date'
    return 'unsupported'


def compatible(source_engine, target_engine, source, target) -> bool | None:
    get_engine(source_engine)
    get_engine(target_engine)
    a, b = family(source), family(target)
    if 'unsupported' in (a, b):
        return None
    if a != b:
        return False
    if a in ('number', 'text'):
        if not source.size or not target.size:
            return None
        if a == 'number':
            if 'unsigned' in source.type_name.lower() or 'unsigned' in target.type_name.lower():
                return None
            return target.scale >= source.scale and target.size - target.scale >= source.size - source.scale
        return target.size >= source.size
    return True
