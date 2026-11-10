# Decisão Medida

A protocol for deciding a project's technology and process with evidence, against functional and non-functional requirements. The decision rule comes before data collection, the measuring instrument must prove it rejects a known bad case, and each decision records a prediction checked on a set date.

Status: draft v0.4, in first use. No decision has been checked yet. The documents are in Portuguese.

## Case: adopt an agent orchestration framework?

[DE-002](casos/DE-002-orquestracao-de-agentes.md) compared the provider SDK with MCP and no framework against LangGraph and Pydantic AI, on a synthetic task: a queue conductor with durable state, human confirmation and an agent over MCP.

All three passed the eliminatory requirements, including 50 forced crashes (5 fixed points repeated 10 times, during start and item completion). Accuracy over 90 commands with a real model was 100% for all three, at US$ 0.41, 0.38 and 0.34. The rule selected the SDK with MCP, on dependencies: 33 packages against 69 and 62. The outputs behind these numbers are in [casos/DE-002-artefatos/](casos/DE-002-artefatos/). DE-001, the method's first case, is private.

The result depends on the margin and on the metric for own code. Counting lines with the original 20% margin, Pydantic AI would win; the margin was raised to 40% after partial results, in favor of the option already in use, and that change is recorded. Counting tokens with the Python 3.12+ tokenizer, the no-framework option stays within the original margin by 0.06%, which does not make the result robust. The accuracy measure repeats the same 30 commands three times, so its 90 measurements are not independent and it cannot separate the options: it works as a floor, not a tiebreaker. The measuring instrument was revised after a first independent audit found 9 defects it missed; those became controls, and all three options pass the revised version. A second audit showed 5 more defects outside the instrument, which all three options also pass; they are listed in DE-002 as not measured. The task is small, each option had one implementation built by an agentic system, and the result applies to this task, these versions and this model. It is not a general assessment of the frameworks.

## Reproduce

```bash
./bancada/provar_regua.sh
```

Python 3, standard library only, no network, no account. Measuring the options requires Python 3.11 or newer. The reference must pass, and each planted defect must fail on the expected requirement.

## License

Apache License 2.0.
