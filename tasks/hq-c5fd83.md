---
id: hq-c5fd83
title: Restore original historical attachments after the verified layout exemption ships
status: todo
priority: 3
size: s
complexity: low
process: direct
created: 2026-10-25T10:54:20Z
updated: 2026-10-25T10:54:57Z
depends: [ops-6e157a]
tags: []
source: hq-c6a149
agent: claude-code
---

Adopting the shared checker (hq-c6a149) required the attachments the layout rule refuses to be represented by portable derivatives. Each original is preserved byte for byte under persistent WORK_ROOT storage; the files this task owns are those its retained: notes list, each with its SHA-256, and each original task carries the placeholder mapping and the raw item's identity. After the implemented attachment policy ships (ops-6e157a) and hq adopts that checker version, verify every raw copy's hash and the current attachment ledger, restore the exact original bytes through tasks detach and tasks attach under the same names, rerun the executing checker, and release each retained file only after its restored attachment is verified. Design completion alone does not trigger restoration.

## Notes

- 2026-10-25T10:54:30Z (feat/ops-check-hq-c6a149): Scratch directory created: host titan, path $WORK_ROOT/hq/hq-c5fd83, purpose exact raw copies of the attachments hq-c6a149 replaces with portable derivatives (one subdirectory per original task) and their manifest; owner task:hq-c5fd83; contents mutable and not yet checkpointed.
- 2026-10-25T10:54:54Z (feat/ops-check-hq-c6a149): retained: {"host":"titan","kind":"evidence","path":"$WORK_ROOT/hq/hq-c5fd83/hq-48c5c6/europa-policy-check.out","state":"kept","verification":"verified","sha256":"415aeb15c12f6f82ff29d885148fcd8636fefd0c64e9639831fe10b91aad1fcd","purpose":"Exact raw bytes of hq-48c5c6 attachment europa-policy-check.out, replaced on that task by a portable derivative for shared-checker adoption","next_owner":"task:hq-c5fd83","cleanup_trigger":"After the shipped layout exemption admits the original and hq adopts that checker version, restore and verify the original attachment"}
- 2026-10-25T10:54:54Z (feat/ops-check-hq-c6a149): retained: {"host":"titan","kind":"evidence","path":"$WORK_ROOT/hq/hq-c5fd83/hq-48c5c6/europa-policy-check-round2.out","state":"kept","verification":"verified","sha256":"e3fd6750d5373f7360ac3c920bb4c6769edeb6fe1edef52ac70a5cc0c79f0522","purpose":"Exact raw bytes of hq-48c5c6 attachment europa-policy-check-round2.out, replaced on that task by a portable derivative for shared-checker adoption","next_owner":"task:hq-c5fd83","cleanup_trigger":"After the shipped layout exemption admits the original and hq adopts that checker version, restore and verify the original attachment"}
- 2026-10-25T10:54:55Z (feat/ops-check-hq-c6a149): retained: {"host":"titan","kind":"evidence","path":"$WORK_ROOT/hq/hq-c5fd83/hq-48c5c6/forms-probe.out","state":"kept","verification":"verified","sha256":"bd6911f7a323894f486514a47d0928bb53388c8cba6bdd60a9c20b9cb334d7cc","purpose":"Exact raw bytes of hq-48c5c6 attachment forms-probe.out, replaced on that task by a portable derivative for shared-checker adoption","next_owner":"task:hq-c5fd83","cleanup_trigger":"After the shipped layout exemption admits the original and hq adopts that checker version, restore and verify the original attachment"}
- 2026-10-25T10:54:55Z (feat/ops-check-hq-c6a149): retained: {"host":"titan","kind":"evidence","path":"$WORK_ROOT/hq/hq-c5fd83/hq-48c5c6/live-fixture.out","state":"kept","verification":"verified","sha256":"c475854df9f5deacf1538467cb1b6e2316390d3086a0f19b9bd93bbda35952cb","purpose":"Exact raw bytes of hq-48c5c6 attachment live-fixture.out, replaced on that task by a portable derivative for shared-checker adoption","next_owner":"task:hq-c5fd83","cleanup_trigger":"After the shipped layout exemption admits the original and hq adopts that checker version, restore and verify the original attachment"}
