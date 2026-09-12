"""Private keyed digests on disk; never store row values or unkeyed low-entropy hashes."""
from contextlib import contextmanager
from datetime import date
from decimal import Decimal
import hashlib
import hmac
import json
from pathlib import Path
import sqlite3
import tempfile

from .engines import family


def canonical(value, column) -> str:
    if value is None:
        return 'null'
    kind = family(column)
    if kind == 'number':
        number = Decimal(str(value))
        if not number.is_finite():
            raise ValueError('Número não finito.')
        return 'n:' + (format(number, 'f').rstrip('0').rstrip('.') if '.' in format(number, 'f') else format(number, 'f')) if number else 'n:0'
    if kind == 'text':
        text = str(value)
        if len(text) > 65536:
            raise ValueError('Texto excede limite de canonicalização.')
        return 's:' + text
    if kind == 'boolean':
        if value not in (True, False, 'true', 'false', '1', '0'):
            raise ValueError('Booleano não canônico.')
        return 'b:1' if value in (True, 'true', '1') else 'b:0'
    if kind == 'date':
        return 'd:' + date.fromisoformat(str(value)).isoformat()
    raise ValueError('Tipo sem canonicalização segura.')


class Hasher:
    def __init__(self, secret: str):
        if len(secret.encode()) < 32:
            raise ValueError('A chave de evidência precisa ter pelo menos 32 bytes.')
        self._key = secret.encode()
        self.key_id = self.digest('dataquality-key-id-v1')

    def digest(self, value: str) -> str:
        return hmac.new(self._key, value.encode('utf-8'), hashlib.sha256).hexdigest()

    def token(self, value, column):
        return self.digest('value-v1:' + canonical(value, column))

    def key(self, values, columns):
        return self.digest('key-v1:' + json.dumps([canonical(v, c) for v, c in zip(values, columns, strict=True)], ensure_ascii=False))


def checksum(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def create_store(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    import os
    fd, name = tempfile.mkstemp(prefix='.dq-evidence-', suffix='.sqlite', dir=directory)
    os.close(fd)
    db = sqlite3.connect(name)
    db.execute('PRAGMA temp_store=FILE')
    db.execute('CREATE TABLE cells (table_id TEXT, key_hash TEXT, column_name TEXT, value_hash TEXT)')
    db.execute('CREATE INDEX lookup ON cells(table_id, column_name, key_hash)')
    return db, Path(name)


@contextmanager
def open_store(snapshot, directory):
    path = Path(directory) / snapshot.evidence_file
    if not snapshot.evidence_file or Path(snapshot.evidence_file).name != snapshot.evidence_file or path.is_symlink():
        raise ValueError('Artefato de evidência inválido.')
    if checksum(path) != snapshot.evidence_sha256:
        raise ValueError('Integridade do artefato de evidência inválida.')
    db = sqlite3.connect(path.resolve().as_uri() + '?mode=ro', uri=True)
    try:
        db.execute('PRAGMA query_only=ON')
        yield db
    finally:
        db.close()


def compare_column(source_db, target_db, source_table, target_table, source_column, target_column, cancel=None):
    # Sorted index cursors: memory is O(1), regardless of table size.
    sql = 'SELECT key_hash, value_hash FROM cells WHERE table_id=? AND column_name=? ORDER BY key_hash'
    left = iter(source_db.execute(sql, (source_table, source_column)))
    right = iter(target_db.execute(sql, (target_table, target_column)))
    a, b = next(left, None), next(right, None)
    missing = extra = changed = 0
    while a is not None or b is not None:
        if cancel is not None and cancel.is_set():
            from .connectors import Cancelled
            raise Cancelled('Comparação cancelada.')
        if b is None or (a is not None and a[0] < b[0]):
            missing += 1
            a = next(left, None)
        elif a is None or b[0] < a[0]:
            extra += 1
            b = next(right, None)
        else:
            changed += a[1] != b[1]
            a, b = next(left, None), next(right, None)
    return missing, extra, changed
