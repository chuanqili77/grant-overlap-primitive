# Grant Overlap Primitive

A GenLayer Intelligent Contract for shared project expenses. V2 separates the project party from two fixed funders: both funders approve an immutable expense proposal, then GenLayer compares it against the latest active ledger before creating a cap. Reservations belong to the funder who signs them.

[GrantWeave application](https://chuanqili77.github.io/grantweave-genlayer/) · [Application source](https://github.com/chuanqili77/grantweave-genlayer)

## V2 deployment

- Network: Studio Network, chain `61999`
- [Contract](https://explorer-studio.genlayer.com/address/0x905A5Fb6212677d43cc2f4CdE75A36069e8136f6): `0x905A5Fb6212677d43cc2f4CdE75A36069e8136f6`
- Deployment transaction: `0x131839e89ba89541cef2f2eb066e348849d37b7d2ec949e7561f9d9fa539a448`
- [Deployment record](https://github.com/chuanqili77/grantweave-genlayer/blob/main/public/deployment.json)
- [V2 network verification](https://github.com/chuanqili77/grantweave-genlayer/blob/main/public/studionet-v2-verification.json)

The public instance uses three controlled test wallets. It demonstrates enforced permissions between distinct addresses, not independent organizations. All test writes transfer zero value; invoice facts are synthetic.

## Authority and invariants

| Action | Project party | Funder A | Funder B |
| --- | --- | --- | --- |
| Propose immutable expense facts and cap | Yes | Yes | Yes |
| Approve a proposal | No | Own approval | Own approval |
| Activate after both approvals and overlap check | Yes | Yes | Yes |
| Reserve active expense capacity | No | Own address | Own address |
| Release a reservation | No | Own records | Own records |

All three addresses must be distinct and nonzero. There is no participant replacement, administrator override, edit or deletion of active expenses. Pending proposals have no funding capacity. Even two approvals cannot bypass the semantic overlap check. Activation reads the current active ledger, so separately approved pending duplicates cannot both create caps.

Leader and validators independently classify the fixed candidate against every active expense as SAME, DISTINCT or UNCERTAIN. The validator reruns classification and compares the complete indexed result. Malformed decisions, non-return results, SAME and UNCERTAIN prevent activation. The first expense needs no semantic comparison because the active ledger is empty.

Reservation ceilings use positive integer minor units. References are unique per funder across the full reservation history, including released records. Release restores capacity while retaining the original funder, amount and reference. No tokens are received, escrowed or paid out.

## Deploy and use V2

Load `contracts/grant_overlap_v2.py` into GenLayer Studio. Constructor arguments are project name, uppercase currency, funder A address and funder B address. The deploying wallet becomes the project party. Supported currencies: USD, EUR, GBP, CNY, SGD, AUD, CAD, HKD and CHF; all use two decimal minor units.

1. Any participant calls `propose_cost(description, evidence, cap)`. Include supplier, invoice identifier, service period, quantities and deliverable. A USD 1,200 expense uses cap `120000`.
2. Each funder signs `approve_cost(proposal_id)` from its own wallet. Repeated approval by the same address cannot satisfy the second approval.
3. A participant calls `activate_cost(proposal_id)`. Both approvals are required, and overlap is checked against the latest active expenses before a cap is created.
4. A funder calls `reserve(cost_id, amount, reference)`. The contract records the caller's address and enforces the shared cap.
5. That same funder can call `release(reservation_id)`. The project party and other funder cannot release it.
6. Anyone reads `snapshot()` to inspect participants, proposals, approvals, active costs and reservation history.

If activation rejects a duplicate, fund the existing active expense instead. Uncertain evidence requires a new, clarified proposal and fresh approvals; proposal facts cannot be edited after approval.

## Scope and bounds

24 active costs, 48 proposals and 120 reservation records. Descriptions allow 900 characters, evidence 1,800 characters, and amounts range from 1 to 10^12 minor units. These bounds limit storage and comparison work. Pending proposals consume the proposal limit even if never activated.

Addresses do not establish real-world independence. One person may control several wallets, participants may collude, supplied invoices may be false, and either funder can block activation by withholding approval. The ledger cannot see undisclosed funding or other deployments. Consensus evaluates expense overlap from supplied facts; it does not certify invoice authenticity. Semantic errors remain possible. Do not put confidential or personal information on a public chain.

## Verification

```sh
python3 -m unittest discover -s tests -v
python3 -m pip install -r requirements-dev.txt
pytest tests/direct -q
genvm-lint check contracts/grant_overlap.py
genvm-lint check contracts/grant_overlap_v2.py
genvm-lint schema contracts/grant_overlap_v2.py --output contracts/grant_overlap_v2.abi.json
```

The dependency-free harness covers permissions, approval thresholds, cap accounting and malformed model decisions. Official GenLayer Direct Mode tests exercise SDK storage and calldata serialization, with mocked model responses and independent validator replay. Direct Mode runs native Python, not a real validator network. Its first run downloads the v0.2.16 SDK bundle matching the contract dependency header. Actual network results and before/after snapshots are recorded separately in the linked V2 evidence.

## Legacy V1

`contracts/grant_overlap.py` is preserved for existing deployments. Its registrar alone registers costs, reserves and releases entries. Funding source names are labels, not funder consent. It does not provide V2's role separation.

V1 address: `0x87cB0341BDd533338e00A9E7F29dDd0396857A27` · [V1 verification](https://github.com/chuanqili77/grantweave-genlayer/blob/main/public/studionet-verification.json).

## References

- [GenLayer equivalence principle](https://docs.genlayer.com/developers/intelligent-contracts/equivalence-principle)
- [GenLayer Studio](https://studio.genlayer.com/)

MIT licensed.
