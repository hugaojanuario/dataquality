import argparse
from collections.abc import Sequence

from dataqualy.config import load_config
from dataqualy.package_validator import run_package_validation
from dataqualy.report import write_html_report
from dataqualy.validator import run_validation


def build_parser() -> argparse.ArgumentParser:
    """Cria os comandos públicos do DataQualy."""
    parser = argparse.ArgumentParser(prog="dataqualy", description="Validador de migrações.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    validate = subcommands.add_parser("validate", help="Valida usando um YAML.")
    validate.add_argument("--config", required=True, help="Arquivo YAML.")
    validate.add_argument(
        "--report", default="reports/validation-report.html",
        help="Caminho do relatório HTML.",
    )
    gui = subcommands.add_parser("gui", help="Abre a interface moderna Qt Quick.")
    gui.add_argument('--demo', action='store_true', help='Dados sintéticos, sem banco.')
    gui.add_argument('--project', default='', help='Diretório do projeto existente ou novo.')
    gui.add_argument('--screenshots', default='', help='Captura visual automática (exige --demo).')
    subcommands.add_parser("gui-audit-legacy", help="Abre a auditoria anterior em Tkinter.")
    subcommands.add_parser("gui-legacy", help="Abre a interface original por tabela.")
    from dataqualy.audit.cli import add_commands
    add_commands(subcommands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Executa a interface de linha de comando."""
    args = build_parser().parse_args(argv)
    if args.command == 'audit':
        from dataqualy.audit.cli import run
        return run(args)
    if args.command == 'gui-legacy':
        from dataqualy.gui import DataQualyApp
        DataQualyApp().mainloop()
        return 0
    if args.command == 'gui-audit-legacy':
        from dataqualy.audit.gui import AuditApp
        AuditApp().mainloop()
        return 0
    if args.command == "gui":
        if args.screenshots and not args.demo:
            print('--screenshots exige --demo para impedir exposição de dados reais.')
            return 2
        from dataqualy.desktop.app import launch_gui
        return launch_gui(demo=args.demo, project=args.project, screenshots=args.screenshots)
    if args.command == "validate":
        try:
            config = load_config(args.config)
            report = (
                run_package_validation(config)
                if config.get("mode") == "package"
                else run_validation(config)
            )
        except Exception:
            print("Validação incompleta. Verifique configuração, acesso às fontes e drivers.")
            return 2
        output = write_html_report(report, args.report)
        print(f"Relatório: {output.resolve()}")
        print(
            "Resultado: aprovado"
            if report.passed
            else f"Resultado: {report.issue_count} divergência(s)"
        )
        return 0 if report.passed else 1
    return 2


# @hugaojanuario
