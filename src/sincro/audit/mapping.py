import re
import unicodedata

from .domain import ColumnMapping, Manifest, TableMapping


def normalized(name):
    return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode().lower())


def candidate(name, targets, name_of=lambda x: x.name):
    for transform, confidence, reason in (
        (lambda x: x, 1.0, 'Nome exato'),
        (str.casefold, 0.9, 'Nome sem diferença de caixa'),
        (normalized, 0.75, 'Nome normalizado'),
    ):
        matches = [t for t in targets if transform(name_of(t)) == transform(name)]
        if len(matches) == 1:
            return matches[0], confidence, reason
        if len(matches) > 1:
            return None, 0.0, 'Ambíguo; escolha manualmente'
    return None, 0.0, 'Nenhum candidato'


def suggest(source, target) -> Manifest:
    result = Manifest()
    for table in source.tables:
        dest, confidence, reason = candidate(table.name, target.tables)
        mapping = TableMapping(table.id, dest.id if dest else '', confidence=confidence, reason=reason)
        mapping.source_key = list(table.primary_key.columns)
        for column in table.columns:
            match, score, why = candidate(column.name, dest.columns if dest else [])
            mapping.columns.append(ColumnMapping(column.name, match.name if match else '', confidence=score, reason=why))
        if dest:
            names = {c.source: c.target for c in mapping.columns}
            mapping.target_key = [names[k] for k in mapping.source_key if names.get(k)]
        result.mappings.append(mapping)
    # Multiple sources suggesting the same target are also ambiguous.
    for mapping in result.mappings:
        if mapping.target and sum(m.target == mapping.target for m in result.mappings) > 1:
            mapping.target = ''
            mapping.confidence = 0
            mapping.reason = 'Destino disputado por várias tabelas; escolha manualmente'
    return result


def validate_manifest(manifest):
    if manifest.format_version != 1:
        raise ValueError('Versão do manifesto não suportada.')
    sources, targets = set(), set()
    for table in manifest.mappings:
        if table.source in sources:
            raise ValueError('Tabela de origem duplicada no manifesto.')
        sources.add(table.source)
        if table.ignored:
            if not table.justification.strip():
                raise ValueError('Exclusão de tabela exige justificativa.')
            continue
        if table.target and table.target in targets:
            raise ValueError('Destino compartilhado exige comparação customizada ainda não disponível.')
        targets.add(table.target)
        if len(table.source_key) != len(table.target_key) or len(set(table.source_key)) != len(table.source_key) or len(set(table.target_key)) != len(table.target_key):
            raise ValueError('Chaves inválidas no manifesto.')
        if table.expected_target_count is not None and table.expected_target_count < 0:
            raise ValueError('Cardinalidade esperada inválida.')
        cols, dests = set(), set()
        for col in table.columns:
            if col.source in cols:
                raise ValueError('Coluna de origem duplicada.')
            cols.add(col.source)
            if col.ignored:
                if not col.justification.strip():
                    raise ValueError('Exclusão de coluna exige justificativa.')
            elif col.target:
                if col.target in dests:
                    raise ValueError('Coluna destino duplicada.')
                dests.add(col.target)
