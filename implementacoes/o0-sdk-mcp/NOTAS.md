# Notas da opção O0, SDK do provedor com MCP

Desenho, decisões em pontos que a especificação não define, e onde a opção ajudou ou atrapalhou. Os resultados estão em `casos/DE-002-orquestracao-de-agentes.md`.

## Entrega

- `condutor.py`: 566 linhas no total; 439 de código próprio pela contagem de `bancada/medir.py` (sem linhas em branco, comentários e testes).
- `requirements.txt`: `mcp==2.3.0`, `anthropic==2.6.0`, `openai==3.46.0`.
- `.venv`: Python 3.14.4, 34 pacotes contando dependências e o pip, 123 MB.

## Verificações além do harness

Verificações de desenvolvimento, feitas com scripts que não fazem parte do repositório e com um modelo roteirizado nos dois formatos. Não têm teste versionado: valem como registro do desenho, não como evidência da DE-002. A evidência da DE-002 é o que o harness mede (`casos/DE-002-artefatos/`).

| Caso | Resultado |
|---|---|
| Operações diretas sem nenhuma variável `MODELO_*` | funcionam |
| `comando` sem `MODELO_API` | `{"ok":false}`; processo segue vivo |
| Modelo inacessível | `{"ok":false}` em 1,6 s (openai) e 2,0 s (anthropic) |
| Modelo falha no segundo turno, depois de `proximo` executado | `{"ok":false}`; fila volta a A; visor recebeu `abrir B` e `abrir A` |
| Modelo falha depois de `pular` | `{"ok":false}`; `pendente` volta a `null`; visor intacto |
| Laço sem fim do modelo | para em 8 passos; `{"ok":false}`; fila restaurada |
| Servidor MCP morto durante uma chamada | `{"ok":false}`; fila restaurada; comando seguinte funciona |
| Servidor MCP morto entre comandos | próximo comando abre outro e tem efeito na fila |
| Porta do agente recebe `confirmar` ou `comando` | recusa; pedido pendente intacto |
| Modelo pede ferramenta `confirmar` | erro volta ao modelo; a fila não muda; fora de `ferramentas`; registrado no rastro |
| Regra 7, operação por operação | conferida, com o visualizador intacto |
| `encerrada` recebe `proximo`, `retomar`, `confirmar` e `item_finalizado` | `{"ok":false}` |
| Queda com pedido feito pelo agente | pedido sobrevive |
| Visualizador fora do ar em `iniciar` | `ok:false`; fila em `parada`; `encerrar` confirmado leva a `encerrada` e responde `ok:false` por não conseguir enviar `fechar` |
| `SIGKILL` ou fim da entrada padrão | filho MCP termina (conferido por PID) |
| `MODELO_CHAVE` | ausente do rastro e do ambiente do filho MCP |

O caso `is_error` do servidor MCP não foi exercitado de ponta a ponta: o ramo existe, mas nenhum teste provoca esse resultado.

## Onde a opção ajudou

- O núcleo da fila é uma função pura: `decidir(fila, mensagem)` devolve resposta, novo estado e efeito. A especificação revista mudou as regras 6, 7 e 9 só nessa função, sem tocar na casca.
- O estado é imutável e o `comando` é sequencial, então a restauração da regra 11 é guardar uma referência e gravá-la de volta (cerca de 12 linhas).
- Controle total da falha: separar "pedido errado volta ao modelo" de "falha do servidor derruba o comando" foram poucas linhas.
- `confirmar` fica fora do agente por três barreiras simples: o servidor não a expõe, o condutor não a encaminha ao servidor e a porta TCP a recusa.
- Importação preguiçosa dos SDKs: as operações diretas não dependem deles.
- `mcp.Client` com `StdioServerParameters` cobre o transporte, e o SDK só repassa variáveis seguras de ambiente: a chave não chega ao servidor sem código adicional.

## Onde a opção atrapalhou

- Dois adaptadores de API escritos à mão (cerca de 60 linhas), com conversão de esquema de ferramenta e de formato de resultado por provedor.
- O laço do agente, os limites de passos e prazos, a recuperação do servidor e a restauração da regra 11 são código próprio, e é nessa camada que se concentra o risco de defeito da opção.
- O cliente MCP usa escopos do anyio que precisam abrir e fechar na mesma tarefa. Manter a sessão entre comandos exigiu uma tarefa dona da sessão e sincronização por `Future`.
- O teste de saúde da sessão precisou de `list_tools`, porque `ping` está obsoleto no protocolo novo do cliente.

## Decisões em pontos que a especificação não define

| Ponto | Decisão |
|---|---|
| `encerrar` "fecha e termina" | envia `fechar` e encerra a fila; o processo continua atendendo |
| Fim natural da fila | também envia `fechar`, embora a tabela só cite "abre o próximo" |
| Navegação em `pausada` | permitida: a pausa só para a troca automática |
| `pular` em `parada` | `{"ok":false}`, sem registrar: a regra 7 não o lista entre as operações com efeito |
| `pular` pendente e o item atual mudou | a confirmação cancela o pedido e responde `{"ok":false,"erro":...}`, para não atingir outro item. A tabela diz que `confirmar` executa; a implementação abre essa exceção deliberadamente, por segurança |
| `iniciar` com fila em andamento | recusado; permitido depois de `encerrada` |
| Itens vazios, repetidos ou com espaço | recusados: o id entra numa linha do protocolo do visualizador |
| Visualizador indisponível | tratado como falha de carga: `parada` durável e `ok:false` |
| Campo `ferramenta` do rastro em operação direta | `null`; o campo extra `origem` diferencia humano, agente e processo |
| Reinício com fila `encerrada` | reenvia `fechar`, que é idempotente |

## O que ficou de fora

- Teste com modelo real nas verificações de desenvolvimento. A coleta com a API real da Anthropic é a da DE-002 (`casos/DE-002-artefatos/c1-modelo-real-o0-sdk-mcp.txt`); a API hospedada da OpenAI não foi testada.
- Queda do processo durante um `comando`: mudanças já feitas por ferramentas ficam gravadas, pois a restauração só ocorre em falha tratada.
- Corrida residual na restauração: uma operação do agente ainda em trânsito na porta TCP quando o comando falha pode ser aplicada depois da restauração. Exigiria o servidor entregar a mensagem após a perda da sessão. Não foi observada.
- Trava contra dois processos na mesma pasta de estado.
- Paginação de `list_tools`: lê só a primeira página, suficiente para as 8 ferramentas atuais.
- Atendimento de mensagens durante um `comando`: a entrada é sequencial e um evento espera o comando terminar, até 60 s.
- Memória de conversa entre comandos: cada comando é uma conversa nova.
- Testes automatizados próprios na entrega: as verificações de desenvolvimento não foram versionadas.
- Recuperação de `estado.json` ilegível: o processo termina com erro, para não recomeçar uma fila vazia.
