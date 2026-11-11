# Decisão Medida

A protocol for deciding a project's technology and process with evidence, against functional and non-functional requirements. The decision rule comes before data collection, the measuring instrument must prove it rejects a known bad case, and each decision records a prediction checked on a set date.

Version 0.4. First check scheduled for 2027-02-04. The documents are in Portuguese.

## Case: adopt an agent orchestration framework?

[DE-002](casos/DE-002-orquestracao-de-agentes.md) compared the provider SDK with MCP and no framework against LangGraph and Pydantic AI, on a synthetic task: a queue conductor with durable state, human confirmation and an agent over MCP. The outputs behind the numbers are in [casos/DE-002-artefatos/](casos/DE-002-artefatos/).

**What the case shows:** on this task, no framework added a guarantee the SDK with MCP lacked. Recovery after crashes, human confirmation for protected operations and halting on a mismatched identifier were met by all three options and verified by the same test bench; the differences were in own code and dependencies.

**Result:** keep the SDK with MCP. All three met every eliminatory requirement, including 50 forced crashes (5 points in the flow, 10 times each), and all three reached 100% accuracy over 90 commands with a real model, at US$ 0.41, 0.38 and 0.34. The tiebreaker was dependencies: 33 packages against 69 and 62.

**Reading the result:**

- It applies to this task (about 400 lines, one implementation per option), these versions and this model. Larger systems may call for a different answer.
- The sensitive point is own code. With the 20% margin set at the start, measured in lines, Pydantic AI would be chosen; the margin was revised to 40% during collection. Both readings, and a token-based measure, are in DE-002.
- The test bench went through two independent audits and a targeted verification. The defects found became controls or are declared in DE-002 as not measured, and all three options pass them all.

## Reproduce

```bash
./bancada/provar_regua.sh
```

Python 3, standard library only, no network, no account. Measuring the options requires Python 3.11 or newer. The reference must pass, and each planted defect must fail on the expected requirement.

## License

Apache License 2.0.
