from pathlib import Path
from typing import Any

import yaml


def _require_mapping(config: dict[str, Any], key: str) -> dict[str, Any]:
    value = config.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"A seção '{key}' é obrigatória e deve ser um mapa.")
    return value


def _validate_source(name: str, source: dict[str, Any]) -> None:
    source_type = source.get("type", "csv")
    if source_type == "csv" and not source.get("path"):
        raise ValueError(f"A fonte '{name}' precisa de path.")
    if source_type == "jdbc":
        required = ("engine", "database", "user", "jar")
        missing = [field for field in required if not source.get(field)]
        if missing:
            raise ValueError(f"A fonte '{name}' não informou: {', '.join(missing)}.")
        if bool(source.get("table")) == bool(source.get("query")):
            raise ValueError(f"A fonte '{name}' deve informar exatamente table ou query.")
    elif source_type != "csv":
        raise ValueError(f"Tipo de fonte não suportado: {source_type}")


def validate_config(config: Any) -> dict[str, Any]:
    """Valida a estrutura antes de iniciar Spark ou acessar bancos."""
    if not isinstance(config, dict):
        raise ValueError("A raiz do YAML deve ser um mapa.")
    if config.get("mode", "migration") == "package":
        package = _require_mapping(config, "package")
        if not package.get("files") and not package.get("attachments"):
            raise ValueError("Informe package.files ou package.attachments.")
        return config

    _require_mapping(config, "checks")
    if "datasets" in config:
        datasets = _require_mapping(config, "datasets")
        if not datasets:
            raise ValueError("A seção datasets não pode ficar vazia.")
        for name, source in datasets.items():
            if not isinstance(source, dict):
                raise ValueError(f"A fonte '{name}' deve ser um mapa.")
            _validate_source(name, source)
        return config

    source = _require_mapping(config, "source")
    target = _require_mapping(config, "target")
    if not config.get("key"):
        raise ValueError("O campo 'key' é obrigatório.")
    _validate_source("source", source)
    _validate_source("target", target)
    return config


def load_config(path: str | Path) -> dict[str, Any]:
    """Carrega e valida uma configuração YAML UTF-8."""
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuração não encontrada: {config_path}")
    with config_path.open(encoding="utf-8") as file:
        return validate_config(yaml.safe_load(file))


# @hugaojanuario
