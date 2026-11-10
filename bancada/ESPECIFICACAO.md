# Especificação do condutor de fila

Tarefa de bancada da DE-002. Toda opção implementa este contrato. O harness não conhece a opção.

## Execução

A implementação é um processo iniciado com:

```text
<comando da opção> --estado <pasta>
```

Variável de ambiente `VISOR_PORTA`: porta TCP do visualizador simulado, em `127.0.0.1`.

O processo lê uma mensagem JSON por linha na entrada padrão e responde uma mensagem JSON por linha na saída padrão.

## Operações

| Mensagem | Efeito | Resposta |
|---|---|---|
| `{"op":"iniciar","itens":["A","B"]}` | Cria a fila e abre o primeiro item | `{"ok":true}` |
| `{"op":"estado"}` | Nenhum | `{"ok":true,"atual":"A","posicao":0,"total":2,"situacao":"ativa","concluidos":[],"pendente":null}` |
| `{"op":"proximo"}` | Abre o próximo item, sem concluir o atual | `{"ok":true}` |
| `{"op":"anterior"}` | Abre o item anterior | `{"ok":true}` |
| `{"op":"pausar"}` | Para a troca automática | `{"ok":true}` |
| `{"op":"retomar"}` | Volta à situação ativa | `{"ok":true}` |
| `{"op":"pular"}` | Registra o pedido, sem efeito, até a confirmação | `{"ok":false,"precisa_confirmacao":true}` |
| `{"op":"encerrar"}` | Registra o pedido, sem efeito, até a confirmação | `{"ok":false,"precisa_confirmacao":true}` |
| `{"op":"confirmar","aceito":true}` | Executa o pedido pendente: `pular` manda o item para o fim da fila, `encerrar` fecha e termina. Com `false`, cancela | `{"ok":true}` |
| `{"op":"comando","texto":"..."}` | O agente interpreta o texto e chama as ferramentas | `{"ok":true,"ferramentas":["proximo"],"resposta":"..."}` |
| `{"op":"evento","tipo":"item_finalizado","id":"A"}` | Conclui o item e abre o próximo | `{"ok":true}` |
| `{"op":"evento","tipo":"falha_de_carga","id":"A"}` | Para a fila | `{"ok":true}` |

`situacao` assume `ativa`, `pausada`, `parada` ou `encerrada`. Ao fim da fila, `atual` é `null` e `situacao` é `encerrada`.

## Regras

1. **Confirmação.** `pular` e `encerrar` só têm efeito depois de `confirmar`. `confirmar` é uma mensagem do humano: não pode ser exposta ao agente. O pedido pendente aparece em `pendente`, sobrevive a uma queda e é executado uma só vez.
2. **Identidade.** `item_finalizado` com `id` diferente do item atual responde `{"ok":false,"divergencia":true}`, muda a situação para `parada` e não altera o visualizador.
3. **Pausa.** Em `pausada` ou `parada`, `item_finalizado` responde `{"ok":false}` e não troca o item.
4. **Durabilidade.** O estado é gravado na pasta antes de qualquer efeito no visualizador. Depois de uma queda, ao reiniciar com a mesma pasta, o processo retoma a fila e reabre o item atual.
5. **Visualizador.** Abrir: enviar `abrir <id>\n`. Fechar: enviar `fechar\n`. Em ambos, aguardar a linha `ok`.
6. **Limites da fila.** `proximo` no último item e `anterior` no primeiro respondem `{"ok":false}` sem efeito.
7. **Situação parada.** Em `parada`, só `estado`, `encerrar` e `confirmar` têm efeito. `retomar` responde `{"ok":false}`.
8. **Precedência.** A regra de identidade vale antes da regra de pausa: `item_finalizado` divergente muda para `parada` mesmo em `pausada`.
9. **Pedidos pendentes.** Um pedido novo substitui o anterior. `confirmar` sem pedido responde `{"ok":false}`.
10. **Encerrar.** Envia `fechar` ao visualizador, deixa `atual` como `null` e `situacao` como `encerrada`, sem alterar `concluidos`.
11. **Falha do agente.** Se o modelo ou o servidor MCP falhar, `comando` responde `{"ok":false}` e a fila não muda.
12. **Rastro.** Cada mensagem recebida gera uma linha JSON em `<pasta>/rastro.jsonl`, com os campos `entrada`, `decisao`, `ferramenta` e `resultado`.

## Agente

Variáveis de ambiente:

- `MODELO_URL`: URL base esperada pelo SDK daquele formato: com `/v1` em `openai` e sem `/v1` em `anthropic`.
- `MODELO_API`: `openai` ou `anthropic`, formato da API.
- `MODELO_NOME`: nome do modelo.
- `MODELO_CHAVE`: chave de acesso.

As ferramentas do agente vêm do servidor MCP `bancada/mcp_operacoes.py`, iniciado pela implementação por stdio, com a variável `CONDUTOR_PORTA`. O servidor é uma peça externa à opção: roda com o interpretador da variável `MCP_PYTHON`, em ambiente próprio, e cada opção usa o cliente MCP compatível com ela. A implementação abre essa porta TCP em `127.0.0.1` e atende uma mensagem JSON por linha, com as mesmas operações, exceto `confirmar` e `comando`.

Instrução do agente, igual em todas as opções:

> Você opera uma fila de trabalho. Use as ferramentas para atender ao pedido. Se o pedido não for sobre a fila, responda sem usar ferramenta.

## Operação da medição C2

Acrescentada depois da base, para medir o esforço de mudança.

| Mensagem | Efeito | Resposta |
|---|---|---|
| `{"op":"priorizar","id":"D"}` | Coloca o item logo depois do atual, sem efeito no visualizador. Durável e com rastro | `{"ok":true}` |

Item inexistente, item atual ou item já concluído respondem `{"ok":false}`, sem mudança. Em `parada`, responde `{"ok":false}`. O agente acessa a operação pela ferramenta `priorizar`, que recebe `id`.
