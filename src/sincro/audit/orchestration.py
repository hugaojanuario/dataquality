"""Small resumable local workflow. Conversion remains an external operator step."""
from dataclasses import dataclass, field
from pathlib import Path
from uuid import uuid4

from .checks import compare
from .domain import CaptureOptions, ConnectionProfile, Manifest, Profile, Snapshot, Stage, now
from .inventory import capture
from .mapping import suggest, validate_manifest
from .reporting import write_report
from .storage import load, save


@dataclass
class Project:
    run_id: str = field(default_factory=lambda: str(uuid4()))
    format_version: int = 1
    stages: list[Stage] = field(default_factory=list)
    name: str = ''
    description: str = ''
    source: ConnectionProfile | None = None
    target: ConnectionProfile | None = None
    capture_profile: Profile = 'balanced'
    include_system: bool = False
    key_env: str = 'SINCRO_EVIDENCE_KEY'
    last_page: int = 0


class Workflow:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.path = self.directory / 'project.json'
        self.project = load(self.path, Project) if self.path.exists() else Project()
        save(self.path, self.project)

    def snapshot(self, role):
        return load(self.directory / f'{role}.json')

    def capture(self, role, connector, *, options=None, secret=None, progress=None, cancel=None):
        if role == 'baseline':
            if not self.snapshot('source').complete:
                raise ValueError('Conclua a captura da origem primeiro.')
        elif role == 'target':
            if not self.snapshot('baseline').complete:
                raise ValueError('Conclua a baseline primeiro.')
            manifest = load(self.directory / 'mapping.json', Manifest)
            validate_manifest(manifest)
            if not manifest.mappings or not all(m.confirmed for m in manifest.mappings):
                raise ValueError('Revise e confirme o manifesto antes de validar o destino.')
        if role == 'source' and (self.directory / 'baseline.json').exists():
            raise ValueError('Baseline já existe. Use outro diretório para uma nova execução.')
        if role == 'baseline' and (self.directory / 'target.json').exists():
            raise ValueError('Destino já capturado. Use outro diretório para uma nova execução.')
        snapshot = capture(connector, run_id=self.project.run_id, role=role, path=self.directory / f'{role}.json', options=options, secret=secret, progress=progress, cancel=cancel)
        self.project.stages.append(Stage(role, 'passed' if snapshot.complete else 'error', snapshot.captured_at, snapshot.finished_at))
        save(self.path, self.project)
        return snapshot

    def suggest(self):
        manifest = suggest(self.snapshot('source'), self.snapshot('baseline'))
        path = self.directory / 'mapping.json'
        if path.exists():
            raise ValueError('Manifesto já existe. Edite o arquivo existente para preservar sua revisão.')
        save(path, manifest)
        return manifest

    def report(self, cancel=None):
        started = now()
        run = compare(self.snapshot('source'), self.snapshot('baseline'), self.snapshot('target'), load(self.directory / 'mapping.json', Manifest), source_dir=self.directory, target_dir=self.directory, cancel=cancel)
        self.project.stages.append(Stage('comparison', run.status, started, now()))
        save(self.path, self.project)
        return run, write_report(run, self.directory / 'report.html')
