# Antecedentes

Cada parte do protocolo tem antecedente. O que pode ser distinto é a montagem, não as partes.

## Origem de cada elemento

| Elemento | Antecedentes |
|---|---|
| Escolha formal entre opções | [CMMI DAR](https://doi.org/10.1184/R1/6572342.v1), [GAO Analysis of Alternatives](https://guides.gaoinnovations.gov/cost-guide/appendix-xi-best-practices-for-the-analysis-of-alternatives-process.html), Kepner-Tregoe |
| Tecnologia e processo no mesmo arcabouço | DESMET (Kitchenham et al., 1996-97), CMMI DAR |
| Requisito com número e forma de medir | Planguage (Gilb), Volere, cenários do [ATAM](https://www.sei.cmu.edu/library/atam-method-for-architecture-evaluation) |
| Situação atual como referência | Green Book do Tesouro do Reino Unido, GAO, [NICE](https://www.nice.org.uk/process/pmg36/resources/nice-health-technology-evaluations-themanual-pdf-72286779244741) |
| Critérios definidos antes dos resultados | [Pre-registration](https://pmc.ncbi.nlm.nih.gov/articles/PMC5856500), Kepner-Tregoe, [FAR 15.3](https://www.acquisition.gov/far/subpart-15.3), [Lei 14.133/2021](https://www.planalto.gov.br/ccivil_03/_ato2019-2022/2021/lei/l14133.htm) |
| Eliminatório antes de comparar | Kepner-Tregoe, filtro conjuntivo em análise multicritério |
| Ordem de prioridade com limiar | [Lexicographic semiorder](https://doi.org/10.1037/h0026750) (Tversky, 1969) |
| Grau de evidência separado da decisão | [GRADE](https://gdt.gradepro.org/app/handbook/handbook.html) |
| Quem defende não avalia | NICE, GAO |
| Teste do instrumento com caso conhecido | [Negative controls](https://pmc.ncbi.nlm.nih.gov/articles/PMC3053408/), teste A/A, [mutation testing](https://doi.org/10.1109/C-M.1978.218136), [Agentic Benchmark Checklist](https://arxiv.org/html/2507.02825v5) |
| Previsão e conferência | PDSA, [decision journal](https://fs.blog/decision-journal/), [Hypothesis-Driven Development](https://www.thoughtworks.com/insights/articles/how-implement-hypothesis-driven-development), Planguage |
| Registro e revisão de decisão técnica | [ADR](https://www.cognitect.com/blog/2011/11/15/documenting-architecture-decisions), [MADR](https://adr.github.io/madr/), [ecADR](https://ozimmer.ch/practices/2020/05/22/ADDefinitionOfDone.html) |
| Lista de atributos de qualidade | [ISO/IEC 25010](https://committee.iso.org/standard/78176.html) |

A regra de decisão padrão é, na essência, uma lexicographic semiorder depois de um filtro eliminatório.

## Combinações menos comuns

Estes pontos não apareceram nas fontes lidas. Isso descreve uma busca, não uma afirmação de ineditismo, e novas leituras podem mudar o quadro.

- Controle negativo como passo obrigatório de uma seleção de tecnologia.
- Previsão numérica com causa do desvio no próprio registro de decisão técnica.
- Custo de voltar atrás definindo ao mesmo tempo a evidência mínima e a separação de papéis.
- O conjunto completo em forma leve, para equipe pequena. Os processos mais próximos, como GAO, Green Book e NICE, são institucionais e de grande porte.

## Limites desta varredura

Normas pagas, como a ISO/IEC 25010, foram lidas só em escopo e prévia. CMMI foi lido em resumo de terceiros. DESMET, Tversky e os livros de Gilb e Kepner-Tregoe não foram lidos na íntegra.
