"""Public contracts only. No converter execution, model dependency or proprietary code."""
from dataclasses import dataclass, field
from typing import Literal, Protocol
import json

from .domain import Manifest
from .storage import decode


@dataclass
class ProviderMessage:
    protocol_version: int
    request_id: str
    run_id: str
    type: Literal['capabilities', 'validate_config', 'start', 'progress', 'table_metrics', 'completed', 'failed', 'cancel', 'cancelled']
    payload: dict = field(default_factory=dict)


def parse_provider_line(line: str) -> ProviderMessage:
    try:
        if len(line.encode('utf-8')) > 65536:
            raise ValueError()
        data = json.loads(line)
        if not isinstance(data, dict) or set(data) != {'protocol_version', 'request_id', 'run_id', 'type', 'payload'}:
            raise ValueError()
        if type(data['protocol_version']) is not int or data['protocol_version'] != 1 or not all(isinstance(data[k], str) and data[k] for k in ('request_id', 'run_id', 'type')) or not isinstance(data['payload'], dict):
            raise ValueError()
        if data['type'] not in ProviderMessage.__annotations__['type'].__args__:
            raise ValueError()
        return ProviderMessage(**data)
    except (ValueError, TypeError):
        raise ValueError('Mensagem de provider inválida.') from None


@dataclass
class AIConfig:
    enabled: bool = False
    provider: str = ''
    metadata_only: bool = True


class AIAssistant(Protocol):
    def suggest(self, metadata: dict) -> str:
        """Return a JSON Manifest, never findings or approval."""
        ...


def validate_ai_suggestion(payload: str) -> Manifest:
    try:
        if len(payload.encode()) > 1_000_000:
            raise ValueError()
        manifest = decode(Manifest, json.loads(payload))
        from .mapping import validate_manifest
        validate_manifest(manifest)
        for mapping in manifest.mappings:
            mapping.confirmed = False
            mapping.reason = 'Sugestão de IA; exige revisão humana e não constitui evidência'
        return manifest
    except (ValueError, TypeError):
        raise ValueError('Sugestão de IA inválida; use o schema do manifesto.') from None
