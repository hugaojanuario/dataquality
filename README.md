# DataQuality

Ferramenta open source para auditar migrações entre CSV, Firebird e PostgreSQL.
Executa regras com PySpark e gera um relatório HTML com contagens e amostras.

## Requisitos

- Python 3.11
- Java 17
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

A interface recebe host, porta, banco, usuário, senha, tabela, chave e drivers JDBC.
As senhas ficam somente em memória e não entram no relatório.

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

    pytest -v

## Executável Windows

    Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
    .\scripts\build-executable.ps1

O resultado será dist\dataqualy.exe. O computador ainda precisa de Java 17 e
dos drivers JDBC selecionados na interface.

## Privacidade

Dados, credenciais, nomes de clientes, estruturas proprietárias e arquivos reais
não devem entrar no repositório. Use somente exemplos genéricos e sintéticos.

## Licença

MIT.

<!-- @hugaojanuario -->
