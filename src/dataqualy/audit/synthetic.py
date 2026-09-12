"""Small, entirely synthetic fixtures. Not a production database connector."""
from collections import Counter
from copy import deepcopy

from .domain import Column, ColumnProfile, PrimaryKey, Table, TableProfile, CaptureOptions
from .orchestration import Workflow
from .storage import save


class MemoryConnector:
    def __init__(self, engine, tables, data):
        self.engine, self.tables, self.data = engine, deepcopy(tables), data
        self.identity = 'synthetic:' + engine

    def discover(self, options):
        return deepcopy(self.tables)

    def profile(self, table, options, token):
        from .engines import family
        rows = self.data[table.id]
        result = TableProfile(len(rows))
        for column in table.columns:
            values = [r.get(column.name) for r in rows]
            nonnull = [v for v in values if v is not None]
            cp = ColumnProfile(values.count(None))
            if options.profile != 'fast' and family(column) != 'unsupported':
                cp.distinct = len(set(nonnull))
                if nonnull and token and family(column) in ('number', 'date'):
                    cp.minimum, cp.maximum = token(min(nonnull), column), token(max(nonnull), column)
            result.columns[column.name] = cp
        keys = options.keys.get(table.id, table.primary_key.columns)
        if keys:
            result.duplicate_keys = sum(count > 1 for count in Counter(tuple(r.get(k) for k in keys) for r in rows).values())
            result.null_keys = sum(any(r.get(k) is None for k in keys) for r in rows)
        if options.profile != 'fast':
            for index in table.indexes:
                if index.unique and not index.partial:
                    result.unique_violations[index.name] = sum(n > 1 for n in Counter(tuple(r.get(k) for k in index.columns) for r in rows if all(r.get(k) is not None for k in index.columns)).values())
            for fk in table.foreign_keys:
                parent = {tuple(r.get(k) for k in fk.target_columns) for r in self.data.get(fk.target_table, [])}
                result.orphans[fk.name] = sum(tuple(r.get(k) for k in fk.columns) not in parent for r in rows if all(r.get(k) is not None for k in fk.columns))
        return result

    def rows(self, table, columns, options):
        for row in self.data[table.id]:
            yield [row.get(c.name) for c in columns]

    def close(self):
        pass


def demo(directory):
    source_table = Table('ITEMS', columns=[Column('ID', 'INTEGER', 4, False, 10), Column('LABEL', 'VARCHAR', 12, True, 80)], primary_key=PrimaryKey(['ID']))
    target_table = Table('items', 'public', columns=[Column('id', 'int4', 4, False, 10), Column('label', 'varchar', 12, True, 80)], primary_key=PrimaryKey(['id']))
    source = MemoryConnector('firebird', [source_table], {source_table.id: [{'ID': 1, 'LABEL': 'synthetic-alpha'}, {'ID': 2, 'LABEL': 'synthetic-beta'}]})
    baseline = MemoryConnector('postgresql', [target_table], {target_table.id: []})
    target = MemoryConnector('postgresql', [target_table], {target_table.id: [{'id': 1, 'label': 'synthetic-alpha'}, {'id': 2, 'label': 'synthetic-beta'}]})
    workflow = Workflow(directory)
    import secrets
    secret = secrets.token_hex(32)
    options = CaptureOptions(profile='exhaustive', quiescent=True)
    workflow.capture('source', source, options=options, secret=secret)
    workflow.capture('baseline', baseline, options=options, secret=secret)
    manifest = workflow.suggest()
    for mapping in manifest.mappings:
        mapping.confirmed = True  # Only this hardcoded synthetic demonstration confirms automatically.
    save(workflow.directory / 'mapping.json', manifest)
    workflow.capture('target', target, options=options, secret=secret)
    return workflow.report()
