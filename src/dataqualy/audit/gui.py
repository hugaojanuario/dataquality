"""Tk workflow: all I/O in workers; widgets exclusively on the main thread."""
from dataclasses import asdict
import json
import os
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
import webbrowser

from .connectors import JDBCConnector
from .domain import CaptureOptions, ConnectionProfile, Manifest, Snapshot
from .engines import ENGINES
from .mapping import suggest, validate_manifest
from .orchestration import Workflow
from .storage import decode, load, save


class Worker:
    def __init__(self):
        self.events, self.cancel = Queue(), Event()
        self.thread = self.connector = None

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def start(self, action):
        if self.busy:
            return False
        self.cancel.clear()

        def execute():
            try:
                self.events.put(('done', action()))
            except Exception:
                self.events.put(('error', 'Operação incompleta. Confira conexão, JAR, variáveis, permissões, manifesto e ordem das etapas.'))
            finally:
                if self.connector:
                    self.connector.close()
                    self.connector = None
        self.thread = Thread(target=execute, daemon=True)
        self.thread.start()
        return True

    def stop(self):
        self.cancel.set()
        connector = self.connector
        if connector and hasattr(connector, 'cancel'):
            Thread(target=connector.cancel, daemon=True).start()

    def progress(self, message):
        self.events.put(('progress', message))


class AuditApp(tk.Tk):
    TABS = ('Projeto', 'Origem', 'Destino', 'Descoberta', 'Mapeamento', 'Captura antes', 'Validação depois', 'Resultado')

    def __init__(self):
        super().__init__()
        self.title('DataQuality — auditoria de migração')
        self.geometry('1060x760')
        self.worker, self.closing, self.discovery, self.report_path = Worker(), False, {}, None
        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill='both', expand=True, padx=12, pady=12)
        self.tabs = {}
        for name in self.TABS:
            self.tabs[name] = ttk.Frame(self.notebook, padding=16)
            self.notebook.add(self.tabs[name], text=name)
        self.directory = tk.StringVar(value=str(Path('reports') / 'audit-project'))
        self.profile, self.key_env = tk.StringVar(value='balanced'), tk.StringVar(value='DATAQUALY_EVIDENCE_KEY')
        self.quiescent, self.include_system = tk.BooleanVar(), tk.BooleanVar()
        self.status = tk.StringVar(value='Crie um projeto, conecte e descubra os bancos.')
        self._project_tab()
        self.connections = {side: self._connection_tab(side, label, engine) for side, label, engine in (('source', 'Origem', 'firebird'), ('target', 'Destino', 'postgresql'))}
        frame = self.tabs['Descoberta']
        ttk.Button(frame, text='Descobrir todas as tabelas nos dois bancos', command=lambda: self._execute('discover')).pack(anchor='w')
        self.tree = ttk.Treeview(frame, columns=('side', 'name', 'columns'), show='headings')
        for name, label in (('side', 'Lado'), ('name', 'Tabela'), ('columns', 'Colunas')):
            self.tree.heading(name, text=label)
        self.tree.pack(fill='both', expand=True, pady=10)
        ttk.Button(frame, text='Excluir tabela de origem selecionada com justificativa', command=self._exclude).pack(anchor='w')
        frame = self.tabs['Mapeamento']
        ttk.Label(frame, text='Revise o JSON: tabelas/colunas, chaves, ignored + justification e confirmed: true.\nFiltros e transformações ficam inconclusivos nesta versão.').pack(anchor='w')
        controls = ttk.Frame(frame)
        controls.pack(fill='x', pady=8)
        ttk.Button(controls, text='Gerar sugestões', command=self._suggest).pack(side='left')
        for action, label in (('load_mapping', 'Carregar manifesto'), ('save_mapping', 'Salvar manifesto revisado')):
            ttk.Button(controls, text=label, command=lambda a=action: self._execute(a)).pack(side='left', padx=8)
        self.editor = tk.Text(frame, wrap='none', undo=True)
        self.editor.pack(fill='both', expand=True)
        frame = self.tabs['Captura antes']
        ttk.Label(frame, text='1. Capture a origem. 2. Capture o destino vazio.\nDepois execute seu conversor externamente. Guarde a mesma chave HMAC fora do projeto.').pack(anchor='w')
        for action, label in (('source', 'Capturar origem'), ('baseline', 'Capturar baseline do destino vazio')):
            ttk.Button(frame, text=label, command=lambda a=action: self._execute(a)).pack(anchor='w', pady=12)
        frame = self.tabs['Validação depois']
        ttk.Label(frame, text='Após a conversão externa, suspenda escritas no destino e capture novamente.').pack(anchor='w')
        for action, label in (('target', 'Capturar destino convertido e gerar relatório'), ('report', 'Comparar snapshots já salvos')):
            ttk.Button(frame, text=label, command=lambda a=action: self._execute(a)).pack(anchor='w', pady=12)
        self.result_text = tk.StringVar(value='Nenhuma auditoria executada.')
        ttk.Label(self.tabs['Resultado'], textvariable=self.result_text, wraplength=850).pack(anchor='w')
        ttk.Button(self.tabs['Resultado'], text='Abrir relatório HTML', command=self._open_report).pack(anchor='w', pady=12)
        bottom = ttk.Frame(self, padding=12)
        bottom.pack(fill='x')
        ttk.Label(bottom, textvariable=self.status, wraplength=850).pack(side='left')
        ttk.Button(bottom, text='Cancelar', command=self.worker.stop).pack(side='right')
        self.protocol('WM_DELETE_WINDOW', self._close)
        self.after(100, self._poll)

    def _project_tab(self):
        frame = self.tabs['Projeto']
        ttk.Label(frame, text='Diretório local (um por execução)').pack(anchor='w')
        ttk.Entry(frame, textvariable=self.directory, width=90).pack(fill='x', pady=8)
        ttk.Button(frame, text='Escolher diretório', command=self._choose_directory).pack(anchor='w')
        ttk.Label(frame, text='fast = contagens/nulos; balanced = agregados; exhaustive = evidências por chave.').pack(anchor='w', pady=(20, 4))
        ttk.Combobox(frame, textvariable=self.profile, values=('fast', 'balanced', 'exhaustive'), state='readonly').pack(anchor='w')
        ttk.Label(frame, text='Variável de ambiente com chave HMAC aleatória (mínimo 32 bytes)').pack(anchor='w', pady=(16, 4))
        ttk.Entry(frame, textvariable=self.key_env, width=50).pack(anchor='w')
        ttk.Checkbutton(frame, text='Confirmo que as escritas estão suspensas durante as capturas', variable=self.quiescent).pack(anchor='w', pady=14)
        ttk.Checkbutton(frame, text='Incluir tabelas/schemas de sistema', variable=self.include_system).pack(anchor='w')
        ttk.Label(frame, text='Sem evidências completas, resultado inconclusive. Senhas permanecem em memória.\nFluxo anterior por tabela: dataqualy gui-legacy.').pack(anchor='w', pady=24)

    def _choose_directory(self):
        directory = filedialog.askdirectory()
        if directory:
            self.directory.set(directory)

    def _connection_tab(self, side, label, engine):
        frame, values = self.tabs[label], {}
        defaults = {'engine': engine, 'host': 'localhost', 'port': str(ENGINES[engine].port), 'database': '', 'user': '', 'password': '', 'jar': ''}
        labels = ('Banco', 'Host', 'Porta', 'Banco / caminho Firebird', 'Usuário somente leitura', 'Senha (somente memória)', 'Driver JDBC (.jar)')
        for row, ((key, default), label) in enumerate(zip(defaults.items(), labels)):
            values[key] = tk.StringVar(value=default)
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky='w', pady=6)
            if key == 'engine':
                widget = ttk.Combobox(frame, textvariable=values[key], values=list(ENGINES), state='readonly')
                widget.bind('<<ComboboxSelected>>', lambda _: values['port'].set(str(ENGINES[values['engine'].get()].port)))
            else:
                widget = ttk.Entry(frame, textvariable=values[key], show='*' if key == 'password' else '', width=65)
            widget.grid(row=row, column=1, sticky='ew')
        ttk.Button(frame, text='Selecionar JAR', command=lambda: self._jar(values)).grid(row=7, column=1, sticky='w', pady=10)
        ttk.Button(frame, text='Testar conexão', command=lambda: self._execute('test_' + side)).grid(row=8, column=1, sticky='w')
        frame.columnconfigure(1, weight=1)
        return values

    def _jar(self, values):
        path = filedialog.askopenfilename(filetypes=[('Driver JDBC', '*.jar')])
        if path:
            values['jar'].set(path)

    def _set_manifest(self, manifest):
        self.editor.delete('1.0', 'end')
        self.editor.insert('1.0', json.dumps(asdict(manifest), ensure_ascii=False, indent=2))

    def _suggest(self):
        if not all(k in self.discovery for k in ('source', 'target')):
            messagebox.showerror('DataQuality', 'Descubra os dois bancos primeiro.')
        elif self.editor.get('1.0', 'end').strip():
            messagebox.showinfo('DataQuality', 'O editor contém revisão. Edite-a ou limpe o texto para gerar novamente.')
        else:
            self._set_manifest(suggest(self.discovery['source'], self.discovery['target']))

    def _exclude(self):
        selected = self.tree.selection()
        if not selected or not selected[0].startswith('source:'):
            messagebox.showinfo('DataQuality', 'Selecione uma tabela da origem.')
            return
        justification = simpledialog.askstring('Exclusão', 'Justificativa (não inclua dados pessoais):')
        if not justification or not justification.strip():
            return
        try:
            manifest = decode(Manifest, json.loads(self.editor.get('1.0', 'end')))
            table_id = self.discovery['source'].tables[int(selected[0].split(':')[1])].id
            mapping = next(m for m in manifest.mappings if m.source == table_id)
            mapping.ignored, mapping.justification, mapping.confirmed = True, justification, True
            self._set_manifest(manifest)
        except Exception:
            messagebox.showerror('DataQuality', 'Gere sugestões no Mapeamento e tente novamente.')

    def _execute(self, action):
        if self.worker.busy:
            return
        # Read all widgets before starting the worker.
        directory = self.directory.get()
        connections = {s: {k: v.get() for k, v in values.items()} for s, values in self.connections.items()}
        options = CaptureOptions(profile=self.profile.get(), include_system=self.include_system.get(), quiescent=self.quiescent.get())
        secret, text = os.getenv(self.key_env.get()), self.editor.get('1.0', 'end')

        def connect(side):
            values = dict(connections[side])
            password = values.pop('password')
            values['port'] = int(values['port'] or ENGINES[values['engine']].port)
            connector = JDBCConnector(ConnectionProfile(**values), password, self.worker.cancel)
            self.worker.connector = connector
            return connector

        def execute():
            workflow = Workflow(directory)
            if action.startswith('test_'):
                connect(action.removeprefix('test_'))
                return ('message', 'Conexão estabelecida. Descubra as tabelas para verificar permissões de catálogo.')
            if action == 'discover':
                snapshots = {}
                for side in ('source', 'target'):
                    connector = connect(side)
                    try:
                        snapshots[side] = Snapshot(workflow.project.run_id, side, connector.engine, tables=connector.discover(options))
                    finally:
                        connector.close()
                return ('discovery', snapshots)
            if action == 'load_mapping':
                return ('mapping', load(workflow.directory / 'mapping.json', Manifest))
            if action == 'save_mapping':
                manifest = decode(Manifest, json.loads(text))
                validate_manifest(manifest)
                save(workflow.directory / 'mapping.json', manifest)
                return ('message', 'Manifesto salvo. Confirme cada tabela após revisar as colunas.')
            if action in ('source', 'baseline', 'target'):
                if text.strip():
                    manifest = decode(Manifest, json.loads(text))
                    validate_manifest(manifest)
                    save(workflow.directory / 'mapping.json', manifest)
                    for mapping in manifest.mappings:
                        if not mapping.ignored:
                            keys = mapping.source_key if action == 'source' else mapping.target_key
                            table = mapping.source if action == 'source' else mapping.target
                            if keys and table:
                                options.keys[table] = keys
                connector = connect('source' if action == 'source' else 'target')
                snapshot = workflow.capture(action, connector, options=options, secret=secret, progress=self.worker.progress, cancel=self.worker.cancel)
                if not snapshot.complete:
                    return ('message', 'Captura incompleta. Consulte findings no snapshot e refaça a etapa.')
                if action != 'target':
                    return ('message', f'Captura {action} salva. Continue para a próxima etapa.')
            return ('report', workflow.report(cancel=self.worker.cancel))
        self.status.set('Executando... Cancelamento será aplicado na consulta/lote em andamento.')
        self.worker.start(execute)

    def _poll(self):
        try:
            while True:
                event, payload = self.worker.events.get_nowait()
                if event in ('progress', 'error'):
                    self.status.set(payload)
                    continue
                kind, value = payload
                self.status.set('Operação concluída.')
                if kind == 'discovery':
                    self.discovery = value
                    self.tree.delete(*self.tree.get_children())
                    for side, snapshot in value.items():
                        for i, table in enumerate(snapshot.tables):
                            self.tree.insert('', 'end', iid=f'{side}:{i}', values=(side, table.id, len(table.columns)))
                elif kind == 'mapping':
                    self._set_manifest(value)
                elif kind == 'report':
                    run, self.report_path = value
                    self.result_text.set(f'Resultado: {run.status}\nQualidade: {run.quality}\nCobertura de tabelas: {run.table_coverage:.1f}% / colunas: {run.column_coverage:.1f}%\nRelatório: {self.report_path}')
                    self.notebook.select(self.tabs['Resultado'])
                else:
                    self.status.set(value)
        except Empty:
            pass
        if self.closing and not self.worker.busy:
            self.destroy()
        else:
            self.after(100, self._poll)

    def _open_report(self):
        if self.report_path:
            webbrowser.open(Path(self.report_path).resolve().as_uri())

    def _close(self):
        self.closing = True
        self.worker.stop()
        self.status.set('Cancelando e fechando recursos...')
