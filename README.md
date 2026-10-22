# Grant Overlap Primitive

A GenLayer Intelligent Contract for one project's co-funded expenses. It compares candidate expenses against the registered ledger by meaning, rejects duplicates or uncertainty, and enforces deterministic reservation ceilings.

## State and authority

The deployer is the project registrar. Only that wallet may register costs, reserve capacity or release reservations; everyone can read `snapshot()`. This is a transparent registrar-controlled register, not a trustless invoice verifier. A dishonest registrar can omit expenses or supply false evidence. Different deployments do not discover each other's funding.

Costs and their caps are immutable. Every reservation has a globally unique reference within the deployment, retained after release. Integer amounts represent hundredths of the selected currency. No tokens are received, escrowed or paid out.

## Deployment and use

Load `contracts/grant_overlap.py` into GenLayer Studio. Constructor arguments: project name and uppercase three-letter currency, for example `Community Workshop`, `USD`. Supported currencies: USD, EUR, GBP, CNY, SGD, AUD, CAD, HKD and CHF. Every amount uses two decimal minor units.

1. Call `register_cost(description, evidence, cap)`. Include supplier, invoice identifier, service period, item quantity and deliverable in the evidence. For example, a 1,200 USD microscope has cap `120000`.
2. Call `reserve(1, "Science fund", 70000, "SCI-001")`.
3. Call `reserve(1, "Local sponsor", 50000, "LOCAL-001")`. Both contributions fit the same cost cap. A further reservation fails.
4. Call `release(1)` to reopen the first contribution's capacity while preserving history.
5. Read `snapshot()` to inspect costs and reservations.

The first cost needs no comparison. Subsequent costs trigger independent LLM reasoning by leader and validators. The validator reruns classification from the same fixed ledger inputs and compares all indexed SAME / DISTINCT / UNCERTAIN decisions. It rejects malformed output and non-return results. SAME and UNCERTAIN both prevent a new cost cap. Use the existing cost for co-funding; supply more specific evidence for an actually distinct expense. Partial overlaps must be clarified and split outside this immutable register.

## Bounds

24 costs, 120 reservation records, 900-character descriptions, 1,800-character evidence, amounts from 1 to 10^12 minor units. These limits bound storage and comparison work. Do not put personal, confidential or payment data on a public chain. Evidence text is treated as untrusted data in prompts; semantic models can still err.

## Tests

```sh
python3 -m unittest discover -s tests -v
python3 -m pip install -r requirements-dev.txt
pytest tests/direct -q
genvm-lint check contracts/grant_overlap.py
genvm-lint schema contracts/grant_overlap.py --output contracts/grant_overlap.abi.json
```

The dependency-free harness covers accounting, permissions, limits and malformed decisions. Official GenLayer Direct Mode tests use SDK storage and calldata serialization with mocked LLM I/O. They explicitly replay the validator with matching and conflicting independent responses. Model output may arrive as JSON text or a decoded list; both pass through the same strict schema and index checks.

Direct Mode runs native Python, not the full WASM GenVM, and does not establish real model accuracy or network consensus. Runtime deployment and real multi-validator transactions remain necessary. The first Direct Mode run downloads the GenVM v0.2.16 SDK bundle corresponding to the source dependency header.

## References

- [GenLayer equivalence principle](https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle)
- [GenLayer Studio](https://studio.genlayer.com/)

MIT licensed.
