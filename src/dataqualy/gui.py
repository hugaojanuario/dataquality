import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Any

from dataqualy.report import write_html_report
from dataqualy.validator import run_validation


def build_database_config(values: dict[str, str]) -> dict[str, Any]:
    """Monta a configuração em memória; a senha nunca é salva em arquivo."""
    compare_columns = [
        item.strip()
        for item in values["compare_columns"].split(",")
        if item.strip()
    ]
    return {
        "migration": {"name": values["migration_name"] or "validation"},
        "source": {
            "type": "jdbc", "engine": "firebird",
            "host": values["source_host"], "port": int(values["source_port"] or "3050"),
            "database": values["source_database"], "user": values["source_user"],
            "password": values["source_password"], "table": values["source_table"],
            "jar": values["source_jar"],
        },
        "target": {
            "type": "jdbc", "engine": "postgresql",
            "host": values["target_host"], "port": int(values["target_port"] or "5432"),
            "database": values["target_database"], "user": values["target_user"],
            "password": values["target_password"], "table": values["target_table"],
            "jar": values["target_jar"],
        },
        "key": values["key"],
        "checks": {
            "duplicate_keys": True,
            "missing_records": True,
            "compare_columns": compare_columns,
        },
        "report": {"sample_size": 0},
    }


class DataQualyApp(tk.Tk):
    """Interface local para validar Firebird contra PostgreSQL."""

    FIELDS = (
        ("migration_name", "Nome da migração", ""),
        ("source_host", "Firebird - host", "localhost"),
        ("source_port", "Firebird - porta", "3050"),
        ("source_database", "Firebird - banco/caminho", ""),
        ("source_user", "Firebird - usuário", "SYSDBA"),
        ("source_password", "Firebird - senha", ""),
        ("source_table", "Firebird - tabela ou view", ""),
        ("source_jar", "Firebird - driver JDBC (.jar)", ""),
        ("target_host", "PostgreSQL - host", "localhost"),
        ("target_port", "PostgreSQL - porta", "5432"),
        ("target_database", "PostgreSQL - banco", ""),
        ("target_user", "PostgreSQL - usuário", ""),
        ("target_password", "PostgreSQL - senha", ""),
        ("target_table", "PostgreSQL - tabela ou view", ""),
        ("target_jar", "PostgreSQL - driver JDBC (.jar)", ""),
        ("key", "Chave de comparação", "id"),
        ("compare_columns", "Colunas (separadas por vírgula)", ""),
    )

    def __init__(self) -> None:
        super().__init__()
        self.title("DataQualy")
        self.geometry("760x760")
        self.variables: dict[str, tk.StringVar] = {}
        self._build()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(
            frame, text="Validação Firebird → PostgreSQL",
            font=("Segoe UI", 16, "bold"),
        ).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 14))
        for row, (name, label, default) in enumerate(self.FIELDS, start=1):
            variable = tk.StringVar(value=default)
            self.variables[name] = variable
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", pady=3)
            show = "*" if "password" in name else ""
            ttk.Entry(frame, textvariable=variable, show=show, width=58).grid(
                row=row, column=1, sticky="ew", pady=3
            )
            if name.endswith("_jar"):
                ttk.Button(
                    frame, text="Selecionar",
                    command=lambda key=name: self._select_jar(key),
                ).grid(row=row, column=2, padx=(6, 0))
        self.status = tk.StringVar(value="Pronto.")
        self.run_button = ttk.Button(
            frame, text="Executar validação", command=self._start_validation
        )
        self.run_button.grid(row=len(self.FIELDS) + 1, column=0, columnspan=3, pady=18)
        ttk.Label(frame, textvariable=self.status).grid(
            row=len(self.FIELDS) + 2, column=0, columnspan=3, sticky="w"
        )
        frame.columnconfigure(1, weight=1)

    def _select_jar(self, key: str) -> None:
        path = filedialog.askopenfilename(filetypes=[("Java archive", "*.jar")])
        if path:
            self.variables[key].set(path)

    def _start_validation(self) -> None:
        values = {key: variable.get() for key, variable in self.variables.items()}
        self.run_button.state(["disabled"])
        self.status.set("Executando validações...")
        threading.Thread(target=self._run_validation, args=(values,), daemon=True).start()

    def _run_validation(self, values: dict[str, str]) -> None:
        try:
            report = run_validation(build_database_config(values))
            output = write_html_report(report, Path("reports/validation-report.html"))
            message = (
                "Validação aprovada." if report.passed
                else f"{report.issue_count} divergência(s) encontrada(s)."
            )
            self.after(0, self._finish, message, str(output.resolve()), None)
        except Exception:
            self.after(0, self._finish, "", "", "Falha na validação. Verifique conexão, driver, permissões e configuração.")

    def _finish(self, message: str, output: str, error: str | None) -> None:
        self.run_button.state(["!disabled"])
        if error:
            self.status.set("Falha na validação.")
            messagebox.showerror("DataQualy", error)
            return
        self.status.set(f"{message} Relatório: {output}")
        messagebox.showinfo("DataQualy", f"{message}\n\nRelatório: {output}")


def launch_gui() -> None:
    """Abre a interface gráfica local."""
    from dataqualy.desktop.app import launch_gui as launch_desktop
    launch_desktop()


# @hugaojanuario
