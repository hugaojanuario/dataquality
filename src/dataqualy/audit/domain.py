from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

Status = Literal['passed', 'failed', 'inconclusive', 'error', 'skipped']
Profile = Literal['fast', 'balanced', 'exhaustive']


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class ConnectionProfile:
    engine: str
    database: str
    user: str = field(repr=False)
    jar: str = ''
    host: str = 'localhost'
    port: int | None = None
    password_env: str = ''
    # Secrets deliberately do not belong to this serializable model.


@dataclass
class Column:
    name: str
    type_name: str
    jdbc_type: int
    nullable: bool = True
    size: int = 0
    scale: int = 0


@dataclass
class PrimaryKey:
    columns: list[str] = field(default_factory=list)
    name: str = ''


@dataclass
class ForeignKey:
    name: str
    columns: list[str]
    target_table: str
    target_columns: list[str]


@dataclass
class Index:
    name: str
    columns: list[str]
    unique: bool = False
    partial: bool = False


@dataclass
class Table:
    name: str
    schema: str = ''
    catalog: str = ''
    columns: list[Column] = field(default_factory=list)
    primary_key: PrimaryKey = field(default_factory=PrimaryKey)
    foreign_keys: list[ForeignKey] = field(default_factory=list)
    indexes: list[Index] = field(default_factory=list)

    @property
    def id(self) -> str:
        # Escaped JSON identifiers avoid collisions involving dots in names.
        import json
        return json.dumps([self.catalog, self.schema, self.name], ensure_ascii=False, separators=(',', ':'))


@dataclass
class Schema:
    name: str
    tables: list[str] = field(default_factory=list)


@dataclass
class Database:
    engine: str
    schemas: list[Schema] = field(default_factory=list)


@dataclass
class ColumnProfile:
    nulls: int
    distinct: int | None = None
    # HMAC of bounds; actual values (possibly personal) are never persisted.
    minimum: str | None = None
    maximum: str | None = None


@dataclass
class TableProfile:
    count: int
    columns: dict[str, ColumnProfile] = field(default_factory=dict)
    duplicate_keys: int | None = None
    null_keys: int | None = None
    unique_violations: dict[str, int] = field(default_factory=dict)
    orphans: dict[str, int] = field(default_factory=dict)
    evidence_columns: list[str] = field(default_factory=list)
    evidence_key: list[str] = field(default_factory=list)


@dataclass
class Finding:
    check: str
    status: Status
    message: str
    table: str = ''
    severity: Literal['info', 'warning', 'critical'] = 'info'
    metrics: dict[str, int | float | None] = field(default_factory=dict)
    sample: list[str] = field(default_factory=list)

    def __post_init__(self):
        self.sample = ['[redigido]' for _ in self.sample[:20]]


@dataclass
class CaptureOptions:
    profile: Profile = 'balanced'
    include_system: bool = False
    batch_size: int = 500
    timeout_seconds: int = 60
    quiescent: bool = False
    # Operator assertion: writes are paused during captures (no global MVCC claim).
    keys: dict[str, list[str]] = field(default_factory=dict)


@dataclass
class Snapshot:
    run_id: str
    role: Literal['source', 'baseline', 'target']
    engine: str
    format_version: int = 1
    id: str = field(default_factory=lambda: str(uuid4()))
    captured_at: str = field(default_factory=now)
    finished_at: str = ''
    options: CaptureOptions = field(default_factory=CaptureOptions)
    database: Database | None = None
    tables: list[Table] = field(default_factory=list)
    profiles: dict[str, TableProfile] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    complete: bool = False
    evidence_file: str = ''
    evidence_sha256: str = ''
    key_id: str = ''
    connection_id: str = ''


@dataclass
class ColumnMapping:
    source: str
    target: str = ''
    ignored: bool = False
    justification: str = ''
    transformation: str = ''
    comparison: str = 'exact'
    confidence: float = 0.0
    reason: str = ''


@dataclass
class TableMapping:
    source: str
    target: str = ''
    columns: list[ColumnMapping] = field(default_factory=list)
    source_key: list[str] = field(default_factory=list)
    target_key: list[str] = field(default_factory=list)
    ignored: bool = False
    justification: str = ''
    confirmed: bool = False
    cardinality: str = '1:1'
    expected_target_count: int | None = None
    expected_filter: str = ''
    confidence: float = 0.0
    reason: str = ''


@dataclass
class Manifest:
    mappings: list[TableMapping] = field(default_factory=list)
    format_version: int = 1


@dataclass
class Stage:
    name: str
    status: Status
    started_at: str
    finished_at: str


@dataclass
class AuditRun:
    run_id: str
    findings: list[Finding] = field(default_factory=list)
    stages: list[Stage] = field(default_factory=list)
    table_coverage: float = 0.0
    column_coverage: float = 0.0
    excluded_tables: int = 0
    excluded_columns: int = 0
    manifest: Manifest = field(default_factory=Manifest)
    snapshots: list[Snapshot] = field(default_factory=list)
    started_at: str = field(default_factory=now)
    finished_at: str = ''

    @property
    def quality(self) -> Status:
        states = {f.status for f in self.findings}
        return 'failed' if 'failed' in states else ('passed' if 'passed' in states else 'inconclusive')

    @property
    def status(self) -> Status:
        states = {f.status for f in self.findings}
        for state in ('error', 'failed', 'inconclusive'):
            if state in states:
                return state
        if not states or self.table_coverage < 100 or self.column_coverage < 100:
            return 'inconclusive'
        return 'passed' if 'passed' in states else 'inconclusive'
