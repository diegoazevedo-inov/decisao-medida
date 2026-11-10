# Notas da opção O1, LangGraph

Desenho, decisões em pontos que a especificação não define, e onde a opção ajudou ou atrapalhou. Os resultados estão em `casos/DE-002-orquestracao-de-agentes.md`.

## O que foi feito

- `condutor.py`: grafo da fila, checkpointer, interrupção humana, visualizador, rastro, porta TCP e grafo do agente.
- `requirements.txt`: versões de `versoes.txt` para o cliente, com `mcp==1.30.0` exigido pelo adaptador, mais `langchain-openai==1.7.4` e `langchain-anthropic==1.7.10`. `pip check` sem conflitos.

Desenho:

- Grafo da fila: `decidir -> [visualizador] -> rastrear -> [aguardar_humano -> decidir ...] -> fim`, com `AsyncSqliteSaver` e `durability="sync"`.
- `pular` e `encerrar` param o grafo em `interrupt()`. Enquanto há pedido pendente, toda mensagem entra por `Command(resume=...)`, e `decidir` trata `confirmar` e as demais.
- `estado` lê o checkpoint com `aget_state`, sem percorrer o grafo.
- Queda: ao reiniciar, a mensagem pela metade termina com `ainvoke(None)`, depois o item atual é reaberto.
- `RetryPolicy` no nó do visualizador. Se ele continua fora, a resposta é `{"ok":false,"erro":"visualizador indisponivel"}` e o efeito é refeito antes da mensagem seguinte.
- Agente: `StateGraph` com `ToolNode` e `tools_condition`, sem checkpointer. Retomar um comando pela metade repetiria uma ferramenta já executada.
- Sessão MCP única por processo, aberta no primeiro `comando` com `MultiServerMCPClient.session` e `load_mcp_tools`. Primeiro `comando` levou de 1,0 s a 1,4 s; os seguintes, 0,02 s, com o modelo simulado.

## Verificações de desenvolvimento

Feitas com scripts que não fazem parte do repositório. Não têm teste versionado: valem como registro do desenho, não como evidência da DE-002. A evidência da DE-002 é o que o harness mede (`casos/DE-002-artefatos/`).

- 39 verificações da fila passaram: bordas das regras 6 a 9 com resposta exata, operações com pedido pendente, queda com `interrupt` ativo, queda no meio do efeito, `confirmar` em queda executado uma só vez, rastro da mensagem interrompida, visualizador fora do ar e de volta, recusa de `confirmar` e `comando` na porta TCP.
- Agente, nos formatos OpenAI e Anthropic: vários `comando` no mesmo processo; `comando` com pedido pendente; `confirmar` humano depois de `pular` pedido pelo agente; linhas do rastro para cada ferramenta e para o `comando`; saída limpa ao fechar a entrada.
- Servidor MCP morto com `kill -9`: o `comando` seguinte responde `{"ok":false}`, e o próximo reabre a sessão e funciona.
- Sem `MCP_PYTHON`: `comando` responde `{"ok":false}` e a fila não muda.
- Modelo que acerta a primeira chamada e falha depois do resultado da ferramenta, nos dois formatos: depois de `proximo`, a fila voltou a A e o visualizador recebeu `abrir A`; depois de `pular`, `pendente` voltou a nulo; com pedido anterior pendente, o pedido ficou e `confirmar` funcionou. O harness não cobre esse caso.

## Decisões onde a especificação não define


| Caso | Decisão |
|---|---|
| `proximo` e `anterior` em `pausada` | Permitidos: a pausa para só a troca automática |
| `falha_de_carga` em `parada` | `{"ok":false}`, pela regra 7 |
| `item_finalizado` divergente em `parada` | `{"ok":false,"divergencia":true}`, situação mantida, pela regra 8 |
| `confirmar` de `pular` pedido antes de a fila parar | Executa, pela regra 7, e a fila continua `parada` |
| Fim da fila | Envia `fechar` ao visualizador |
| "`encerrar` fecha e termina" | Fecha o visualizador e encerra a fila. O processo continua até o fim da entrada padrão |
| `confirmar` de `pular` depois de o item atual mudar | `{"ok":false}`, e o pedido é limpo: o humano aprovou pular outro item |
| `iniciar` com fila em andamento | Recusado. Depois de `encerrada`, permitido |
| Ids vazios, repetidos ou com espaço | `iniciar` recusa: o id vai numa linha do protocolo do visualizador |
| `estado` antes de `iniciar` | `atual` nulo, `total` 0, `situacao` `encerrada` |
| Campo `ferramenta` do rastro | Nulo em mensagem direta, nome da operação na porta TCP, lista em `comando` |
| Modelo falha depois de uma ferramenta já executada | O `comando` responde `{"ok":false}` e a fila volta à foto tirada antes dele, por uma operação interna `restaurar` que passa pelo grafo. Se o item mudou, o visualizador recebe `abrir` do item anterior |

## Onde a opção ajudou

- `durability="sync"` deu a ordem exigida pela regra 4, estado antes do efeito, sem código próprio.
- A retomada do nó interrompido refez o efeito e completou o rastro da mensagem que estava no meio, com `ainvoke(None)`.
- `interrupt()` manteve pedido e ponto de parada no mesmo checkpoint: E2q passou sem tabela à parte.
- `RetryPolicy` cobriu a repetição no visualizador.

## Onde a opção atrapalhou

- O adaptador exige mcp<2: cliente e servidor ficaram em ambientes separados.
- `durability` padrão não é `sync`: sem passar o argumento em cada chamada, a regra 4 fica sem garantia.
- Cada mensagem grava mais de um checkpoint com o estado da fila, e a implementação não limpa checkpoints antigos. O crescimento do banco não foi medido.
- Inicialização de 0,44 s por processo (`casos/DE-002-artefatos/medir.txt`).
- O servidor MCP recebe o ambiente completo do processo, inclusive `MODELO_CHAVE`; O0 e O2 filtram as variáveis repassadas.
- A regra 11 não tem suporte direto: a ferramenta já tinha efeito quando o modelo falha, e o desfazer foi escrito à mão. O LangGraph permite voltar a um checkpoint, mas isso não refaz o visualizador nem passa pelo rastro.
- O grafo do agente não tem checkpointer, porque o interrompido não pode ser retomado sem risco de repetir ferramenta: nessa parte a durabilidade do LangGraph não foi usada.
- `interrupt` não atende, sozinho, a confirmação com outras operações aceitas durante o pedido pendente: o contorno, descrito em "Desenho", faz toda mensagem entrar por `Command(resume=...)` enquanto há pedido.

## O que ficou de fora

- Retomar um `comando` interrompido por queda: o pedido se perde, e a ferramenta que já rodou fica aplicada, sem o desfazer da regra 11.
- Linha de rastro para mensagem perdida antes de entrar no grafo. Numa queda dentro de `rastrear`, a linha pode sair duplicada.
- Limpeza de checkpoints antigos.
- Teste com modelo real nas verificações de desenvolvimento. A coleta com a API real da Anthropic é a da DE-002 (`casos/DE-002-artefatos/c1-modelo-real-o1-langgraph.txt`); a API hospedada da OpenAI não foi testada.
