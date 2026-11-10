# Decisão Medida

[English summary](README.en.md)

Um protocolo para decidir tecnologia e processo de um projeto com evidência, contra requisitos funcionais e não funcionais. A regra de decisão vem antes da coleta, a régua precisa provar que reprova um caso ruim, e toda decisão registra uma previsão conferida em data marcada.

Estado: rascunho v0.4, em primeiro uso. Nenhuma decisão foi conferida ainda.

## O problema

O protocolo parte de três premissas, que este repositório não mede: decisões técnicas podem ser tomadas por opinião, moda ou documentação do fornecedor; quando há medição, o critério pode aparecer depois do resultado, sem que ninguém volte para ver se a decisão acertou; e, com sistemas agênticos, construir uma alternativa para comparar ficou barato o bastante para tornar a medição viável. O único dado aqui sobre a última premissa é o tempo de implementação da DE-002, relatado sem registro.

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
| Retomada em 50 quedas forçadas (5 pontos fixos × 10, durante `iniciar` e `item_finalizado`) | 50/50 | 50/50 | 50/50 |
| Operação protegida sem confirmação | 0 | 0 | 0 |
| Acerto, 90 comandos, modelo real | 100% | 100% | 100% |
| Custo de 90 comandos, modelo real | US$ 0,41 | US$ 0,38 | US$ 0,34 |
| Linhas de código próprio | 439 | 330 | 385 |
| Pacotes instalados | 33 | 69 | 62 |

Resultado da regra: manter SDK com MCP, por dependências.

**Limites que acompanham esse resultado:**

- A escolha depende da margem e da métrica de código próprio. Contando linhas, com a margem original de 20%, Pydantic AI venceria; a margem subiu para 40% depois de resultados parciais, em favor da opção já usada, e essa mudança está registrada. Contando tokens com o tokenizador do Python 3.12 ou mais novo, a opção sem framework fica dentro da margem original por uma folga de 0,06%, o que não torna o resultado robusto.
- O acerto com modelo real usa 3 repetições dos mesmos 30 comandos. As medidas não são independentes, e a amostra não separa diferenças menores que cerca de 15 pontos: o acerto serve como piso, não como desempate.
- A régua foi revista depois da primeira auditoria independente, que achou 9 defeitos que ela não pegava; eles viraram controles, e as três opções passam na régua revista. A segunda auditoria demonstrou mais 5 defeitos fora da régua, em que as três opções também passam; eles não viraram controles e estão listados na DE-002 como não medidos.
- A tarefa é pequena, com cerca de 400 linhas. Sistemas maiores podem favorecer os frameworks.
- Cada opção teve uma implementação, feita por sistema agêntico.
- O resultado vale para esta tarefa, estas versões e este modelo. Não é uma avaliação geral dos frameworks.

Conferência marcada para 04/02/2027.

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

## Limitação atual

O protocolo teve uso de uma só pessoa. Nenhuma conferência aconteceu, e é ela que mostra se as decisões acertaram. Os limites e margens dos níveis foram propostos sem medição.

## Licença

Apache License 2.0. Veja [LICENSE](LICENSE).

---

Desenvolvido por Diêgo Azevedo · [github.com/diegoazevedo-inov](https://github.com/diegoazevedo-inov)
