# Decisão Medida

[English summary](README.en.md)

Um protocolo para decidir tecnologia e processo de um projeto com evidência, contra requisitos funcionais e não funcionais. A regra de decisão vem antes da coleta, a régua precisa provar que reprova um caso ruim, e toda decisão registra uma previsão conferida em data marcada.

Versão 0.4 ([doi:10.5281/zenodo.24139207](https://doi.org/10.5281/zenodo.24139207)). Primeira conferência marcada para 04/02/2027.

## Para quê

O protocolo troca o argumento pela medição na hora de escolher tecnologia ou processo. Requisitos e regra de decisão são fixados antes da coleta; as opções são construídas e medidas na mesma bancada; e a decisão registra uma previsão, conferida depois. Com sistemas agênticos, construir as alternativas para comparar se torna viável mesmo em equipe pequena.

## Como funciona

1. **Enquadrar:** pergunta, decisor, custo de voltar atrás, premissas e porte representativo.
2. **Levantar requisitos:** com fonte, situação, limite e forma de medir.
3. **Listar opções:** "manter como está" sempre concorre.
4. **Planejar a evidência:** regra de decisão, controles e capacidade de detecção, antes da coleta.
5. **Coletar e verificar:** provar a régua e guardar o que permite repetir.
6. **Decidir:** com sensibilidade, previsão numérica e gatilhos de reavaliação.
7. **Conferir:** na data marcada, comparar o previsto com o observado.

Texto completo: [PROTOCOLO.md](PROTOCOLO.md).

## O que tem aqui

| Parte | Para quê | Onde |
|---|---|---|
| **Protocolo** | Passos, regras, níveis, graus de evidência e modelo de registro | [PROTOCOLO.md](PROTOCOLO.md) |
| **Antecedentes** | De onde vem cada parte e o que foi lido | [ANTECEDENTES.md](ANTECEDENTES.md) |
| **Caso** | Decisão completa, com requisitos, resultados, mudanças de plano e sensibilidade | [casos/](casos/) |
| **Bancada** | Especificação, harness, controles e roteiro do caso | [bancada/](bancada/) |
| **Implementações** | As três opções comparadas | [implementacoes/](implementacoes/) |

## Caso: adotar um framework de orquestração de agentes?

A [DE-002](casos/DE-002-orquestracao-de-agentes.md) comparou SDK do provedor com MCP, sem framework, contra LangGraph e Pydantic AI, numa tarefa sintética: um condutor de fila com estado durável, confirmação humana e agente por MCP. A DE-001, primeiro caso do método, é privada. As saídas que sustentam os números estão em [casos/DE-002-artefatos/](casos/DE-002-artefatos/).

| Medida | SDK + MCP | LangGraph | Pydantic AI |
|---|---:|---:|---:|
| Retomada em 50 quedas forçadas (5 pontos do fluxo, 10 vezes cada) | 50/50 | 50/50 | 50/50 |
| Operação protegida sem confirmação | 0 | 0 | 0 |
| Acerto, 90 comandos, modelo real | 100% | 100% | 100% |
| Custo de 90 comandos, modelo real | US$ 0,41 | US$ 0,38 | US$ 0,34 |
| Linhas de código próprio | 439 | 330 | 385 |
| Pacotes instalados | 33 | 69 | 62 |

**O que o caso mostra:** nesta tarefa, nenhum framework acrescentou garantia que o SDK com MCP não tivesse. Durabilidade depois de queda, confirmação humana em operação protegida e parada diante de identificador divergente foram atendidas nas três opções e verificadas pela mesma bancada; a diferença entre elas ficou no código próprio e nas dependências.

**Resultado:** manter o SDK com MCP. As três opções atenderam a todos os requisitos eliminatórios e empataram em acerto; o desempate foi pelas dependências: 33 pacotes, contra 69 e 62.

**Como ler o resultado:**

- Vale para esta tarefa (cerca de 400 linhas, uma implementação por opção), estas versões e este modelo. Sistemas maiores podem pedir outra resposta.
- O ponto sensível é o código próprio. Com a margem de 20% definida no início, medida em linhas, o Pydantic AI seria o escolhido; a margem foi revista para 40% durante a coleta. As duas leituras, e a medida em tokens, estão na DE-002.
- A bancada passou por duas auditorias independentes e uma verificação dirigida. Os defeitos encontrados viraram controles ou estão declarados na DE-002 como não medidos, e as três opções passam em todos.

## Reproduza

A prova da régua usa Python 3, só com a biblioteca padrão, sem rede e sem conta. Medir as opções exige Python 3.11 ou mais novo:

```bash
./bancada/provar_regua.sh
```

A referência precisa passar, e cada defeito plantado precisa reprovar no requisito esperado.

Para medir uma opção:

```bash
python3 -m venv bancada/.venv && bancada/.venv/bin/pip install mcp==2.3.0
cd implementacoes/o0-sdk-mcp
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cd ../../bancada
python3 harness.py --quedas 50 -- ../implementacoes/o0-sdk-mcp/.venv/bin/python ../implementacoes/o0-sdk-mcp/condutor.py
python3 harness_agente.py -- ../implementacoes/o0-sdk-mcp/.venv/bin/python ../implementacoes/o0-sdk-mcp/condutor.py
python3 harness_c2.py -- ../implementacoes/o0-sdk-mcp/.venv/bin/python ../implementacoes/o0-sdk-mcp/condutor.py
python3 medir.py ../implementacoes/o0-sdk-mcp
```

Sem modelo real, o harness usa um modelo simulado que sempre acerta: ele testa o caminho, não o acerto. `harness_c2.py` confere a operação acrescentada para medir C2, `medir.py` gera C3, C4 e C5, e `contar_tokens.py` conta o código próprio em tokens, para a sensibilidade de C3. A coleta com modelo real usa `rodar_real.sh`, e a do modelo local sem rede, `rodar_e6.sh`.

## Estado do método

A conferência de 04/02/2027 vai mostrar se a decisão se sustenta, e os limites dos níveis do protocolo serão calibrados com o uso.

## Licença

Apache License 2.0. Veja [LICENSE](LICENSE).

---

Desenvolvido por Diêgo Azevedo · [github.com/diegoazevedo-inov](https://github.com/diegoazevedo-inov)
