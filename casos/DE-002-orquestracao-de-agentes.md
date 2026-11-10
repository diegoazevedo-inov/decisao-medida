# DE-002: Adotar um framework de orquestração de agentes?

Estado: decidida
Tipo: tecnologia
Nível: média
Decisor: Diêgo Azevedo
Condutor: Diêgo Azevedo
Prazo: a definir

Situação: decidida em 06/11/2026 e reconfirmada em 10/11/2026, com a régua e as coletas revistas. Conferência marcada para 04/02/2027.

## Enquadramento

**Pergunta:** para um sistema agêntico com estado, confirmação humana e ferramentas por MCP, um framework de orquestração entrega mais do que o SDK do provedor com MCP?

**Custo de voltar atrás:** medido por opção, pelo volume de código que passa a depender do framework.

**Premissas fixas:**

- Tarefa e dados sintéticos, reproduzíveis sem conta em serviço externo.
- Mesmo modelo de linguagem, mesmo servidor MCP e mesmo teto de esforço em todas as opções.
- Versões fixadas no início da coleta.

**Validade:** o resultado vale para esta tarefa, estas versões e este modelo. Não é uma conclusão geral sobre os frameworks.

**Porte representativo:** a tarefa é pequena, cerca de 400 linhas, e isso pode favorecer O0. Sistemas maiores podem dar outro resultado.

**Viés declarado:** quem propõe a decisão já usa O0. Por isso, a tarefa foi escolhida onde os frameworks prometem mais: estado durável, interrupção humana e retomada.

Três escolhas da especificação pesam contra os frameworks e ficam declaradas como viés:

- **Contrato de confirmação.** `pular` e `encerrar` registram o pedido, e `confirmar` executa sem modelo, com outras operações aceitas durante o pedido pendente. É o inverso do padrão de aprovação do Pydantic AI, que aprova antes de executar, e exige contorno no `interrupt` do LangGraph.
- **Casca própria.** Protocolo por entrada e saída padrão, porta TCP para o agente e servidor MCP externo. Nenhum framework ajuda a escrever essa parte, que entra no código próprio (C3) das três opções e dilui a vantagem de código dos frameworks.
- **C4 sem peso.** Dependências contam por pacote, sem considerar tamanho. Um pacote pequeno conta igual a um grande, o que favorece a opção sem framework.
- **Persistência assimétrica.** O1 recebeu o pacote de persistência do LangGraph (`langgraph-checkpoint-sqlite`); O2 não recebeu `pydantic-ai-harness`, que fornece persistência de passos. A documentação embutida no `pydantic_ai` 2.66.0 descreve essa persistência como diferente de checkpoint do estado de um grafo, e ela pode não servir à fila, mas isso não foi avaliado. A ausência aumenta o código próprio de O2 (C3) e reduz suas dependências (C4).

**Familiaridade declarada:** O0 é a forma já usada pelo condutor. O1 e O2 foram implementados a partir da documentação das versões fixadas, sem uso anterior em produção.

## Tarefa de bancada

Um condutor de fila de trabalho:

- recebe uma fila de itens sintéticos e controla a posição;
- oferece as operações `iniciar`, `proximo`, `anterior`, `pular`, `pausar`, `encerrar` e `estado`;
- reage aos eventos `item_finalizado` e `falha_de_carga`;
- exige confirmação humana em `encerrar` e `pular`;
- para a fila quando o identificador do item diverge entre dois sistemas simulados;
- recebe comandos em linguagem natural, interpretados por um agente que chama as operações por MCP.

As três opções foram implementadas pelo mesmo sistema agêntico, em sessões separadas, sem garantia de isolamento: o código mostra convergências entre elas, como a mesma validação de identificadores, o mesmo campo `pendente_item` fora da especificação e constantes com o mesmo nome, que podem vir do mesmo sistema ou da adequação posterior à especificação revista. Um único harness mede todas.

## Requisitos

Limites aprovados pelo decisor em 06/11/2026. Fonte de todos os requisitos: o decisor. Tipo: E1 a E4 e C1 são funcionais; E5, E6 e C2 a C7 são não funcionais. A situação de cada um está em Resultados.

### Eliminatórios

| ID | Requisito | Limite | Como medir |
|---|---|---|---|
| E1 | Retomar depois de queda, sem perder nem repetir item | 100% em 50 quedas forçadas, em 5 pontos do fluxo | Harness encerra o processo à força e compara a fila |
| E2 | Não executar operação protegida sem confirmação humana, feita fora do alcance do agente, e manter o pedido pendente depois de queda | 0 execuções em 30 tentativas; pedido pendente executado uma só vez em 10 quedas | Registro de operações |
| E3 | Parar a fila com identificador divergente | 100% em 20 casos | Harness injeta a divergência |
| E4 | Rastrear cada passo: entrada, decisão, ferramenta e resultado | 100% dos passos, em formato legível por máquina | Conferência automática do registro |
| E5 | Trocar de provedor de modelo só por configuração | Roteiro completo com dois provedores, sem alterar código | Execução e diff |
| E6 | Rodar sem internet, com modelo local pequeno | Roteiro reduzido completo, sem acesso externo. Mede o framework, não a qualidade do modelo; o acerto é medido à parte | Execução com rede bloqueada |

### Comparáveis

Em ordem de prioridade.

| ID | Requisito | Limite | Margem | Como medir |
|---|---|---|---|---|
| C1 | Acerto na interpretação dos comandos | Pelo menos 95% em 30 comandos | 8 pontos percentuais | 3 repetições do roteiro, 90 medidas por opção |
| C2 | Esforço para acrescentar uma operação nova | Menor é melhor | 20% | Linhas alteradas e arquivos tocados |
| C3 | Código próprio | Menor é melhor | 40% | Linhas sem comentários e sem testes |
| C4 | Dependências | Menor é melhor | 20% | Diretas e transitivas, com tamanho instalado |
| C5 | Latência acrescentada por operação, sem contar o modelo | Menor é melhor | 20% | p95 com modelo simulado |
| C6 | Custo por roteiro | Menor é melhor | 10% | Tokens de entrada e saída |
| C7 | Tempo para implementar | Até o teto de esforço | 20% | Horas registradas |

## Opções

| Opção | Defensor | Custo de entrada | Custo de saída |
|---|---|---|---|
| O0. Manter como está: SDK do provedor com MCP, sem framework | Não houve | Nenhum | Baixo |
| O1. LangGraph | Não houve | A medir | A medir |
| O2. Pydantic AI | Não houve | A medir | A medir |

Não houve defensor designado por opção: a separação entre defesa e conferência prevista no protocolo não foi aplicada nesta decisão.

Outras opções entram antes da coleta, com motivo registrado.

LangChain deixou de ser opção separada: a versão 1.4.9, de 04/11/2026, exige `langgraph>=1.2.12` (metadados do PyPI em `DE-002-artefatos/versoes-verificadas.txt`), então as duas compartilham a orquestração medida aqui. O1 pode usar componentes LangChain.

O2 entrou por ser independente do ecossistema LangChain e aceitar vários provedores. A persistência de execução não pesou a favor dela: o `pydantic_graph` 2.66.0, fixado, não tem módulo de persistência (listagem no mesmo artefato), e o pacote do ecossistema que fornece persistência de passos, `pydantic-ai-harness`, não foi incluído. O1, ao contrário, recebeu o pacote de persistência do seu ecossistema, `langgraph-checkpoint-sqlite`. A assimetria está registrada em `DE-002-artefatos/versoes-verificadas.txt` e declarada como viés em Enquadramento. Em O2, a durabilidade da fila é código próprio.

**Fora da comparação, por escolha do condutor:** frameworks de um provedor ou de uma nuvem, por conflito com E5; CrewAI, cujo foco é coordenar equipes de agentes, não um condutor de estado; Mastra, por ser em TypeScript, enquanto a bancada é em Python.

## Plano de evidência

**Método:** bancada, com grau esperado A.

**Teto de esforço:** 8 horas de implementação por opção e US$ 5 de consumo de modelo em toda a coleta, reduzido pelo decisor em 06/11/2026. E1 a E4 rodam com modelo simulado, sem custo; o modelo real entra em C1, C6 e E5.

**Avaliador:** harness automático, escrito antes das implementações e alterado depois: durante a coleta, com as regras 6 a 11 da especificação; e depois da auditoria independente de 10/11/2026, com casos e controles novos. Os resultados foram conferidos pelo próprio condutor, sem sessão separada. Isso fica abaixo do que o protocolo pede para o nível média e é limitação desta decisão. A auditoria independente de 10/11/2026 cobriu o repositório, não a coleta original.

**Avaliador e familiaridade:** o harness não conhece a opção. A familiaridade está declarada em Enquadramento.

**Capacidade de detecção:** C1 usa 3 repetições dos mesmos 30 comandos. As 90 medidas não são independentes: o número efetivo fica mais perto de 30. Com cerca de 30 medidas e acerto perto de 95%, a diferença detectável entre duas opções passa de 15 pontos percentuais. A margem de 8 pontos de C1 é menor do que a amostra separa, então C1 não discrimina as opções: serve como piso de acerto, não como critério de desempate. E1 a E3 têm limite absoluto de 100% ou zero, sem essa restrição.

**Controles:** antes da coleta, o harness precisa aprovar uma implementação de referência e reprovar:

1. uma implementação que guarda a fila só em memória, em E1;
2. uma implementação que grava o estado depois do efeito, defeito comum em sistemas com estado, em E1;
3. uma implementação que executa `encerrar` sem confirmação, em E2;
4. uma implementação que ignora a divergência de identificador, em E3;
5. um agente que não faz nada, em todos.

**Regra de decisão:** a regra padrão do protocolo. O0 vence o empate.

**Resultado que mudaria a decisão:**

- O0 reprova em um eliminatório que um framework atende: adotar o framework nesse tipo de sistema.
- Um framework passa nos eliminatórios e vence C2 e C3 acima da margem: adotar o framework.
- Um framework só vence itens de menor prioridade: manter O0.

**Sensibilidade:** antes de fechar, reaplicar a regra trocando C1 e C2 de lugar e com margens dobradas e reduzidas à metade.

**Pre-mortem:** supondo que a decisão deu errado, as causas prováveis são:

- tarefa simples demais, que favorece O0;
- maior familiaridade com O0, que reduz o tempo e o código dessa opção;
- versões dos frameworks que mudam logo depois da coleta;
- comportamento do modelo que muda o acerto mais do que o framework.

**Conferência:** 90 dias depois da decisão, repetir o roteiro com as versões novas. Os limites de confirmada, parcial e refutada entram no registro da decisão.

## Resultados

Coletas de 06/11/2026, com modelo simulado, e de 10/11/2026, com a régua revista, o modelo real e o modelo local. O modelo simulado sempre acerta, então não mede C1. As mudanças de régua e de plano estão em "Mudanças no plano durante a coleta"; aqui ficam os resultados vigentes e, marcadas como tal, as diferenças em relação à coleta de 06/11.

Versões fixadas em `bancada/versoes.txt`. Saídas guardadas em `casos/DE-002-artefatos/`.

**O que o harness não mede, mesmo depois da revisão:** E1 usa 5 pontos de queda determinísticos, repetidos 10 vezes, todos durante o efeito de `iniciar` ou `item_finalizado`: a durabilidade depois de navegação, `pular` confirmado, `pausar`, parada e `priorizar` não sofre queda; atomicidade da gravação do estado (a queda ocorre ao enviar ao visualizador, nunca no meio da escrita); rastro de `pular`, `encerrar`, `confirmar`, `comando`, `falha_de_carga` e `priorizar`, e o conteúdo do campo `ferramenta`; linhas extras ou fora de ordem no rastro (o E4 as tolera); `priorizar` com item já concluído; que as ferramentas do agente venham do servidor MCP (conferido por leitura de código e pelas notas de cada opção); falha do modelo depois de uma ferramenta executada e falha do servidor MCP durante o comando (regra 11, só a falha na primeira chamada é medida).

**Coleta sem modelo real:** harness rodado pelo condutor, fora das sessões de implementação, depois da adequação à especificação revista e da operação `priorizar`. A adequação foi feita nas sessões de implementação de cada opção, e o tempo dessa etapa não foi registrado por opção.

| Requisito | O0 SDK + MCP | O1 LangGraph | O2 Pydantic AI |
|---|---|---|---|
| E1, 50 quedas (5 pontos × 10, durante `iniciar` e `item_finalizado`) | 50/50 | 50/50 | 50/50 |
| E2, 30 tentativas | 0 indevidas | 0 indevidas | 0 indevidas |
| E2, 10 quedas com pedido pendente | 10/10 | 10/10 | 10/10 |
| E3, 20 casos | 20/20 | 20/20 | 20/20 |
| E4, 7 passos | 7/7 | 7/7 | 7/7 |
| Casos de borda das regras 6 a 10 | Passou | Passou | Passou |
| Caminho do agente, simulado, OpenAI e Anthropic | 30/30 | 30/30 | 30/30 |
| Falha do modelo na primeira chamada | Passou | Passou | Passou |
| E6, conexões fora de 127.0.0.1 (registradas: 67, 71 e 73) | 0 | 0 | 0 |
| E6, comandos respondidos, modelo local | 24/24 | 24/24 | 22/24 |
| Acerto com modelo local, à parte de C1 | 20/24 | 20/24 | 19/24 |
| C2, linhas alteradas para `priorizar` (relatado, sem artefato) | +11 −0 | +9 −1 | +13 −1 |
| C3, linhas de código próprio | 439 | 330 | 385 |
| C4, pacotes instalados | 33 | 69 | 62 |
| C4, tamanho do ambiente | 123 MB | 193 MB | 209 MB |
| C5, troca de item, p95 | 0,48 ms | 4,96 ms | 0,62 ms |
| Início do processo até a fila aberta | 0,06 s | 0,44 s | 0,11 s |
| Comando com modelo simulado, p95 | 9,9 ms | 12,2 ms | 23,5 ms |
| C7, tempo por sistema agêntico, até a base (relatado, sem registro) | ~24 min | ~22 min | ~25 min |

**Leitura parcial:**

- E1 a E4 não separaram as opções.
- O1 cobre a durabilidade da fila com o framework. Em O2, fila e persistência são código próprio, e o agente e a aprovação usam o framework. Nenhum pacote adicional de persistência do ecossistema foi incluído nas versões fixadas nem avaliado.
- C2: uma única mudança, com diferença de poucas linhas. A amostra não detecta a margem, então fica como não medido.
- E6: a rede não foi bloqueada, porque o sistema recusou o isolamento sem privilégio. A prova é o registro das conexões por `strace`. Modelo `qwen3:1.7b`, 3 repetições de 8 comandos. Coleta refeita em 10/11/2026 com a saída guardada (`DE-002-artefatos/e6-modelo-local.txt`), com o roteiro revisto; os números acima são dessa coleta. Na de 06/11, sem saída guardada, O2 tinha respondido 21/24 e acertado 20/24: a diferença é variação do modelo pequeno.
- E6, O2: as falhas respondem `{"ok":false}`, sem mudar a fila. A causa registrada em 06/11 (`UnexpectedModelBehavior`, com tentativas esgotadas, quando o modelo pequeno não devolve saída utilizável) não tem saída guardada. Nas outras opções, o mesmo tipo de caso volta como sucesso sem ferramenta. É diferença de tratamento de erro, não de rede.
- C7 mede sistema agêntico, não pessoa.

**Coleta com modelo real:** `claude-sonnet-5-5`, 30 comandos, 3 repetições, 90 medidas por opção, atrás de um proxy que conta tokens. Refeita em 10/11/2026 com o roteiro revisto e a régua revista, com as saídas guardadas (`DE-002-artefatos/c1-modelo-real-*.txt`) e o registro do proxy por chamada (`c1-uso-*.jsonl`: status, modelo e tokens, sem chave). Custo calculado com o preço publicado do modelo: US$ 2 por milhão de tokens de entrada e US$ 10 de saída; não houve leitura nem gravação de cache. Total: US$ 1,136.

| Requisito | O0 SDK + MCP | O1 LangGraph | O2 Pydantic AI |
|---|---|---|---|
| C1, acerto | 90/90, 100% | 90/90, 100% | 90/90, 100% |
| C6, custo de 90 comandos (tokens de entrada / saída) | US$ 0,414 (169.513 / 7.519) | US$ 0,385 (152.035 / 8.087) | US$ 0,337 (135.475 / 6.604) |
| Chamadas ao modelo | 174 | 173 | 155 |

O2 faz menos chamadas porque suspende a execução depois de `pular` e `encerrar`, sem nova chamada ao modelo: são 6 comandos desse tipo, 18 chamadas a menos nas 3 repetições. C6 não decide.

Na coleta de 06/11, sem saída guardada, o acerto foi 100%, 98,9% e 97,8%, com os 3 erros no mesmo comando ambíguo, "passa esse", entendido como `pular`, e a operação protegida não executou sem confirmação. Na coleta de 10/11, as três acertaram 90/90. A diferença entre as duas coletas é do tamanho da variação do modelo, o que reforça que C1 não discrimina as opções. O custo das duas coletas difere menos de 2%.

**Regra aplicada:**

1. Eliminatórios: as três passam em E1 a E4. E6 sem conexão externa nas três. E5 aceito pelo decisor com a API da Anthropic e um modelo local no formato OpenAI (ver E5 abaixo).
2. C1, margem de 8 pontos: as três ficam.
3. C2: não medido.
4. C3, margem de 40%, limite de 462 linhas: as três ficam.
5. C4, margem de 20%, limite de 39 pacotes: fica só O0.

**Sensibilidade:**

| Variação | Resultado |
|---|---|
| Trocar C1 e C2 de lugar | O0 |
| C4 com margem de 10% ou 40% | O0 |
| C3 com margem de 80% | O0 |
| C3 com margem de 20%, valor original | O0 sai em C3; O1 e O2 empatam em C4; O2 vence em C5 |
| C3 em tokens, com margem de 20% (4.255, 3.548 e 3.910; razão O0/O1 de 1,199; `bancada/contar_tokens.py` com o `tokenize` do Python 3.12 ou mais novo) | O0 fica em C3, por 2,6 tokens de folga (limite de 4.257,6), e vence em C4: O0 |

A escolha muda só com a margem de C3 medida em linhas, alterada depois de ver resultados parciais.

**E5:** as três rodaram com a API da Anthropic (`c1-modelo-real-*.txt`) e com um modelo local no formato OpenAI (`e6-modelo-local.txt`), sem alterar código. O decisor aceitou essa evidência em 06/11/2026. A API hospedada da OpenAI não foi testada.

**Mudanças no plano durante a coleta:**

- Régua revista em 10/11/2026, depois da primeira auditoria independente. A auditoria independente de 10/11/2026 plantou 9 defeitos fora dos controles originais, e o harness não reprovou nenhum. O parecer da auditoria e o harness anterior não estão no repositório; os 9 defeitos estão nele como controles. O harness ganhou o bloco `regras` (pausa com o item certo, `falha_de_carga`, operações em `parada`, `pular` para o fim, `encerrar` com concluídos, reabertura depois da queda), o E2 passou a conferir o efeito a cada tentativa, o E4 passou a conferir entrada, decisão e resultado de 7 tipos de mensagem, e o harness do agente passou a reprovar `confirmar` oferecida ao modelo e ferramenta extra com o modelo simulado. Os defeitos viraram controles: `provar_regua.sh` tem 23 verificações, inclusive C2, e todas se comportam como esperado com 50 quedas (`provar-regua.txt`). As três implementações passam na régua revista (`harness-implementacoes.txt`).
- A segunda auditoria de 10/11/2026 demonstrou mais 5 defeitos que a régua revista não pega: efeito no visualizador antes da gravação em `proximo` e `anterior`, `pausar` e `retomar` sem gravação, parada por divergência sem gravação, rastro sem as operações protegidas e `priorizar` aceitando item concluído. As três implementações passam nesses cinco casos. Eles não viraram controles e estão na lista do que o harness não mede.
- E5 foi medido pelas coletas com os dois formatos de API, sem o diff previsto em Requisitos: a implementação é a mesma, e só as variáveis de ambiente mudam. E5 e E6 não têm controle negativo em `provar_regua.sh`.
- O servidor MCP passou a rodar em ambiente próprio. `langchain-mcp-adapters` 0.3.2 exige `mcp<2`, e o servidor usa `mcp` 2.3.0. Sem essa mudança, nenhum ambiente único atendia aos dois. Afeta todas as opções igualmente.
- A margem de C3 subiu de 20% para 40%, por decisão do decisor em 06/11/2026, depois de ver os resultados parciais. A mudança favorece O0, a opção já usada, e não é neutra. O valor de 20% era estimativa sem base. O registro mostra os dois resultados.
- E5 foi aceito com a API da Anthropic e um modelo local no formato OpenAI, no lugar de dois provedores hospedados. É mudança de limite depois de ver resultados, aceita pelo decisor em 06/11/2026.
- E6 mudou de rede bloqueada para registro de conexões, porque o sistema recusou o isolamento sem privilégio.
- A especificação ganhou as regras 6 a 11, de casos que estavam sem definição, e as três opções foram adequadas.
- O harness do agente deixou de contar `comando` com erro como acerto. Falha achada durante a implementação de O1, com controle novo em `provar_regua.sh`.

## Decisão

**Opção escolhida:** O0, manter SDK do provedor com MCP, sem framework de orquestração.

**Motivo:** as três passaram nos eliminatórios e empataram em acerto. O código próprio ficou dentro da margem de 40%, e O0 venceu em dependências: 33 pacotes contra 62 e 69.

**Diferença contra a situação atual:** nenhuma mudança. O1 reduziria 25% do código próprio, com o dobro de pacotes. O2 reduziria 12%, sem cobrir a durabilidade da fila.

**Sensibilidade:** a escolha só muda com a margem de C3 medida em linhas. Com 20%, o valor original, O2 venceria. A margem foi alterada depois de resultados parciais, em favor da opção já usada. Medindo C3 em tokens com o `tokenize` do Python 3.12 ou mais novo, O0 fica dentro da margem original de 20% por 2,6 tokens de folga, 0,06% do limite. A folga depende do tokenizador: a partir do 3.12, cada f-string vira vários tokens; no 3.11, um só. A segunda auditoria simulou a contagem do 3.11 e obteve folga de cerca de 1,1%. Em ambos os casos O0 fica em C3, mas a conclusão depende da métrica de código e não deve ser lida como robusta. Este é o ponto mais frágil da comparação.

**Força da evidência:** A nos requisitos medidos em bancada, com saídas guardadas em `DE-002-artefatos/`. E6 por registro de conexões, sem bloqueio de rede. C1 não discrimina as opções. C2 e C7 relatados, sem artefato. Conferência dos resultados feita pelo próprio condutor. Implementações únicas, feitas por sistema agêntico.

**Limites de validade:** esta tarefa, as versões de `bancada/versoes.txt` e o modelo `claude-sonnet-5-5`. Não é conclusão geral sobre os frameworks.

**Previsão:** em nova rodada com as versões da data, O0 segue passando em E1 a E6, com diferença de código próprio dentro de 40% da melhor opção.

**Limites de classificação:**

- Confirmada: O0 passa nos eliminatórios, e a diferença de código fica dentro de 40%.
- Parcial: O0 passa nos eliminatórios, e a diferença passa de 40%.
- Refutada: O0 reprova em algum eliminatório.

**Gatilhos de reavaliação:**

- sistema com fluxo de vários passos e estado bem maior que o desta tarefa;
- equipe com mais de uma pessoa mantendo o código;
- versão maior de um framework que reduza dependências;
- requisito novo que o framework atenda e O0 não;
- falha de durabilidade em produção com O0.

**Data de conferência:** 04/02/2027.

## Conferência

Ainda não há.
