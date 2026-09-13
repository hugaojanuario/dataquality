# Verificação da migração desktop

Rodada concluída em 13/09/2026. Ambiente local: macOS ARM64, Python 3.11.16,
PySide6 6.9.3 e Java 17. Nenhuma instância real de banco foi utilizada.

| Verificação | Resultado |
|---|---|
| Suíte antes da migração, com Java configurado | 121 aprovados, 4 integrações ignoradas |
| Suíte após a migração | 131 aprovados, 4 integrações ignoradas |
| `python -m compileall -q src tests scripts` | Aprovado |
| Fluxo de captura → revisão → comparação pelo adaptador | Aprovado com `MemoryConnector` injetado e motor existente |
| Senhas em estado público, artefatos e erros | Testes aprovados; senha sem getter Qt |
| Workers, responsividade, entrega na thread Qt e cancelamento | Testes aprovados |
| Nova tentativa de validação falhando após aprovação | Aprovação anterior invalidada; regressão coberta |
| Navegação QML, temas, dimensões e teclado | Testes aprovados sem warnings QML |
| Edição de coluna no diálogo com foco por teclado | Teste aprovado; captura visual inspecionada |
| Telas vazias e captura incompleta | Testadas sem aprovação indevida |
| Capturas offscreen | 32 imagens: 8 telas × 2 temas × 2 tamanhos |
| Abertura e captura nativa no macOS | 32 imagens, log QML vazio |
| PyInstaller macOS ARM64 | `DataQuality.app` concluído; demonstração do bundle gera 32 imagens, sem warnings QML |
| Instalador macOS ARM64 | `DataQuality-macos-arm64.dmg` gerado; checksum aprovado por `hdiutil verify` |
| Recursos QML e identidade no wheel e aplicativo | 35 recursos QML e 5 assets; SVG, PNG, ICO e ICNS incluídos |
| Identidade visual | Veleiro vetorial, tema claro inspirado na referência e tema oceano escuro; telas revisadas em 1280×800 e 1024×700 |
| QtWebEngine/QtWebView no executável final | Ausentes; hook de coleta restrito às famílias desktop |
| Build e execução no Windows | Não executados localmente; workflow e smoke test preparados |
| Mica nativo no Windows | Implementado com fallback; não validado visualmente no Windows |
| macOS Intel e distribuição assinada | Não verificados; sem Developer ID e sem notarização Apple |
| Bancos reais Firebird/PostgreSQL/SQL Server/MySQL | Não verificados; quatro integrações puladas por falta de configuração |

As oito telas foram inspecionadas visualmente em temas claro/escuro. Em 1024×700,
conteúdos extensos usam rolagem; os controles não se sobrepõem. As seis imagens
públicas estão em [screenshots](screenshots/), incluindo visão geral, conexões e
resultado com 68 checks aprovados e uma divergência sintética.

Comandos de reprodução:

```sh
python -m pytest -q
python -m compileall -q src tests scripts
python -m dataqualy gui --demo
python -m dataqualy gui --demo --screenshots reports/screenshots
python -m PyInstaller --clean --noconfirm dataqualy.spec
DATAQUALITY_PYTHON=.venv/bin/python ./scripts/build-macos.sh --smoke-test
```

No macOS com Java Homebrew, a suíte foi executada com `JAVA_HOME` apontando para
o JDK 17 instalado. A primeira tentativa sem essa variável resultou em sete erros
de inicialização do Spark; todos passaram após corrigir o ambiente, sem alterar
o motor ou remover testes.

O build pode informar que `pyspark.sql.connect` não encontra Pandas. Esse modo
já está excluído do spec e não participa da auditoria local nem da GUI. O arquivo
Windows deve ser gerado e testado no Windows; o binário local não é um `.exe`.

A inspeção adicional pela automação de acessibilidade do macOS ficou pendente
das permissões do sistema. A validação visual usou capturas geradas pelo próprio
Qt, incluindo as 32 imagens produzidas pelo aplicativo empacotado.
