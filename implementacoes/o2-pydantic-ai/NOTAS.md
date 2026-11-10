# Notas da opção O2, Pydantic AI

Desenho, decisões em pontos que a especificação não define, e onde a opção ajudou ou atrapalhou. Os resultados estão em `casos/DE-002-orquestracao-de-agentes.md`.

## O que foi entregue

| Arquivo | Linhas | Papel |
|---|---|---|
| condutor.py | 179 | Entrada e saída, porta TCP do agente, visualizador, rastro, retomada |
| fila.py | 176 | Regras da fila em transições puras |
| agente.py | 125 | Modelo, MCP, aprovação e conversa em Pydantic AI |
| persistencia.py | 19 | Escrita atômica com fsync |

## Verificações de desenvolvimento

Feitas com scripts que não fazem parte do repositório. Não têm teste versionado: valem como registro do desenho, não como evidência da DE-002. A evidência da DE-002 é o que o harness mede (`casos/DE-002-artefatos/`).

- Aprovação nos dois formatos: `pula esse` chama a ferramenta MCP, suspende a execução e grava `deferred_tool_requests` em conversa.json. Depois de SIGKILL e reinício, `estado` mostra `pendente: pular`, `confirmar` executa uma vez, e o comando seguinte retoma a conversa suspensa e usa a ferramenta certa.
- Modelo falha depois de `proximo`, nos dois formatos: `{"ok":false}`, fila de volta em A, visualizador com `abrir A, abrir B, abrir A`. Um `pular` que já estava pendente continua pendente.
- `MCP_PYTHON` inválido ou inexistente: `{"ok":false}` em 1,2 s.
- Ferramenta MCP com erro: `{"ok":false}` em 1,7 s.
- Servidor MCP morto durante a sessão: o comando seguinte responde `{"ok":false}`, e o próximo reconecta e funciona.
- Modelo travado: `{"ok":false}` em 80,0 s, com a fila intacta.
- Regra 7: em `parada`, com `pular` pendente, nenhuma operação vedada mudou a fila ou o visualizador. `comando` com `proximo` responde ok=true, mas a ferramenta é recusada e a fila não muda. `encerrar` confirmado fecha.
- 60 comandos seguidos na mesma conversa: sem erro, 40 mensagens guardadas, cerca de 31 KB.
- Porta do agente: recusa `confirmar` e `comando` com `{"ok":false}`.
- Servidor MCP: morre junto com o condutor no SIGKILL e não recebe `MODELO_CHAVE`.
- Visualizador fora do ar: `iniciar` responde `{"ok":false}`, a fila fica `parada` e o processo segue atendendo.
- Primeiro comando de um processo: cerca de 1,7 s (openai) e 2,1 s (anthropic).

## Onde a opção ajudou

- MCP: `MCPToolset` com `StdioTransport` resolveu a conexão, a lista de ferramentas e o ciclo de vida do servidor. A troca para `MCP_PYTHON` mudou uma linha.
- Provedor: `OpenAIChatModel` e `AnthropicModel` deram o mesmo comportamento. A troca é só pelas variáveis.
- Aprovação: `ApprovalRequired`, levantado no gancho `process_tool_call`, suspende a execução sem código de controle de fluxo próprio.
- Conversa: `Conversation` com `ConversationTypeAdapter` guarda mensagens, uso e chamadas suspensas num só JSON, e a retomada depois de queda funcionou sem ajuste.
- Ordem das ferramentas: `Agent.parallel_tool_call_execution_mode("sequential")` resolveu em uma linha.

## Onde a opção atrapalhou ou não cobriu

- Estado da fila: a opção não cobre. O pacote `pydantic_graph` 2.66.0, fixado em `versoes.txt`, não tem módulo de persistência (listagem em `casos/DE-002-artefatos/versoes-verificadas.txt`); nenhum pacote adicional de persistência foi incluído nas versões fixadas. Fila, durabilidade, reabertura do item, pendência e execução única são código próprio, em fila.py, persistencia.py e condutor.py.
- Fluxo de aprovação: o padrão da opção é aprovar antes de executar a ferramenta e depois retomar com o modelo. O contrato pede o inverso: a ferramenta registra o pedido, e `confirmar` executa sem modelo. Por isso a implementação não usa `approval_required()`: o gancho chama a ferramenta primeiro e só então suspende. A decisão fica em fila.json e chega à conversa só no comando seguinte.
- Comando com pedido ainda sem decisão: a opção exige resposta para toda chamada suspensa antes de continuar. A implementação responde com `ToolDenied` e o texto de que o pedido segue pendente. A fila não muda, mas a conversa registra uma negação provisória e não é avisada de uma confirmação posterior.
- `UsageLimits`: o uso acumula na `Conversation`, e o limite padrão é 50 pedidos, segundo o código e a documentação da versão fixada. A implementação calcula o limite por comando somando o uso já acumulado; o caso sem esse ajuste não foi executado.
- Tamanho da conversa: a opção não apara o que vai para o disco; `ProcessHistory` apara só o que vai ao modelo. A implementação corta ao gravar, nos últimos 10 turnos.
- Rollback: a opção não desfaz efeitos de ferramenta quando a execução falha. A compensação da regra 11 é código próprio, em `Condutor._desfazer`.
- Erro de ferramenta: com o padrão `tool_error_behavior="retry"`, a falha do servidor MCP não é repassada ao chamador. A implementação troca esse comportamento para atender à regra 11. Não há teste versionado que exercite o padrão.
- Tempo de importação: o Pydantic AI é importado só no primeiro `comando`, para as operações diretas não pagarem esse custo.

## O que ficou de fora

- Modelo real: fora das verificações de desenvolvimento; a coleta com modelo real é a da DE-002.
- Execução durável de uma execução em curso: uma queda no meio de `comando` perde a conversa daquele turno. Efeitos já feitos pelas ferramentas ficam na fila.
- Rastro de `comando`: a linha é gravada ao fim. Numa queda no meio do comando ela não existe, e só ficam as linhas das ferramentas já chamadas.
- `ConversationStore`: sem subclasse. A documentação indica `Conversation` em JSON para este caso, e há uma só conversa.
- StepPersistence: fornecida pelo pacote `pydantic-ai-harness`, que não está em versoes.txt (consulta ao PyPI em `casos/DE-002-artefatos/versoes-verificadas.txt`).
- `comando` bloqueia a leitura da entrada padrão até terminar, com limite de 60 s por chamada ao modelo e 80 s no total.
