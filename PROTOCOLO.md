# Decisão Medida

Protocolo de decisão por evidência. Rascunho v0.4 · 06/11/2026

## Objetivo

Escolher, em cada decisão de tecnologia ou de processo de um projeto, a opção que melhor alcança os requisitos funcionais e não funcionais, com evidência registrada e conferida depois.

## Escopo

| Tipo | Exemplos | Evidência principal |
|---|---|---|
| Tecnologia | Linguagem, framework, biblioteca, provedor, arquitetura | Bancada |
| Processo | Duração da sprint, limite de WIP, etapa de auditoria, definição de pronto, rotina de operação | Piloto |

Fora do escopo:

- **Metodologia de gestão do projeto.** Entra como premissa fixa, declarada no passo 1.
- **Decisão sem alternativa real.** Quando contrato ou norma determina a resposta, registra-se a origem e cumpre-se.

## Regras

1. O enquadramento é aprovado antes dos requisitos, e os requisitos vêm antes das opções.
2. Manter como está sempre concorre e, mesmo reprovada, continua como referência de comparação.
3. A regra de decisão é definida antes da coleta.
4. O esforço acompanha o custo de errar.
5. Quem defende uma opção não a avalia.
6. Antes de ser usada, a régua precisa reprovar um caso ruim parecido com o real e aprovar um caso bom.
7. Evidência fraca pode decidir, desde que declarada como fraca.
8. O resultado vale para o contexto medido: projeto, equipe e versão.
9. Toda decisão registra uma previsão, conferida em data marcada.

## Níveis de decisão

O nível é definido no passo 1 e determina o esforço das etapas seguintes.

| Nível | Quando se aplica | Evidência mínima | Avaliação |
|---|---|---|---|
| Leve | Volta atrás em até um dia, sem efeito fora do projeto | D | Do próprio condutor |
| Média | Volta atrás em até um mês, ou afeta vários módulos ou a equipe inteira | B ou C | Avaliador separado |
| Pesada | Volta atrás em mais de um mês, ou envolve segurança, dado sensível, contrato ou efeito sobre pessoas atendidas | A ou B nos requisitos eliminatórios | Avaliador separado e plano de saída |

## Força da evidência

| Grau | Fonte |
|---|---|
| A | Medição controlada no ambiente do projeto: mesma tarefa, mesmos dados, versões fixadas, repetida |
| B | Piloto real com linha de base, antes e depois |
| C | Histórico do próprio projeto ou de projeto comparável, sem controle |
| D | Documentação, relato ou benchmark de terceiros |
| E | Opinião ou experiência sem registro |

Dados do fornecedor da opção avaliada contam como D, mesmo quando apresentados como medição.

## Papéis

| Papel | Responsabilidade |
|---|---|
| Decisor | Decide e responde pela decisão |
| Condutor | Conduz os passos e mantém o registro |
| Defensor | Apresenta o melhor caso de uma opção |
| Avaliador | Executa ou confere a medição, sem defender opção |

Uma pessoa pode acumular papéis, exceto defensor e avaliador da mesma opção. O registro declara a familiaridade do avaliador com cada opção e, quando viável, o nome da opção fica oculto na correção. Em equipe de uma pessoa, o avaliador pode ser uma pessoa externa ou um sistema agêntico em sessão separada, sem acesso aos argumentos de defesa. Quando a separação não for possível, o registro declara isso.

## Passos

### 1. Enquadrar

Registrar:

- a pergunta em uma frase;
- o tipo e o nível da decisão;
- o decisor e o prazo;
- o custo de voltar atrás;
- as premissas fixas, ou seja, o que não está em discussão;
- o porte representativo: se a tarefa ou a amostra avaliada tem o tamanho da decisão real e, se for menor, a quem isso pode favorecer;
- o contexto: projeto, equipe, versões e fase.

**Saída:** enquadramento aprovado pelo decisor. Sem essa aprovação, o passo 2 não começa, porque um enquadramento errado invalida os requisitos levantados depois.

### 2. Levantar requisitos

Cada requisito tem identificador, tipo, fonte, situação, classe, limite numérico e forma de medir.

- **Tipo:** funcional ou não funcional. Em decisão de processo, o funcional é o que a prática precisa garantir, e o não funcional é com que desempenho.
- **Fonte:** especificação, contrato, norma, dado de uso ou decisão do dono do produto. Requisito sem fonte não entra. Para uso real, a fonte primária é quem usa, não a documentação da ferramenta.
- **Situação:** confirmado, hipótese ou a levantar. Hipótese pode orientar o plano, mas nenhuma decisão fecha com requisito eliminatório que não esteja confirmado.
- **Classe:** eliminatório, quando reprovar exclui a opção, ou comparável, quando serve para ordenar as opções.

Os requisitos comparáveis são ordenados por prioridade. Cada um declara a margem mínima que conta como diferença real.

Para não esquecer requisito não funcional, a lista é conferida contra as características de qualidade da ISO/IEC 25010.

**Saída:** tabela de requisitos, sem item sem limite ou sem forma de medir. Limite comparável pode ficar para uma sessão com o decisor, desde que seja definido antes da coleta daquele requisito.

### 3. Listar opções

A lista inclui manter como está e a opção mais simples capaz de atender aos eliminatórios. Cada opção registra o custo de entrada, o custo de saída e o defensor. Opções descartadas nesta etapa ficam registradas com o motivo.

**Saída:** pelo menos duas opções, contando manter como está.

### 4. Planejar a evidência

Antes de qualquer coleta, definir:

- o método, a amostra e a duração para cada requisito;
- o grau de evidência esperado;
- o teto de esforço, em tempo e custo;
- os controles: um caso ruim parecido com o real, que a régua precisa reprovar, e um caso bom, que ela precisa aprovar;
- a capacidade de detecção: se a amostra consegue distinguir a margem de cada requisito;
- a regra de decisão;
- o resultado que mudaria a decisão;
- em decisão média ou pesada, um pre-mortem: supor que a decisão deu errado e listar as causas, que viram riscos do plano e gatilhos de reavaliação.

**Regra de decisão padrão:**

1. Excluir as opções reprovadas em algum eliminatório.
2. Percorrer os requisitos comparáveis pela ordem de prioridade. Em cada um, manter só as opções dentro da margem da melhor. A comparação é feita contra a melhor, nunca aos pares, porque aos pares pode haver ciclo.
3. Se restar uma opção, ela é a escolhida. Se restar mais de uma, é empate: ficar com manter como está. Se essa opção já tiver sido excluída, ficar com a de menor custo de saída.
4. Se todas as opções forem excluídas, nada muda: o registro marca uma nova avaliação com data, e os requisitos são revistos.
5. Requisito cuja amostra não detecta a margem não conta como empate. Amplia-se a amostra até o teto de esforço ou o requisito fica registrado como não medido.

Não se somam notas em um número único.

**Bancada, para tecnologia:** mesma tarefa, mesmos dados, mesmas condições, versões fixadas e o mesmo teto de esforço por opção. A tarefa deriva dos requisitos, não de exemplos do fornecedor.

**Piloto, para processo:** linha de base antes do início, janela com data de fim, uma mudança por vez e condição de reversão definida. Outras mudanças ocorridas no período entram no registro.

Depois de aprovado, o plano só muda com motivo registrado. Mudar limite, margem, prioridade ou regra depois de ver qualquer resultado exige decisão do decisor, e o registro passa a mostrar o resultado nas duas versões e a dizer a quem a mudança favorece.

**Saída:** plano aprovado pelo decisor.

### 5. Coletar e verificar

1. Rodar os controles. Se a régua não reprovar o caso ruim ou não aprovar o caso bom, corrigir a régua antes de continuar.
2. Executar o plano.
3. Guardar artefatos que permitam repetir a medição: scripts, dados, versões e saídas.
4. Manter no registro as falhas e os resultados desfavoráveis.

Em piloto, a diferença é comparada com a variação normal da linha de base. Se a diferença for menor que essa variação, o resultado é inconclusivo.

Inconclusivo é um resultado válido. Com amostra capaz de detectar a margem, conta como empate. Sem essa capacidade, conta como não medido.

Quando leitura de documentação e execução divergirem, vale a execução no cenário testado. O registro diz qual cenário foi esse, sem generalizar.

**Saída:** resultados por requisito e por opção, com o grau de evidência alcançado.

### 6. Decidir

O decisor aplica a regra definida no passo 4. Pode decidir de outra forma, desde que registre o motivo. Antes de fechar, a regra é aplicada de novo trocando as duas primeiras prioridades e variando as margens, e o registro diz se a escolha muda. O registro inclui:

- a opção escolhida, os números que a sustentam e a diferença de cada opção contra a situação atual;
- a força da evidência e os limites de validade;
- a previsão numérica do que deve acontecer, em faixa, com os limites de confirmada, parcial e refutada;
- os gatilhos de reavaliação;
- a data de conferência.

**Gatilhos comuns:** mudança de equipe ou de projeto, versão maior de uma dependência, requisito novo, limite violado, mudança relevante de custo.

**Saída:** decisão registrada.

### 7. Conferir

Na data marcada, comparar a previsão com o observado e classificar a decisão como confirmada, parcial ou refutada, pelos limites definidos no passo 6. Se houver desvio, identificar a causa:

- requisito ausente ou mal definido;
- régua incapaz de detectar o problema;
- contexto alterado;
- opção mal implementada.

A causa alimenta as próximas decisões. Se um gatilho disparar antes da data, a conferência é antecipada.

**Saída:** conferência anexada ao registro da decisão.

## Reaproveitamento entre projetos

O resultado de outro projeto entra como evidência C ou D. Ele pode reduzir o trabalho do passo 4, mas não dispensa os requisitos do projeto atual.

## Modelo de registro

```markdown
# DE-000: <pergunta em uma frase>

Estado: em análise | decidida | conferida | substituída
Tipo: tecnologia | processo
Nível: leve | média | pesada
Decisor:
Condutor:
Prazo:

## Enquadramento
Custo de voltar atrás:
Premissas fixas:
Porte representativo:
Contexto (projeto, equipe, versões, fase):

## Requisitos
| ID | Requisito | Tipo | Fonte | Situação | Classe | Prioridade | Limite | Margem | Como medir |
|---|---|---|---|---|---|---|---|---|---|

## Opções
| Opção | Defensor | Custo de entrada | Custo de saída |
|---|---|---|---|
| Manter como está | | | |

Descartadas antes da coleta:

## Plano de evidência
| Requisito | Método | Amostra e duração | Grau esperado |
|---|---|---|---|

Avaliador:
Teto de esforço:
Controles (caso ruim e caso bom):
Capacidade de detecção:
Familiaridade do avaliador:
Regra de decisão:
Resultado que mudaria a decisão:
Pre-mortem:

## Resultados
Controles:

| Requisito | Opção | Resultado | Grau alcançado | Artefato |
|---|---|---|---|---|

Mudanças no plano, com resultado nas duas versões quando vierem depois de ver resultados, e outras mudanças no período:

## Decisão
Opção escolhida:
Motivo:
Diferença contra a situação atual:
Sensibilidade:
Força da evidência:
Limites de validade:
Previsão e limites de classificação:
Gatilhos de reavaliação:
Data de conferência:

## Conferência
Data:
Previsto x observado:
Classificação: confirmada | parcial | refutada
Causa do desvio:
Ajuste nas próximas decisões:
```

---

Desenvolvido por Diêgo Azevedo · [github.com/diegoazevedo-inov](https://github.com/diegoazevedo-inov)
