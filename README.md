# DataQuality

Ferramenta Python 3.11/MIT para auditar migrações localmente, sem depender de IA.
Pacote e executável: `dataqualy`. Preserva CSV, regras PySpark e pacotes/anexos;
adiciona auditoria de banco inteiro com snapshots, mapeamento e evidências redigidas.

## Quick start — exemplo totalmente sintético

```sh
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,jdbc]"
dataqualy audit demo --project reports/synthetic-demo
```

Abra `reports/synthetic-demo/report.html`. O exemplo executa origem → baseline
vazia → destino convertido → comparação → relatório, com conectores em memória,
sem Java, banco, conversor ou IA. Use outro diretório para repetir uma execução.

## Banco inteiro — Firebird → PostgreSQL

Edite `configs/audit-firebird.yml` e `configs/audit-postgresql.yml` com conexões de
teste. Use usuários com SELECT e acesso a todos os metadados do escopo. Defina
`DATAQUALY_SOURCE_PASSWORD` e `DATAQUALY_TARGET_PASSWORD` no ambiente; nunca em YAML.
Defina também `DATAQUALY_EVIDENCE_KEY` com chave aleatória de pelo menos 32 bytes
(por exemplo, saída de `python -c "import secrets; print(secrets.token_hex(32))"`).
Mantenha a mesma chave nas capturas e guarde-a fora dos artefatos/repositório.

Suspenda escritas durante as capturas. `--quiescent` registra sua confirmação;
o programa não suspende aplicações nem oferece snapshot global entre bancos.

```sh
dataqualy audit capture --project reports/run-1 --role source --config configs/audit-firebird.yml --profile exhaustive --quiescent
dataqualy audit capture --project reports/run-1 --role baseline --config configs/audit-postgresql.yml --profile balanced --quiescent
dataqualy audit suggest --source reports/run-1/source.json --baseline reports/run-1/baseline.json --output reports/run-1/mapping.json
```

Revise `mapping.json`: destinos, colunas e chaves compostas; marque cada tabela
revisada com `"confirmed": true`. Exclusões exigem `"ignored": true` e justificativa.
Não confirme sugestão ambígua. IDs de tabelas são strings JSON `[catalog,schema,name]`.

Execute seu conversor **externamente**. Depois:

```sh
dataqualy audit capture --project reports/run-1 --role target --config configs/audit-postgresql.yml --profile exhaustive --quiescent
dataqualy audit compare --source reports/run-1/source.json --baseline reports/run-1/baseline.json --target reports/run-1/target.json --mapping reports/run-1/mapping.json --report reports/run-1/report.html
```

Para capturas independentes use `--output arquivo.json --run-id identificador` em
vez de `--project`. Se não houver PK, use `--keys chaves.json`, mapa de ID de tabela
para lista de colunas. Compare snapshots salvos sem banco e sem chave HMAC, mantendo
os arquivos `.sqlite` ao lado dos respectivos JSON.

Estados: `passed`, `failed`, `inconclusive`, `error`, `skipped`. Saída da comparação:
0 aprovado no escopo; 1 divergência; 2 erro; 3 inconclusivo. Sucesso de `capture`
significa captura concluída, não migração aprovada. `fast` e `balanced` não comprovam
igualdade de registros. Sem chave HMAC, manifesto completo e evidência suficiente,
não há aprovação global. O relatório separa qualidade observada e cobertura.

## Suporte desta fatia

| Engine | URL/driver | Descoberta e perfis JDBC | Comparação determinística | Validação real |
|---|---|---|---|---|
| Firebird | Jaybird / 3050 | Implementados | Tipos suportados, chaves simples/compostas | Integração opcional |
| PostgreSQL | pgJDBC / 5432 | Implementados | Tipos suportados, chaves simples/compostas | Integração opcional |
| SQL Server | Microsoft JDBC / 1433 | Implementados pelo contrato JDBC; experimentais | Mesma matriz conservadora | Integração opcional |
| MySQL | Connector/J / 3306 | Implementados pelo contrato JDBC; experimentais | Mesma matriz conservadora | Integração opcional |

Testes unitários validam descoberta, SQL, falhas e fluxo completo sem bancos reais.
Compatibilidade real depende da versão do banco/JAR e permissões. Não há validação
de instâncias reais implícita nesta matriz.

## Arquitetura e limites

`dataqualy.audit`: conectores → inventário/snapshot → mapeamento → checks →
orquestração → relatório. Contratos de conversor e IA são portas isoladas e não
participam da decisão. Consulte [arquitetura, privacidade e limites](docs/audit-architecture.md)
e [protocolo público JSON Lines](docs/conversion-protocol.md).

Compara existência/tipos, contagens, chaves, ausentes/extras, nulidade, distintos,
extremos HMAC, unicidade, FKs e valores por chave. Usa agregados, cursor JDBC e SQLite
de digests em disco; não carrega tabelas inteiras em memória. A evidência exaustiva
pode ocupar bastante disco e exige varreduras completas.

Floats, timestamps/timezone, binários, LOBs e textos grandes/ilimitados não têm
canonicalização segura nesta versão. Filtros, transformações e comparadores
customizados podem ser declarados, mas ficam inconclusivos. Views, triggers,
procedures, sequences, permissões e regras SQL especiais estão fora do escopo.
Não há promessa de garantia total nem mecanismo antifraude de artefatos.

## Requisitos

- Python 3.11
- Java 17 para JDBC e testes/regras Spark (configure JAVA_HOME se necessário)
- Drivers JDBC do Firebird e PostgreSQL para conexões com bancos

## Instalação

    python -m venv .venv
    python -m pip install -e ".[dev]"

No Windows:

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\.venv\Scripts\Activate.ps1

## Terminal

    dataqualy validate --config configs/example.yml

Também funciona com:

    python -m dataqualy validate --config configs/example.yml

O comando retorna código 0 quando aprovado e 1 quando encontra divergências.
O relatório padrão fica em reports/validation-report.html.

## Interface gráfica

    dataqualy gui

A interface tem oito abas: projeto, conexões, descoberta, revisão do manifesto,
capturas antes/depois e resultado. Conexão, descoberta e auditoria rodam em worker,
com progresso e cancelamento cooperativo. O editor de mapeamento usa JSON nesta rodada.
O fluxo anterior por tabela continua disponível em `dataqualy gui-legacy`.
Senhas ficam somente em memória. Tkinter precisa estar instalado no Python utilizado.

## Configuração e regras

Use type: csv para arquivos. Para bancos use type: jdbc, engine: firebird ou
postgresql e informe exatamente table ou query. Prefira password_env; nunca
versione senha.

Regras disponíveis:

- chaves duplicadas e registros ausentes;
- diferenças entre valores;
- campos obrigatórios;
- domínios e expressões regulares;
- datas inválidas;
- registros órfãos;
- caracteres inválidos e prefixos antes de RTF.

Veja configs/jdbc-example.yml e configs/rules-example.yml.

## Validação de pacote antes da importação

O modo `package` verifica os arquivos extraídos antes de carregar dados no banco:

- existência de cada CSV;
- codificação válida e ausência de BOM UTF-8;
- nomes e ordem exata das colunas;
- existência dos anexos relacionados no manifesto;
- proteção contra caminhos que saiam da pasta de anexos;
- tamanho e hash dos anexos, quando informados.

Copie `configs/package-example.yml`, ajuste os caminhos e cabeçalhos para o
layout utilizado e execute:

    dataqualy validate --config configs/package-example.yml

O manifesto de anexos deve possuir a coluna configurada em `path_column`. As
colunas de tamanho e hash são opcionais; quando preenchidas, também serão
comparadas com o arquivo físico.

## Testes

```sh
python -m pytest -v
python -m compileall -q src tests
```

Integrações reais são opcionais, marcadas `integration`: defina
`DATAQUALY_INTEGRATION_FIREBIRD_CONFIG`, `DATAQUALY_INTEGRATION_POSTGRESQL_CONFIG`,
`DATAQUALY_INTEGRATION_SQLSERVER_CONFIG` ou `DATAQUALY_INTEGRATION_MYSQL_CONFIG`
com caminho de perfil YAML local, JAR e variável de senha. Prepare apenas tabelas
sintéticas em instância/container descartável. Execute `pytest -m integration -v`.
Sem essas variáveis, os quatro casos são pulados com motivo explícito.

Para testar somente a fatia sem iniciar Spark: `pytest tests/test_audit*.py -v`.

## Executável Windows

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\scripts\build-executable.ps1

O resultado será dist\dataqualy.exe. O computador ainda precisa de Java 17 e
dos drivers JDBC selecionados na interface.

## Privacidade

Dados, credenciais, nomes de clientes, estruturas proprietárias e arquivos reais
não devem entrar no repositório. Use somente exemplos genéricos e sintéticos.
Na nova auditoria, amostras reais ficam desativadas e extremos são HMAC. No YAML
legado, `sample_size` passa a 0 por padrão; quando solicitado, limita a 20 e mascara
valores. Relatório vazio deixou de aprovar. Demais comandos/configurações permanecem.

## Licença

MIT.

<!-- @hugaojanuario -->
