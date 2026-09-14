"""Strict versioned JSON and atomic, owner-only local artifacts."""
import json
import math
import os
import tempfile
import types
from dataclasses import asdict, fields, is_dataclass
from pathlib import Path
from typing import Literal, Union, get_args, get_origin, get_type_hints

from .domain import Manifest, Snapshot


def decode(cls, data):
    origin, args = get_origin(cls), get_args(cls)
    if origin in (Union, types.UnionType):
        for candidate in args:
            try:
                return decode(candidate, data)
            except (ValueError, TypeError):
                pass
        raise ValueError('Valor incompatível com o formato.')
    if origin is Literal:
        if data not in args:
            raise ValueError('Opção inválida no documento.')
        return data
    if origin is list:
        if not isinstance(data, list):
            raise ValueError('Lista esperada.')
        return [decode(args[0], x) for x in data]
    if origin is dict:
        if not isinstance(data, dict):
            raise ValueError('Mapa esperado.')
        return {decode(args[0], k): decode(args[1], v) for k, v in data.items()}
    if is_dataclass(cls):
        if not isinstance(data, dict) or set(data) - {f.name for f in fields(cls)}:
            raise ValueError('Campos desconhecidos no documento.')
        hints = get_type_hints(cls)
        try:
            return cls(**{k: decode(hints[k], v) for k, v in data.items()})
        except TypeError:
            raise ValueError('Campos obrigatórios ausentes.') from None
    if type(data) is not cls and not (cls is float and type(data) is int):
        raise ValueError('Tipo inválido no documento.')
    if cls is float and not math.isfinite(data):
        raise ValueError('Número não finito no documento.')
    return data


def atomic_write(path: str | Path, content: str) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.dq-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    return path


def save(path: str | Path, document) -> Path:
    return atomic_write(path, json.dumps(asdict(document), ensure_ascii=False, indent=2, allow_nan=False))


def load(path: str | Path, cls=Snapshot):
    try:
        data = json.loads(Path(path).read_text(encoding='utf-8'))
        if not isinstance(data, dict) or data.get('format_version') != 1:
            raise ValueError('Versão de formato não suportada.')
        return decode(cls, data)
    except (OSError, ValueError, TypeError):
        raise ValueError('Documento inválido, inacessível ou versão não suportada.') from None
