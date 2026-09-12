# Protocolo público de conversão — JSON Lines v1

Somente contrato. Não há implementação de motor, adaptador proprietário, subprocesso
de conversão ou modelo de IA neste repositório. Cada empresa implementa seu sidecar
e mantém código/configuração privada fora do DataQuality MIT.

## Transporte

Processo externo iniciado por lista de argumentos, sem shell, com stdin/stdout UTF-8.
Uma mensagem JSON por linha, máximo 64 KiB por mensagem. stdout é exclusivo do
protocolo; stderr contém diagnósticos já redigidos e nunca valores ou credenciais.
Credenciais vêm de variável de ambiente ou mecanismo privado de segredo; mensagens
contêm somente referências opacas, nunca senhas, DSNs com senha ou linhas reais.

Envelope obrigatório, validado por `parse_provider_line`:

```json
{"protocol_version":1,"request_id":"request-1","run_id":"run-1","type":"capabilities","payload":{}}
```

`request_id` correlaciona resposta e comando. Eventos de execução conservam o ID do
`start`; cada novo comando tem ID próprio. `run_id` é estável. Versão desconhecida,
JSON inválido, mensagem truncada, EOF sem terminal ou saída diferente de zero são
erros; nunca implicam conversão concluída ou auditoria aprovada.

## Mensagens e estado

| Tipo | Direção | Payload esperado |
|---|---|---|
| `capabilities` | host → sidecar / resposta | pedido `{}`; resposta `engines`, `provider_version`, `supports_cancel`, `protocol_versions` |
| `validate_config` | host → sidecar / resposta | pedido `config_ref`; resposta `valid` boolean e lista `issues` sem dados sensíveis |
| `start` | host → sidecar | `config_ref`, `mapping_ref`; exige validate_config válido |
| `progress` | sidecar → host | `sequence` crescente, `phase`, `completed_units`, `total_units` (ou null) |
| `table_metrics` | sidecar → host | `sequence`, `table_id`, contagens não negativas `read`, `written`, `rejected` |
| `completed` | sidecar → host | terminal, `sequence`, `duration_ms`, resumo agregado |
| `failed` | sidecar → host | terminal, `sequence`, `code`, mensagem redigida e `retryable` |
| `cancel` | host → sidecar | pedido idempotente para execução ativa |
| `cancelled` | sidecar → host | terminal, confirma interrupção e informa `partial_output: true/false` |

Máquina de estados: negociação → configuração validada → execução → exatamente um
terminal (`completed`, `failed`, `cancelled`). Não aceitar `start` concorrente para a
mesma execução. Repetição de `request_id` deve ser idempotente ou rejeitada, nunca
duplicar escrita. Eventos fora de ordem/duplicados são registrados e não contam duas
vezes. `cancel` após terminal responde com o estado terminal existente.

Futuro host negocia timeout de inicialização e prazo de cancelamento; após o prazo
pode terminar **apenas o processo iniciado por ele**, registrando erro/saída parcial.
O sidecar deve documentar transações, checkpoints, retomada e recuperação. Cancelar
não implica rollback completo. Conversão parcial exige nova avaliação do destino.

O parser desta rodada valida o envelope, versão, tipo e tamanho. Validação específica
de payload, sequenciamento, subprocesso, timeouts e negociação pertencem à futura
implementação do host, não são anunciados como funcionalidades executáveis.

`completed` significa apenas que o provider terminou. Métricas e mensagens do
provider não são evidência de aprovação. A auditoria captura o destino e executa
seus próprios checks determinísticos.

## Porta opcional de IA

`AIConfig(enabled=False)` e `AIAssistant` definem a porta, sem Ollama/SDK obrigatório.
Uma futura implementação deverá criar uma projeção estrita de metadados e contagens,
sem perfis de conexão, linhas, fingerprints, extremos reais ou justificativas livres.
Ela retornará JSON no schema tipado de `Manifest`. `validate_ai_suggestion` rejeita
campos/tipos desconhecidos, valida o manifesto, força `confirmed=false` e identifica
a origem como sugestão. Nenhuma saída de IA é finding ou aprovação. Não há chamada
de IA nesta versão, mesmo que alguém instancie `AIConfig(enabled=True)`.
