# Auditoria de banco inteiro — formato 1

## Diagnóstico e plano incremental

O histórico até `1aa517a` implementava validação por tabela com Spark, regras YAML,
pacotes CSV/anexos, HTML e uma GUI Firebird → PostgreSQL. Não havia inventário,
baseline, manifesto, comparação offline ou estado persistido. A árvore estava
limpa antes desta implementação.

Plano executado: (1) adicionar domínio e conectores sem substituir o legado;
(2) capturar e comparar evidências; (3) integrar CLI, Tk e relatório;
(4) provar a fatia com fixtures sintéticas, testes negativos e integrações opcionais.

## Camadas

| Responsabilidade | Módulo `dataqualy.audit` |
|---|---|
| Modelos tipados, estados, versões | `domain`, `storage` |
| Acesso JDBC e introspecção | `connectors`, `engines` |
| Captura de esquema, agregados, evidências | `inventory`, `evidence` |
| Sugestões determinísticas e manifesto | `mapping` |
| Regras determinísticas e decisão global | `checks` |
| Projeto retomável, etapas e conversão externa manual | `orchestration` |
| HTML autocontido e resultado JSON | `reporting` |
| Interfaces locais | `cli`, `gui` |
| Contratos de conversor externo e IA opcional | `providers` |

O fluxo antigo mantém seus módulos e APIs. O novo conector usa JPype **opcional**
para acessar os mesmos JARs JDBC diretamente, sem iniciar Spark para capturar
contagens/metadados. Usa `DatabaseMetaData.getTables`, `getColumns`,
`getPrimaryKeys`, `getImportedKeys` e `getIndexInfo`. SQL de identificadores,
contagens e duplicações fica no catálogo de engines. Não há condicionais de
engine no orquestrador.

JDBC usa conexão read-only, autocommit desativado e rollback ao fechar. Ainda é
necessário um usuário com SELECT/metadados: `setReadOnly` não substitui permissões.
Os resultados são buscados com fetch size; PostgreSQL usa cursor transacional,
MySQL habilita cursor/prepared statements e SQL Server usa buffering adaptativo.
O driver controla detalhes de buffering e pode impor limites próprios.

Referências do contrato JDBC: [Jaybird DatabaseMetaData](https://www.firebirdsql.org/docs/drivers/java/latest/docs/org.firebirdsql.jaybird/org/firebirdsql/jdbc/FBDatabaseMetaData.html)
e [JPype — carregamento da JVM/JARs](https://jpype.readthedocs.io/en/latest/userguide.html).

## Evidências e privacidade

Snapshots JSON guardam engine, horários UTC de início/fim, identificador da execução,
versão 1, opções, esquema, contagens, perfis e findings. A identidade do destino é
SHA-256 da URL **sem usuário/senha**. O perfil de conexão é separado do snapshot;
não inclui campo de senha. A GUI recebe senha apenas em memória. A nova CLI exige
`password_env`, sem senha literal no YAML.

Extremos mínimo/máximo de números exatos e datas são HMAC, não valores legíveis.
Textos, binários, emails e nomes de registros nunca entram em snapshots ou HTML.
O perfil `exhaustive` gera um SQLite auxiliar contendo somente identificador de
tabela/coluna, HMAC da chave e HMAC de cada valor. A mesma chave aleatória de pelo
menos 32 bytes, fornecida por variável de ambiente, deve ser usada nas capturas de
origem e destino. A chave não é salva; somente um identificador derivado permite
detectar chaves diferentes. Compare offline não precisa mais dela.

Trate HMAC como evidência pseudonimizada, não anonimização absoluta. Proteja a chave
e os arquivos; uma chave divulgada permite ataques de dicionário. Nomes de tabelas,
colunas e justificativas revelam metadados: não coloque segredos ou dados pessoais
nesses campos. Nesta fatia a auditoria nova não oferece amostras reais; o domínio
mascara qualquer amostra recebida e limita a 20 itens. O relatório não as exibe.

Os JSON são escritos em arquivo temporário no mesmo diretório, sincronizados e
substituídos atomicamente. Os arquivos temporários usam permissão 0600 no POSIX;
no Windows, proteja o diretório com ACL. O SQLite é fechado e renomeado antes de o
snapshot publicar sua referência e SHA-256. Capture só é completa após finalizar.
Uma falha ao publicar JSON pode deixar um SQLite órfão, sem publicar sucesso.
Recapturas mantêm artefatos anteriores para recuperação; limpeza não é automática.

O SHA-256 detecta corrupção acidental do sidecar, **não autentica** um operador
que possa alterar JSON e SQLite. Formatos locais não são prova antifraude assinada.
Distribua JSON e seu SQLite juntos, sem renomear o sidecar.

## Decisão e cobertura

Prioridade global: `error` → `failed` → `inconclusive` → `passed`.
`skipped` exige exclusão justificada ou uma validação inaplicável (ex.: extremos
de coluna inteiramente nula). Lista vazia nunca aprova. Qualidade encontrada
mostra violações observadas; cobertura mostra itens de origem resolvidos por
mapeamento confirmado ou exclusão justificada. Exclusões aparecem separadamente
e não representam dados efetivamente comparados.

Uma tabela/coluna não mapeada, um destino extra sem origem, manifesto não confirmado,
tipo sem comparação segura, perfil ausente ou regra não executada bloqueia a aprovação.
Uma captura cancelada/incompleta gera evidência explícita. Falhas em uma tabela não
impedem registrar as outras, mas não se convertem em sucesso parcial global.

Baseline precisa ter contagem zero para todas as tabelas descobertas. O destino pode
ter tabelas criadas pelo conversor depois da baseline: elas precisam estar mapeadas.
Se o destino ainda não tiver estrutura, capture a baseline vazia e revise o manifesto
após descobrir o esquema convertido, antes da captura final.

`--quiescent` é uma afirmação do operador de que suspendeu escritas durante cada
captura. Sem ela a consistência é `inconclusive`. Não há snapshot transacional global
entre bancos nem bloqueio de escritores pelo DataQuality. Mudanças detectadas entre
contagem e leitura invalidam a captura, mas não detectam toda alteração concorrente.
As contas JDBC precisam enxergar todas as tabelas dentro do escopo. Metadados
ocultos por permissões não podem ser descobertos por um usuário sem privilégios.

## Perfis

| Perfil | Execução | Limite de aprovação |
|---|---|---|
| `fast` | esquema, contagem, nulos, duplicações/nulos de chave | sem prova de valores ou integridade completa |
| `balanced` | fast + distintos, extremos HMAC, índices únicos e órfãos | agregados iguais não comprovam registros iguais |
| `exhaustive` | balanced + fingerprints de chave/coluna, comparados em disco | aprova somente escopo 1:1 confirmado e totalmente suportado |

Todos evitam `collect()` de tabelas. Metadados ficam na memória; agregados retornam
uma linha; registros do JDBC são consumidos incrementalmente. SQLite indexa digests
em disco e a comparação usa dois cursores ordenados, com memória constante por coluna.
O volume de evidência em disco é proporcional a registros × colunas suportadas.
Há uma consulta agregada por coluna e por restrição, além de varredura exaustiva:
isso pode ser caro em bases grandes. Tamanho padrão do lote: 500; timeout SQL: 60s.

Contagens incluem diferença absoluta e percentual contra a cardinalidade esperada;
para origem zero e destino não zero o percentual é indeterminado (`null`). Chaves
simples/compostas, ausentes/extras e valores são comparados por HMAC. Duplicação é
quantidade de grupos duplicados, não quantidade de linhas excedentes. Unicidade
de índices considera chaves completamente não nulas; semântica de índice parcial,
expressões e NULLS NOT DISTINCT não é generalizada. FKs usam semântica MATCH SIMPLE;
tipos/regras especiais de FK exigem validação adicional.

## Matriz de tipos e limites

A matriz combina cada par de engines do catálogo com códigos JDBC, conservando o
tipo nativo, tamanho e escala. Números exatos, texto limitado, booleano e DATE são
as famílias da primeira versão. Redução de tamanho/precisão ou troca de família
falha; tipos desconhecidos produzem `inconclusive`. Inteiros unsigned exigem revisão.

Canonicalização de números exatos usa Decimal (1, 1.0 e 1.00 equivalem); NULL é um
token distinto. Textos mantêm Unicode, caixa e espaços sem trim ou normalização;
collations diferentes podem ter distintos diferentes mesmo com valores iguais.
Datas são ISO sem timezone. Chaves compostas preservam ordem e fronteiras dos valores.
Floats, NaN, timestamp/time/timezone, LOBs, binários, textos grandes/ilimitados e tipos
especiais não têm canonicalização segura nesta rodada: ficam inconclusivos ou geram
erro explícito se o driver não conseguir consultar o perfil. Não há hash nativo SQL
comparado entre engines. SHA/HMAC tem risco teórico de colisão; não é garantia total.

Manifestos registram filtros esperados, cardinalidade, transformação e comparação
customizada, mas não executam SQL ou código fornecido nesses campos. Sem comparador
determinístico implementado, marcam `inconclusive`. Sugestões por nome nunca são
confirmadas automaticamente, exceto no exemplo sintético fixo. Tabelas usam ID JSON
`[catalog,schema,name]` para evitar colisões envolvendo pontos em identificadores.

Esta versão inventaria tabelas, colunas, PK, FK e índices. Views, sequences, triggers,
procedures, permissões, defaults, checks SQL e validação de planos/performance não
fazem parte da aprovação. As regras customizadas antigas continuam em `validate`.

## GUI e cancelamento

Oito abas Tk, sem servidor. Conexão, descoberta, captura, leitura/gravação e comparação
ocorrem em worker. A thread principal só altera widgets e consome uma fila a cada
100 ms. Senhas não são capturadas por logs de erro. Cancelar sinaliza Event e tenta
`Statement.cancel()` fora da thread de UI; captura checa cancelamento por registro,
tabela e metadado. Drivers podem demorar até o timeout da consulta; conexão/metadados
podem depender do timeout de rede do driver. Não se mata thread nem se interrompe
um write atômico pela metade. Conversão externa não é controlada pela GUI nesta fase.

## Compatibilidade

`dataqualy validate`, CSV/JDBC, regras e pacotes permanecem. A GUI anterior está em
`dataqualy gui-legacy`; `dataqualy gui` e o executável abrem o fluxo novo. Relatório
vazio deixou de aprovar (correção intencional). `sample_size` continua aceito no YAML
antigo, mas o padrão passa a 0, o máximo a 20 e os valores ficam mascarados. O helper
de HTML antigo ainda aceita amostras fornecidas explicitamente pela API; não o use
para publicar dados sensíveis. Migre senhas literais antigas para `password_env`.
