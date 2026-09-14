"""Public demonstration: synthetic rows passed through the real audit engine."""
from __future__ import annotations

import secrets
from copy import deepcopy
from pathlib import Path
from threading import Event
from typing import Callable

from sincro.audit.domain import CaptureOptions, Column, PrimaryKey, Table
from sincro.audit.orchestration import Workflow
from sincro.audit.storage import save
from sincro.audit.synthetic import MemoryConnector


def create_demo(directory: Path, progress: Callable[[str], None], cancel: Event) -> None:
    source_tables, target_tables, source_data, target_data = [], [], {}, {}
    for name, size in [('PRODUCTS', 48), ('CATEGORIES', 8), ('WAREHOUSES', 4)]:
        source = Table(name, columns=[Column('ID', 'INTEGER', 4, False, 10),
                                     Column('LABEL', 'VARCHAR', 12, True, 80)],
                       primary_key=PrimaryKey(['ID']))
        target = Table(name.lower(), 'public', columns=[Column('id', 'int4', 4, False, 10),
                                                       Column('label', 'varchar', 12, True, 80)],
                       primary_key=PrimaryKey(['id']))
        source_tables.append(source)
        target_tables.append(target)
        source_data[source.id] = [{'ID': i, 'LABEL': f'synthetic-{i:03d}'} for i in range(1, size + 1)]
        target_data[target.id] = [{'id': i, 'label': f'synthetic-{i:03d}'} for i in range(1, size + 1)]
    # Exactly one altered synthetic record, no personal data or real identifiers.
    changed = deepcopy(target_data)
    changed[target_tables[0].id][0]['label'] = 'synthetic-divergence'
    workflow = Workflow(directory)
    options = CaptureOptions(profile='exhaustive', quiescent=True)
    secret = secrets.token_hex(32)
    for role, connector in [
        ('source', MemoryConnector('firebird', source_tables, source_data)),
        ('baseline', MemoryConnector('postgresql', target_tables, {t.id: [] for t in target_tables})),
    ]:
        workflow.capture(role, connector, options=options, secret=secret, progress=progress, cancel=cancel)
    manifest = workflow.suggest()
    for mapping in manifest.mappings:
        mapping.confirmed = True  # Authorized only for this hardcoded synthetic fixture.
    save(directory / 'mapping.json', manifest)
    workflow.capture('target', MemoryConnector('postgresql', target_tables, changed),
                     options=options, secret=secret, progress=progress, cancel=cancel)
    workflow.report(cancel=cancel)
