# Desktop DataQuality

## Estado encontrado e entrega

A versão 0.2.0 já continha dois fluxos Tkinter: validação por tabela/pacote e
uma auditoria por snapshots. O domínio já oferecia quatro engines JDBC, perfis
fast/balanced/exhaustive, inventário de PK/FK, manifesto revisável, comparação
conservadora, evidências HMAC/SQLite e HTML. Os contratos de conversor/IA existem,
mas não participam da aprovação e não foram adicionados à interface.

Esta rodada migra apenas a apresentação para Qt Quick. O motor em `audit/`,
regras Spark, leitores, formatos e comandos de validação não foram reescritos.

## Organização

- `desktop/app.py`: inicialização, carregamento QML e ciclo de vida.
- `desktop/viewmodel.py`: propriedades tipadas, comandos, filtros e revisão visual;
  `ConnectionViewModel` mantém a senha fora do estado público.
- `desktop/service.py`: chamadas a `Workflow`, `JDBCConnector`, `suggest`,
  `validate_manifest`, `compare` e armazenamento existentes. Executa fora da UI.
- `desktop/demo.py`: fixtures sintéticas via `MemoryConnector` e motor real.
- `desktop/qml/Tokens.qml`: cores, tipografia, espaçamentos, raios e animações.
- `desktop/qml/components/`: componentes reutilizáveis e ícones vetoriais próprios.
- `desktop/qml/pages/`: apresentação das sete áreas e resultado.
- `desktop/native.py`: backdrop Mica opcional no Windows 11 build 22621+;
  outros sistemas usam superfícies e sombras QML. Sem APIs privadas de blur.
- `desktop/screenshots.py`: captura de todas as telas, temas e dimensões.

QML não acessa banco nem decide aprovação. O JavaScript limita-se a apresentação,
encaminhamento de eventos e desenho vetorial. Threads recebem cópias dos dados;
nenhum worker lê widgets ou altera o modelo Qt. Sinais queued entregam resultados
na thread principal. O pool aceita uma operação por vez.

## Operação, cancelamento e privacidade

Cancelar ativa o `Event` consumido pelo motor e tenta `Statement.cancel()` numa
thread separada. Não se mata uma thread. Conexão e metadados JDBC podem aguardar
o timeout de rede do driver; a janela mostra essa limitação e espera a liberação
dos recursos antes de fechar. Progresso de tabela usa o callback real do motor;
conexão/descoberta/comparação têm progresso indeterminado.

Senhas não têm getter Qt e não entram no QVariantMap, preferências, manifesto ou
resumo. Ficam no objeto de conexão e na requisição privada do worker, com `repr`
desabilitado; a requisição elimina suas referências ao terminar. Python/Qt não
prometem zerar memória de strings. QML mantém somente o texto do campo mascarado
enquanto a tela está aberta. Importar YAML elimina a senha anterior em memória.

Exceções técnicas não atravessam a fronteira cruas: usuário recebe ação sugerida
e categoria/etapa na área secundária. Findings usam mensagens do domínio e
amostras limitadas/redigidas. Não existe telemetria ou envio externo de dados.
Mensagens públicas do conector (como JAR ausente) são preservadas na interface.
No macOS, se a descoberta padrão do Java falhar e `JAVA_HOME` não estiver definido,
o conector procura também os JDKs Homebrew da arquitetura do aplicativo.

Abrir projeto carrega os artefatos existentes e recalcula a comparação usando o
motor, sem acrescentar etapa ao histórico. `project.json` guarda nome, descrição,
perfis de conexão sem senha, opções e última tela. Inventários de descoberta e
mapeamentos em revisão são salvos automaticamente na mesma pasta. O último projeto
é reaberto na próxima inicialização e até cinco projetos recentes ficam disponíveis
em Configurações. Aparência e a lista de recentes são persistidas em QSettings.
Senhas continuam apenas em memória ou na variável indicada por `password_env`.
A confirmação de escritas suspensas não é reutilizada entre sessões.
O projeto padrão fica na pasta local de dados do aplicativo, independente do
diretório de trabalho usado pelo Finder. Outro diretório pode ser escolhido em
Configurações.

## Demonstração e imagens

`dataqualy gui --demo` cria um diretório temporário exclusivo. São três tabelas,
60 registros, baseline vazia e um valor sintético alterado. As métricas são
calculadas pelo mesmo motor; não são números preenchidos em QML. O modo é
identificado no título, sidebar, rodapé e telas prioritárias. Credenciais e
endereços apresentados são sintéticos (`demo.invalid`, domínio reservado).

`dataqualy gui --demo --screenshots reports/screenshots` percorre oito telas,
dois temas e dois tamanhos. As seis imagens principais ficam em `docs/screenshots`.
Os screenshots não capturam conteúdo de outras janelas: usam `QQuickWindow.grabWindow`.

## Empacotamento e licenças

`pyproject.toml` inclui PySide6 e todos os recursos QML no wheel. O spec usa hooks
Qt do PyInstaller para coletar imports/plugins QML, binários Qt, PySpark e JPype.
O hook local `scripts/pyinstaller-hooks/hook-PySide6.QtQml.py` limita os imports
às famílias QtQuick/QtQml/QtCore/Qt antes da análise de binários, excluindo
QtWebEngine/QtWebView e suas dependências de navegador. Não se distribuem fontes proprietárias nem
ícones de terceiros: Segoe UI é resolvida no sistema Windows; demais plataformas
usam fonte de sistema. Os ícones Canvas deste repositório seguem sua licença MIT.
PySide6/Qt mantêm suas licenças próprias, incluídas pelos pacotes de origem.

O executável conserva o despacho `-m pyspark.worker` / `pyspark.daemon` antes de
importar Qt, evitando abrir janelas de GUI em processos Spark.

Referências de implementação: [integração Python/QML](https://doc.qt.io/qtforpython-6/tutorials/qmlintegration/qmlintegration.html),
[threads Qt](https://doc.qt.io/qtforpython-6/overviews/qtdoc-threads-technologies.html),
[backdrops DWM](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwm_systembackdrop_type).

## Limites desta rodada

- Sem validação de bancos reais nesta máquina; os quatro testes de integração
  dependem de configuração externa. SQL Server/MySQL continuam experimentais.
- Windows e Mica precisam de execução no Windows; CI específico foi adicionado.
  Capturas macOS/offscreen não comprovam o efeito nativo Windows.
- Histórico é do projeto aberto, sem catálogo global de projetos.
- Revisão avançada de transformações/filtros mantém os campos do manifesto,
  mas o motor continua considerando esses casos inconclusivos.
- Seleção não reduz o inventário capturado; exclusões reduzem a cobertura.
- Não há virtualização do conjunto Python inteiro: listas QML virtualizam linhas
  visíveis, mas o inventário/metadados continuam em memória como no backend atual.

## Evidências da rodada

Veja [desktop-verification.md](desktop-verification.md) para resultados exatos,
comandos reproduzíveis e verificações que dependem de Windows/bancos reais.

## Identidade visual e aplicativos nativos

Interface inspirada na referência Figma fornecida: navegação azul-marinho,
fundo suave azul/verde, cards claros e textos curtos. O tema claro é o padrão
para novas preferências; escolhas já salvas são preservadas. O tema escuro usa
uma paleta oceano. Informações avançadas de conexão ficam em um disclosure.

O veleiro foi reconstruído em SVG a partir da referência fornecida. Os arquivos
em `desktop/assets/` incluem SVG, PNG 1024, ICO com sete resoluções (16–256) e
ICNS Retina. `python scripts/generate-icons.py` reproduz os ícones; a geração de
ICNS usa `iconutil` no macOS. O PNG/SVG também define o ícone da janela/Dock.

O mesmo spec gera `DataQuality.app` no macOS, em modo onedir com BUNDLE, e
`dataqualy.exe` no Windows, em modo onefile. `scripts/build-macos.sh` cria o DMG
com atalho para Applications e oferece `--smoke-test`. São builds nativos:
Apple Silicon foi verificado localmente; Intel/Windows precisam de seus runners.
Nenhum certificado de assinatura ou credencial de publicação foi usado.
