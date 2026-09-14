from contextlib import ExitStack

from .domain import AuditRun, Finding, Stage, now
from .engines import compatible, family
from .evidence import open_store, compare_column
from .mapping import validate_manifest
from .connectors import Cancelled


def compare(source, baseline, target, manifest, *, source_dir='.', target_dir='.', cancel=None) -> AuditRun:
    run = AuditRun(source.run_id, manifest=manifest, snapshots=[source, baseline, target])

    def finding(check, status, message, table='', **metrics):
        run.findings.append(Finding(check, status, message, table, 'critical' if status in ('failed', 'error') else ('warning' if status == 'inconclusive' else 'info'), metrics))

    def equal(check, a, b, table):
        finding(check, 'inconclusive' if a is None or b is None else ('passed' if a == b else 'failed'), 'Evidência indisponível.' if a is None or b is None else 'Comparação determinística das evidências.', table)

    def zero(check, value, table):
        finding(check, 'inconclusive' if value is None else ('passed' if value == 0 else 'failed'), 'Quantidade de violações; evidência ausente impede aprovação.', table, violations=value)

    try:
        validate_manifest(manifest)
    except ValueError:
        finding('manifest', 'error', 'Manifesto inválido: revise duplicações, exclusões e chaves.')
        run.finished_at = now()
        return run
    for snapshot, role in zip((source, baseline, target), ('source', 'baseline', 'target'), strict=True):
        run.stages.append(Stage(role, 'passed' if snapshot.complete else 'error', snapshot.captured_at, snapshot.finished_at))
        run.findings.extend(snapshot.findings)
        if snapshot.role != role or snapshot.run_id != source.run_id or snapshot.format_version != 1:
            finding('provenance', 'error', 'Snapshots precisam pertencer à mesma execução, versão e etapas corretas.')
        if not snapshot.complete or len(snapshot.profiles) != len(snapshot.tables) or len({t.id for t in snapshot.tables}) != len(snapshot.tables):
            finding('capture_complete', 'error', 'Captura incompleta ou inventário inconsistente.')
        if not snapshot.options.quiescent:
            finding('consistency', 'inconclusive', 'Ausência de confirmação de suspensão das escritas durante a captura.')
    if baseline.engine != target.engine or baseline.options.include_system != target.options.include_system or source.options.include_system != target.options.include_system:
        finding('scope', 'error', 'Engine do destino ou escopo de descoberta mudou entre capturas.')
    if not baseline.connection_id or baseline.connection_id != target.connection_id:
        finding('destination_identity', 'error', 'Baseline e destino precisam identificar a mesma conexão (sem credenciais).')
    try:
        from datetime import datetime
        if not (datetime.fromisoformat(source.finished_at) <= datetime.fromisoformat(baseline.captured_at) and datetime.fromisoformat(baseline.finished_at) <= datetime.fromisoformat(target.captured_at)):
            finding('chronology', 'error', 'Ordem das capturas inválida: origem, baseline, destino.')
    except (ValueError, TypeError):
        finding('chronology', 'error', 'Horários das capturas inválidos.')
    if not source.tables:
        finding('inventory', 'inconclusive', 'Nenhuma tabela de origem descoberta; confira permissões e escopo.')
    for table in baseline.tables:
        profile = baseline.profiles.get(table.id)
        zero('baseline_empty', profile.count if profile else None, table.id)
    sources, targets = {t.id: t for t in source.tables}, {t.id: t for t in target.tables}
    mappings = {m.source: m for m in manifest.mappings}
    for extra in mappings.keys() - sources.keys():
        finding('mapping', 'error', 'Manifesto referencia tabela de origem inexistente.', extra)
    table_covered = column_covered = total_columns = 0
    with ExitStack() as stack:
        source_db = target_db = None
        if source.evidence_file and target.evidence_file and source.key_id and source.key_id == target.key_id:
            try:
                source_db = stack.enter_context(open_store(source, source_dir))
                target_db = stack.enter_context(open_store(target, target_dir))
            except Exception:
                source_db = target_db = None
                finding('evidence_integrity', 'error', 'Evidência ausente, corrompida ou inacessível. Recapture os snapshots.')
        for table_id, table in sources.items():
            if cancel is not None and cancel.is_set():
                finding('comparison_cancelled', 'inconclusive', 'Comparação cancelada; não há aprovação.')
                break
            total_columns += len(table.columns)
            mapping = mappings.get(table_id)
            if mapping is None or not mapping.confirmed:
                finding('mapping', 'inconclusive', 'Tabela sem mapeamento confirmado.', table_id)
                continue
            if mapping.ignored:
                table_covered += 1
                column_covered += len(table.columns)
                run.excluded_tables += 1
                run.excluded_columns += len(table.columns)
                finding('mapping', 'skipped', 'Tabela excluída explicitamente; justificativa no manifesto.', table_id)
                continue
            dest = targets.get(mapping.target)
            if dest is None:
                finding('table_exists', 'failed', 'Tabela destino não encontrada.', table_id)
                continue
            table_covered += 1
            finding('table_exists', 'passed', 'Tabela destino encontrada.', table_id)
            sp, tp = source.profiles.get(table_id), target.profiles.get(dest.id)
            if sp is None or tp is None:
                finding('profiles', 'error', 'Perfil de origem ou destino ausente.', table_id)
                continue
            customized = mapping.cardinality != '1:1' or bool(mapping.expected_filter)
            if customized:
                finding('custom_mapping', 'inconclusive', 'Filtro/cardinalidade declarados exigem comparador específico; SQL do manifesto não é executado.', table_id)
            expected = mapping.expected_target_count if mapping.expected_target_count is not None else sp.count
            diff = tp.count - expected
            finding('row_count', 'passed' if diff == 0 else 'failed', 'Contagem em relação à cardinalidade esperada.', table_id, source=sp.count, target=tp.count, expected=expected, absolute_difference=abs(diff), percentage_difference=(abs(diff) * 100 / expected if expected else (0 if not diff else None)))
            for label, profile in (('source', sp), ('target', tp)):
                zero(label + '_duplicate_keys', profile.duplicate_keys, table_id)
                zero(label + '_null_keys', profile.null_keys, table_id)
            scols, tcols = {c.name: c for c in table.columns}, {c.name: c for c in dest.columns}
            cols = {c.source: c for c in mapping.columns}
            for extra in cols.keys() - scols.keys():
                finding('column_mapping', 'error', 'Coluna de origem inexistente no manifesto.', table_id)
            keys_valid = bool(mapping.source_key) and set(mapping.source_key) <= scols.keys() and set(mapping.target_key) <= tcols.keys()
            keys_valid = keys_valid and all(k in cols and not cols[k].ignored and cols[k].target == dest_key for k, dest_key in zip(mapping.source_key, mapping.target_key, strict=True))
            rows_ready = (keys_valid and not customized and source_db is not None and target_db is not None
                          and sp.evidence_key == mapping.source_key and tp.evidence_key == mapping.target_key
                          and sp.duplicate_keys == tp.duplicate_keys == sp.null_keys == tp.null_keys == 0)
            if not rows_ready:
                finding('row_comparison', 'inconclusive', 'Comparação por chave requer captura exhaustive, mesma chave HMAC, chaves únicas/não nulas e manifesto 1:1 compatível.', table_id)
            for name, column in scols.items():
                if cancel is not None and cancel.is_set():
                    finding('comparison_cancelled', 'inconclusive', 'Comparação cancelada; não há aprovação.', table_id)
                    break
                cm = cols.get(name)
                if cm is None:
                    finding('column_mapping', 'inconclusive', 'Coluna de origem sem mapeamento.', table_id)
                    continue
                if cm.ignored:
                    column_covered += 1
                    run.excluded_columns += 1
                    finding('column_mapping', 'skipped', 'Coluna excluída com justificativa no manifesto.', table_id)
                    continue
                target_column = tcols.get(cm.target)
                if target_column is None:
                    finding('column_exists', 'failed', 'Coluna destino não encontrada.', table_id)
                    continue
                column_covered += 1
                compat = compatible(source.engine, target.engine, column, target_column)
                finding('type:' + name, 'inconclusive' if compat is None else ('passed' if compat else 'failed'), 'Capacidade de representação do tipo destino (família JDBC, precisão e escala).', table_id)
                if cm.transformation or cm.comparison != 'exact':
                    finding('transformation:' + name, 'inconclusive', 'Transformação/comparação declarada sem implementação determinística nesta versão.', table_id)
                    continue
                a, b = sp.columns.get(name), tp.columns.get(cm.target)
                if a is None or b is None:
                    finding('column_profile:' + name, 'error', 'Perfil de coluna incompleto.', table_id)
                    continue
                if not customized:
                    equal('nulls:' + name, a.nulls, b.nulls, table_id)
                    equal('distinct:' + name, a.distinct, b.distinct, table_id)
                    if not column.nullable or not target_column.nullable:
                        zero('required:' + name, b.nulls, table_id)
                    if family(column) in ('number', 'date') and family(target_column) == family(column):
                        if sp.count == a.nulls and tp.count == b.nulls:
                            finding('bounds:' + name, 'skipped', 'Não há valores não nulos para comparar extremos.', table_id)
                        elif source.key_id and source.key_id == target.key_id:
                            equal('minimum:' + name, a.minimum, b.minimum, table_id)
                            equal('maximum:' + name, a.maximum, b.maximum, table_id)
                        else:
                            finding('bounds:' + name, 'inconclusive', 'Extremos exigem mesma chave HMAC nas capturas.', table_id)
                if rows_ready and name in sp.evidence_columns and cm.target in tp.evidence_columns:
                    try:
                        for db, table_ref, col_ref, count in ((source_db, table_id, name, sp.count), (target_db, dest.id, cm.target, tp.count)):
                            observed = db.execute('SELECT COUNT(*), COUNT(DISTINCT key_hash) FROM cells WHERE table_id=? AND column_name=?', (table_ref, col_ref)).fetchone()
                            if observed != (count, count):
                                raise ValueError('Evidência por chave incompleta.')
                        missing, extra, changed = compare_column(source_db, target_db, table_id, dest.id, name, cm.target, cancel=cancel)
                        for check, count in (('missing', missing), ('extra', extra), ('values', changed)):
                            zero(check + ':' + name, count, table_id)
                    except Cancelled:
                        finding('comparison_cancelled', 'inconclusive', 'Comparação cancelada; não há aprovação.', table_id)
                        break
                    except Exception:
                        finding('row_comparison:' + name, 'error', 'Falha na leitura da evidência por chave.', table_id)
                elif rows_ready:
                    finding('row_comparison:' + name, 'inconclusive', 'Coluna sem fingerprint seguro.', table_id)
            # Verify actual uniqueness and preservation of the declaration.
            for index in table.indexes:
                if not index.unique:
                    continue
                mapped = [cols[c].target for c in index.columns if c in cols and not cols[c].ignored]
                candidates = [i for i in dest.indexes if i.unique and i.columns == mapped and not i.partial]
                if index.partial or len(mapped) != len(index.columns) or not candidates:
                    finding('unique:' + index.name, 'inconclusive', 'Índice único parcial, não mapeado ou sem equivalente no destino.', table_id)
                else:
                    zero('source_unique:' + index.name, sp.unique_violations.get(index.name), table_id)
                    zero('target_unique:' + index.name, tp.unique_violations.get(candidates[0].name), table_id)
            if table.primary_key.columns:
                mapped_pk = [cols[c].target for c in table.primary_key.columns if c in cols and not cols[c].ignored]
                equal('primary_key', mapped_pk, dest.primary_key.columns, table_id)
            for fk in table.foreign_keys:
                parent = mappings.get(fk.target_table)
                parent_cols = {c.source: c.target for c in parent.columns if not c.ignored} if parent else {}
                mapped_child = [cols[c].target for c in fk.columns if c in cols and not cols[c].ignored]
                mapped_parent = [parent_cols[c] for c in fk.target_columns if c in parent_cols]
                equivalents = [f for f in dest.foreign_keys if parent and f.target_table == parent.target and f.columns == mapped_child and f.target_columns == mapped_parent]
                zero('source_fk:' + fk.name, sp.orphans.get(fk.name), table_id)
                if not equivalents or len(mapped_child) != len(fk.columns) or len(mapped_parent) != len(fk.target_columns):
                    finding('foreign_key:' + fk.name, 'inconclusive', 'FK sem equivalente verificável no destino.', table_id)
                else:
                    zero('target_fk:' + fk.name, tp.orphans.get(equivalents[0].name), table_id)
            for fk in dest.foreign_keys:
                zero('target_integrity:' + fk.name, tp.orphans.get(fk.name), table_id)
        mapped_targets = {m.target for m in manifest.mappings if m.confirmed and not m.ignored}
        for extra in targets.keys() - mapped_targets:
            finding('target_unmapped', 'inconclusive', 'Tabela de destino sem origem mapeada; revise o escopo.', extra)
    run.table_coverage = 100 * table_covered / len(sources) if sources else 0
    run.column_coverage = 100 * column_covered / total_columns if total_columns else 0
    run.finished_at = now()
    run.stages.append(Stage('comparison', run.status, run.started_at, run.finished_at))
    return run
