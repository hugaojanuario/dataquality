import os
from pathlib import Path

import yaml

from .connectors import JDBCConnector
from .domain import CaptureOptions, ConnectionProfile, Manifest
from .inventory import capture
from .mapping import suggest
from .checks import compare
from .orchestration import Workflow
from .reporting import write_report
from .storage import decode, load, save


def add_commands(subcommands):
    audit = subcommands.add_parser('audit', help='Auditoria determinística de banco inteiro.')
    commands = audit.add_subparsers(dest='audit_command', required=True)
    demo = commands.add_parser('demo', help='Fluxo sintético completo sem Java ou banco.')
    demo.add_argument('--project', required=True)
    capture_parser = commands.add_parser('capture', help='Captura independente ou etapa de projeto.')
    capture_parser.add_argument('--config', required=True)
    capture_parser.add_argument('--role', choices=['source', 'baseline', 'target'], required=True)
    capture_parser.add_argument('--project')
    capture_parser.add_argument('--output')
    capture_parser.add_argument('--run-id')
    capture_parser.add_argument('--profile', choices=['fast', 'balanced', 'exhaustive'], default='balanced')
    capture_parser.add_argument('--key-env', default='SINCRO_EVIDENCE_KEY')
    capture_parser.add_argument('--include-system', action='store_true')
    capture_parser.add_argument('--quiescent', action='store_true', help='Confirma que escritas foram suspensas durante a captura.')
    capture_parser.add_argument('--keys', help='JSON de table-id -> lista de colunas (chaves sem PK).')
    mapping = commands.add_parser('suggest', help='Gera sugestões não confirmadas.')
    mapping.add_argument('--source', required=True)
    mapping.add_argument('--baseline', required=True)
    mapping.add_argument('--output', required=True)
    comp = commands.add_parser('compare', help='Compara snapshots locais, sem conexão.')
    comp.add_argument('--source', required=True)
    comp.add_argument('--baseline', required=True)
    comp.add_argument('--target', required=True)
    comp.add_argument('--mapping', required=True)
    comp.add_argument('--report', default='reports/audit.html')


def read_connection(path):
    try:
        config = yaml.safe_load(Path(path).read_text(encoding='utf-8'))
        if not isinstance(config, dict) or 'password' in config:
            raise ValueError()
        return decode(ConnectionProfile, config)
    except Exception:
        raise ValueError('Perfil inválido. Use campos de conexão e password_env; nunca senha no YAML.') from None


def run(args):
    try:
        if args.audit_command == 'demo':
            from .synthetic import demo
            report, path = demo(args.project)
        elif args.audit_command == 'capture':
            if bool(args.project) == bool(args.output) or (args.output and not args.run_id):
                raise ValueError('Use --project OU --output com --run-id.')
            options = CaptureOptions(profile=args.profile, include_system=args.include_system, quiescent=args.quiescent)
            if args.keys:
                import json
                options.keys = decode(dict[str, list[str]], json.loads(Path(args.keys).read_text()))
            from threading import Event
            import signal
            cancellation = Event()
            previous = signal.signal(signal.SIGINT, lambda *_: cancellation.set())
            connector = None
            try:
                connector = JDBCConnector(read_connection(args.config), cancel=cancellation)
                if args.project:
                    snapshot = Workflow(args.project).capture(args.role, connector, options=options, secret=os.getenv(args.key_env), progress=print, cancel=cancellation)
                else:
                    snapshot = capture(connector, run_id=args.run_id, role=args.role, path=args.output, options=options, secret=os.getenv(args.key_env), progress=print, cancel=cancellation)
            finally:
                if connector:
                    connector.close()
                signal.signal(signal.SIGINT, previous)
            print('Captura concluída.' if snapshot.complete else 'Captura incompleta; consulte findings no snapshot.')
            return 0 if snapshot.complete else 2
        elif args.audit_command == 'suggest':
            if Path(args.output).exists():
                raise ValueError('Manifesto já existe; edite-o para preservar a revisão.')
            save(args.output, suggest(load(args.source), load(args.baseline)))
            print('Sugestões salvas. Revise e marque confirmed: true no JSON.')
            return 0
        else:
            report = compare(load(args.source), load(args.baseline), load(args.target), load(args.mapping, Manifest), source_dir=Path(args.source).parent, target_dir=Path(args.target).parent)
            path = write_report(report, args.report)
        print(f'Resultado: {report.status}. Relatório: {path}')
        return {'passed': 0, 'failed': 1, 'error': 2, 'inconclusive': 3, 'skipped': 3}[report.status]
    except Exception:
        print('Erro na auditoria. Verifique argumentos, perfis/JAR, variáveis de ambiente, permissões e ordem das etapas. Nenhuma aprovação emitida.')
        return 2
