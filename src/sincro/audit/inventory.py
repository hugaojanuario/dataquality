from collections import defaultdict
from copy import deepcopy
import os
from pathlib import Path

from .connectors import Cancelled
from .domain import CaptureOptions, Database, Finding, Schema, Snapshot, now
from .engines import family, get_engine
from .evidence import Hasher, checksum, create_store
from .storage import save


def capture(connector, *, run_id: str, role: str, path, options=None, secret=None, progress=None, cancel=None) -> Snapshot:
    options = deepcopy(options or CaptureOptions())
    if role not in ('source', 'baseline', 'target') or not run_id.strip():
        raise ValueError('Informe etapa e identificador de execução válidos.')
    if options.profile not in ('fast', 'balanced', 'exhaustive') or not 1 <= options.batch_size <= 10000 or not 1 <= options.timeout_seconds <= 3600:
        raise ValueError('Perfil, lote ou timeout inválido.')
    hasher = Hasher(secret) if secret else None
    snapshot = Snapshot(run_id, role, get_engine(connector.engine).name, options=options)
    snapshot.key_id = hasher.key_id if hasher else ''
    snapshot.connection_id = getattr(connector, 'identity', '')
    path = Path(path)
    db = temporary = None

    def checkpoint():
        if cancel is not None and cancel.is_set():
            raise Cancelled('Captura cancelada.')

    try:
        checkpoint()
        snapshot.tables = connector.discover(options)
        if len({t.id for t in snapshot.tables}) != len(snapshot.tables):
            raise ValueError('Inventário duplicado.')
        schemas = defaultdict(list)
        for table in snapshot.tables:
            schemas[table.schema].append(table.id)
        snapshot.database = Database(snapshot.engine, [Schema(k, v) for k, v in schemas.items()])
        if options.profile == 'exhaustive' and hasher and role != 'baseline':
            db, temporary = create_store(path.parent)
        for index, table in enumerate(snapshot.tables):
            checkpoint()
            if progress:
                progress(f'{role}: tabela {index + 1}/{len(snapshot.tables)}')
            try:
                profile = connector.profile(table, options, hasher.token if hasher else None)
                snapshot.profiles[table.id] = profile
                if db is not None:
                    keys = options.keys.get(table.id, table.primary_key.columns)
                    supported = [c for c in table.columns if family(c) != 'unsupported']
                    by_name = {c.name: c for c in supported}
                    if not keys or not set(keys) <= by_name.keys():
                        snapshot.findings.append(Finding('fingerprint', 'inconclusive', 'Chave ausente ou tipo de chave sem canonicalização segura.', table.id, 'warning'))
                        continue
                    if profile.duplicate_keys != 0 or profile.null_keys != 0:
                        snapshot.findings.append(Finding('fingerprint', 'inconclusive', 'Chave duplicada, nula ou não verificada; comparação por chave indisponível.', table.id, 'warning'))
                        continue
                    positions = [supported.index(by_name[k]) for k in keys]
                    count = 0
                    for row in connector.rows(table, supported, options):
                        checkpoint()
                        if len(row) != len(supported):
                            raise ValueError('Linha incompleta.')
                        key = hasher.key([row[p] for p in positions], [by_name[k] for k in keys])
                        db.executemany('INSERT INTO cells VALUES (?, ?, ?, ?)', ((table.id, key, c.name, hasher.token(value, c)) for c, value in zip(supported, row, strict=True)))
                        count += 1
                        if count % options.batch_size == 0:
                            db.commit()
                            if progress:
                                progress(f'{role}: {count} registros processados na tabela {index + 1}')
                    if count != profile.count:
                        raise ValueError('Contagem mudou durante leitura.')
                    # Detect a key changing/duplicating between aggregation and streaming.
                    duplicated = db.execute('SELECT 1 FROM cells WHERE table_id=? AND column_name=? GROUP BY key_hash HAVING COUNT(*)>1 LIMIT 1', (table.id, supported[0].name)).fetchone()
                    if duplicated:
                        raise ValueError('Chave inconsistente durante leitura.')
                    profile.evidence_columns = [c.name for c in supported]
                    profile.evidence_key = list(keys)
            except Cancelled:
                raise
            except Exception:
                if db is not None:
                    db.execute('DELETE FROM cells WHERE table_id=?', (table.id,))
                snapshot.findings.append(Finding('capture_table', 'error', 'Captura da tabela incompleta. Verifique SELECT, tipos, estabilidade e timeout.', table.id, 'critical'))
        checkpoint()
        if db is not None:
            db.commit()
            db.close()
            db = None
            destination = path.parent / f'{snapshot.id}.sqlite'
            os.replace(temporary, destination)
            temporary = None
            snapshot.evidence_file = destination.name
            snapshot.evidence_sha256 = checksum(destination)
        snapshot.complete = not any(f.status == 'error' for f in snapshot.findings)
    except Cancelled:
        snapshot.findings.append(Finding('capture', 'inconclusive', 'Captura cancelada; refaça esta etapa.', severity='warning'))
    except Exception:
        snapshot.findings.append(Finding('capture', 'error', 'Não foi possível concluir a descoberta/captura. Verifique conexão e permissões.', severity='critical'))
    finally:
        if db is not None:
            db.close()
        if temporary is not None:
            temporary.unlink(missing_ok=True)
        snapshot.finished_at = now()
    save(path, snapshot)
    return snapshot
